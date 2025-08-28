"""
Scheduler Worker that scans due schedules and starts workflow runs.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List
import logging

from .database import SchedulerDatabase
from .run_launcher import RunLauncher
from .models import Schedule, ScheduleRun
from .cron_utils import (
    generate_idempotency_key, 
    apply_jitter, 
    enumerate_due_times,
    get_next_cron_time
)

logger = logging.getLogger(__name__)


class SchedulerWorker:
    """Worker process that scans due schedules and starts workflow runs."""
    
    def __init__(
        self, 
        db: SchedulerDatabase,
        run_launcher: RunLauncher,
        tick_ms: int = 1000,
        lookahead_ms: int = 60000,
        max_catchup_per_tick: int = 100
    ):
        """
        Initialize the scheduler worker.
        
        Args:
            db: Database interface
            run_launcher: RunLauncher instance
            tick_ms: Milliseconds between ticks
            lookahead_ms: Lookahead window in milliseconds
            max_catchup_per_tick: Maximum catchup runs per tick
        """
        self.db = db
        self.run_launcher = run_launcher
        self.tick_ms = tick_ms
        self.lookahead_ms = lookahead_ms
        self.max_catchup_per_tick = max_catchup_per_tick
        
        self.running = False
        self.worker_thread = None
        self.leader_lock = None
        
        # Configuration
        self.leader_lock_timeout = 30  # seconds
        self.retry_attempts = 3
        self.retry_backoff_ms = 1000
    
    def start(self):
        """Start the worker process."""
        if self.running:
            logger.warning("Worker is already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Scheduler worker started")
    
    def stop(self):
        """Stop the worker process."""
        if not self.running:
            logger.warning("Worker is not running")
            return
        
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        logger.info("Scheduler worker stopped")
    
    def _worker_loop(self):
        """Main worker loop."""
        logger.info("Starting scheduler worker loop")
        
        while self.running:
            try:
                # Try to acquire leader lock
                if not self._acquire_leader_lock():
                    time.sleep(self.tick_ms / 1000.0)
                    continue
                
                # Process due schedules
                self._process_tick()
                
                # Release leader lock
                self._release_leader_lock()
                
                # Sleep until next tick
                time.sleep(self.tick_ms / 1000.0)
                
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                self._release_leader_lock()
                time.sleep(self.tick_ms / 1000.0)
        
        logger.info("Scheduler worker loop ended")
    
    def _acquire_leader_lock(self) -> bool:
        """
        Try to acquire the leader lock.
        
        Returns:
            True if lock was acquired, False otherwise
        """
        try:
            # For now, we'll use a simple file-based lock
            # In production, use Redis SETNX or Postgres advisory lock
            import os
            
            lock_file = "scheduler_worker.lock"
            
            if os.path.exists(lock_file):
                # Check if lock is stale
                lock_time = os.path.getmtime(lock_file)
                if time.time() - lock_time > self.leader_lock_timeout:
                    # Remove stale lock
                    os.remove(lock_file)
            
            # Try to create lock file
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            self.leader_lock = lock_file
            return True
            
        except Exception as e:
            logger.debug(f"Failed to acquire leader lock: {e}")
            return False
    
    def _release_leader_lock(self):
        """Release the leader lock."""
        try:
            if self.leader_lock and os.path.exists(self.leader_lock):
                os.remove(self.leader_lock)
                self.leader_lock = None
        except Exception as e:
            logger.error(f"Failed to release leader lock: {e}")
    
    def _process_tick(self):
        """Process one tick - scan due schedules and start runs."""
        try:
            now = datetime.utcnow()
            
            # Get schedules that are due within the lookahead window
            due_schedules = self.db.get_due_schedules(now, self.lookahead_ms)
            
            if not due_schedules:
                return
            
            logger.debug(f"Processing {len(due_schedules)} due schedules")
            
            for schedule in due_schedules:
                try:
                    self._process_schedule(schedule, now)
                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.schedule_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
    
    def _process_schedule(self, schedule: Schedule, now: datetime):
        """Process a single schedule."""
        try:
            # Enumerate all due times for this schedule
            run_times = enumerate_due_times(
                schedule.cron_expr,
                schedule.timezone,
                schedule.next_run_at,
                now,
                self.lookahead_ms,
                schedule.catchup_policy
            )
            
            if not run_times:
                return
            
            # Limit catchup runs
            if schedule.catchup_policy != "none":
                run_times = run_times[:self.max_catchup_per_tick]
            
            # Process each run time
            for run_at in run_times:
                try:
                    self._process_run_time(schedule, run_at, now)
                except Exception as e:
                    logger.error(f"Error processing run time {run_at} for schedule {schedule.schedule_id}: {e}")
                    continue
            
            # Update next run time
            if run_times:
                last_considered = max(now, run_times[-1])
                next_run_at = get_next_cron_time(schedule.cron_expr, schedule.timezone, last_considered)
                self.db.update_schedule_next_run(schedule.schedule_id, next_run_at)
            
        except Exception as e:
            logger.error(f"Error processing schedule {schedule.schedule_id}: {e}")
    
    def _process_run_time(self, schedule: Schedule, run_at: datetime, now: datetime):
        """Process a single run time for a schedule."""
        try:
            # Generate idempotency key
            idempotency_key = generate_idempotency_key(schedule.schedule_id, run_at)
            
            # Check if this run already exists
            existing_run = self.db.get_schedule_run(idempotency_key)
            if existing_run:
                logger.debug(f"Run {idempotency_key} already exists, skipping")
                return
            
            # Check overlap policy
            if schedule.overlap_policy != "allow":
                if self.db.has_inflight_runs(schedule.schedule_id):
                    if schedule.overlap_policy == "skip":
                        # Mark as skipped
                        run = ScheduleRun(
                            idempotency_key=idempotency_key,
                            schedule_id=schedule.schedule_id,
                            run_at=run_at,
                            status="SKIPPED"
                        )
                        self.db.insert_schedule_run(run)
                        logger.info(f"Run {idempotency_key} skipped due to overlap policy")
                        return
                    elif schedule.overlap_policy == "queue":
                        # Stop processing more runs for this schedule
                        logger.debug(f"Queueing run {idempotency_key} due to overlap policy")
                        return
            
            # Apply jitter
            fire_at = apply_jitter(run_at, schedule.jitter_ms)
            
            # Start the workflow if it's time to fire
            if fire_at <= now:
                success = self._start_workflow(schedule, run_at, idempotency_key)
                status = "ENQUEUED" if success else "FAILED"
            else:
                # Schedule for future execution
                # For now, we'll just mark it as enqueued
                # In production, you might want to use a timer or queue
                success = True
                status = "ENQUEUED"
            
            # Record the run
            run = ScheduleRun(
                idempotency_key=idempotency_key,
                schedule_id=schedule.schedule_id,
                run_at=run_at,
                status=status
            )
            self.db.insert_schedule_run(run)
            
            if success:
                logger.info(f"Run {idempotency_key} started successfully")
            else:
                logger.error(f"Run {idempotency_key} failed to start")
            
        except Exception as e:
            logger.error(f"Error processing run time {run_at}: {e}")
    
    def _start_workflow(self, schedule: Schedule, run_at: datetime, idempotency_key: str) -> bool:
        """Start a workflow execution."""
        try:
            # Retry logic for starting workflows
            for attempt in range(self.retry_attempts):
                try:
                    success = self.run_launcher.start(
                        schedule.workflow_id,
                        schedule.version,
                        schedule.user_id,
                        run_at,
                        idempotency_key
                    )
                    
                    if success:
                        return True
                    
                    # Wait before retry
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_backoff_ms / 1000.0)
                        
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < self.retry_attempts - 1:
                        time.sleep(self.retry_backoff_ms / 1000.0)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to start workflow: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get the current status of the worker."""
        return {
            "running": self.running,
            "tick_ms": self.tick_ms,
            "lookahead_ms": self.lookahead_ms,
            "max_catchup_per_tick": self.max_catchup_per_tick,
            "leader_lock": self.leader_lock is not None
        }
