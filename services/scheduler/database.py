"""
Database interface for the Cron Scheduler service.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from .models import Schedule, ScheduleRun

logger = logging.getLogger(__name__)


class SchedulerDatabase:
    """Database interface for managing schedules and schedule runs."""
    
    def __init__(self, db_path: str = "scheduler.db"):
        """Initialize the database connection."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schedules (
                        schedule_id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        cron_expr TEXT NOT NULL,
                        timezone TEXT NOT NULL,
                        start_at TEXT,
                        end_at TEXT,
                        next_run_at TEXT NOT NULL,
                        paused INTEGER DEFAULT 0,
                        jitter_ms INTEGER DEFAULT 0,
                        overlap_policy TEXT DEFAULT 'skip',
                        catchup_policy TEXT DEFAULT 'none',
                        updated_at TEXT NOT NULL
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schedule_runs (
                        idempotency_key TEXT PRIMARY KEY,
                        schedule_id TEXT NOT NULL,
                        run_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        run_id TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (schedule_id) REFERENCES schedules (schedule_id)
                    )
                """)
                
                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON schedules(next_run_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_paused ON schedules(paused)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_schedule_runs_schedule_id ON schedule_runs(schedule_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_schedule_runs_status ON schedule_runs(status)")
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _datetime_to_str(self, dt: datetime) -> str:
        """Convert datetime to ISO string for storage."""
        if dt is None:
            return None
        return dt.isoformat()
    
    def _str_to_datetime(self, dt_str: str) -> Optional[datetime]:
        """Convert ISO string to datetime."""
        if dt_str is None:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None
    
    def upsert_schedule(self, schedule: Schedule) -> Schedule:
        """Insert or update a schedule."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO schedules (
                        schedule_id, workflow_id, version, user_id, cron_expr, timezone,
                        start_at, end_at, next_run_at, paused, jitter_ms,
                        overlap_policy, catchup_policy, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    schedule.schedule_id,
                    schedule.workflow_id,
                    schedule.version,
                    schedule.user_id,
                    schedule.cron_expr,
                    schedule.timezone,
                    self._datetime_to_str(schedule.start_at),
                    self._datetime_to_str(schedule.end_at),
                    self._datetime_to_str(schedule.next_run_at),
                    1 if schedule.paused else 0,
                    schedule.jitter_ms,
                    schedule.overlap_policy,
                    schedule.catchup_policy,
                    self._datetime_to_str(schedule.updated_at)
                ))
                conn.commit()
                logger.info(f"Schedule {schedule.schedule_id} upserted successfully")
                return schedule
                
        except Exception as e:
            logger.error(f"Failed to upsert schedule: {e}")
            raise
    
    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM schedules WHERE schedule_id = ?
                """, (schedule_id,))
                row = cursor.fetchone()
                
                if row:
                    return Schedule(
                        schedule_id=row[0],
                        workflow_id=row[1],
                        version=row[2],
                        user_id=row[3],
                        cron_expr=row[4],
                        timezone=row[5],
                        start_at=self._str_to_datetime(row[6]),
                        end_at=self._str_to_datetime(row[7]),
                        next_run_at=self._str_to_datetime(row[8]),
                        paused=bool(row[9]),
                        jitter_ms=row[10],
                        overlap_policy=row[11],
                        catchup_policy=row[12],
                        updated_at=self._str_to_datetime(row[13])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get schedule: {e}")
            raise
    
    def get_due_schedules(self, now: datetime, lookahead_ms: int) -> List[Schedule]:
        """Get schedules that are due within the lookahead window."""
        try:
            lookahead_time = datetime.fromtimestamp(now.timestamp() + lookahead_ms / 1000)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM schedules
                    WHERE paused = 0
                    AND (end_at IS NULL OR end_at >= ?)
                    AND next_run_at <= ?
                    ORDER BY next_run_at ASC
                """, (
                    self._datetime_to_str(now),
                    self._datetime_to_str(lookahead_time)
                ))
                
                schedules = []
                for row in cursor.fetchall():
                    schedule = Schedule(
                        schedule_id=row[0],
                        workflow_id=row[1],
                        version=row[2],
                        user_id=row[3],
                        cron_expr=row[4],
                        timezone=row[5],
                        start_at=self._str_to_datetime(row[6]),
                        end_at=self._str_to_datetime(row[7]),
                        next_run_at=self._str_to_datetime(row[8]),
                        paused=bool(row[9]),
                        jitter_ms=row[10],
                        overlap_policy=row[11],
                        catchup_policy=row[12],
                        updated_at=self._str_to_datetime(row[13])
                    )
                    schedules.append(schedule)
                
                return schedules
                
        except Exception as e:
            logger.error(f"Failed to get due schedules: {e}")
            raise
    
    def update_schedule_next_run(self, schedule_id: str, next_run_at: datetime):
        """Update the next run time for a schedule."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE schedules 
                    SET next_run_at = ?, updated_at = ?
                    WHERE schedule_id = ?
                """, (
                    self._datetime_to_str(next_run_at),
                    self._datetime_to_str(datetime.utcnow()),
                    schedule_id
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update schedule next run: {e}")
            raise
    
    def pause_schedule(self, schedule_id: str, paused: bool):
        """Pause or unpause a schedule."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE schedules 
                    SET paused = ?, updated_at = ?
                    WHERE schedule_id = ?
                """, (
                    1 if paused else 0,
                    self._datetime_to_str(datetime.utcnow()),
                    schedule_id
                ))
                conn.commit()
                logger.info(f"Schedule {schedule_id} {'paused' if paused else 'unpaused'}")
                
        except Exception as e:
            logger.error(f"Failed to pause/unpause schedule: {e}")
            raise
    
    def delete_schedule(self, schedule_id: str):
        """Delete a schedule and all its runs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Delete associated runs first
                conn.execute("DELETE FROM schedule_runs WHERE schedule_id = ?", (schedule_id,))
                # Delete the schedule
                conn.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))
                conn.commit()
                logger.info(f"Schedule {schedule_id} deleted successfully")
                
        except Exception as e:
            logger.error(f"Failed to delete schedule: {e}")
            raise
    
    def insert_schedule_run(self, run: ScheduleRun):
        """Insert a new schedule run record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO schedule_runs (
                        idempotency_key, schedule_id, run_at, status, run_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    run.idempotency_key,
                    run.schedule_id,
                    self._datetime_to_str(run.run_at),
                    run.status,
                    run.run_id,
                    self._datetime_to_str(run.created_at),
                    self._datetime_to_str(run.updated_at)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to insert schedule run: {e}")
            raise
    
    def get_schedule_run(self, idempotency_key: str) -> Optional[ScheduleRun]:
        """Get a schedule run by idempotency key."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM schedule_runs WHERE idempotency_key = ?
                """, (idempotency_key,))
                row = cursor.fetchone()
                
                if row:
                    return ScheduleRun(
                        idempotency_key=row[0],
                        schedule_id=row[1],
                        run_at=self._str_to_datetime(row[2]),
                        status=row[3],
                        run_id=row[4],
                        created_at=self._str_to_datetime(row[5]),
                        updated_at=self._str_to_datetime(row[6])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get schedule run: {e}")
            raise
    
    def has_inflight_runs(self, schedule_id: str) -> bool:
        """Check if a schedule has any inflight runs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM schedule_runs
                    WHERE schedule_id = ? AND status IN ('ENQUEUED', 'STARTED')
                """, (schedule_id,))
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"Failed to check inflight runs: {e}")
            raise
    
    def get_recent_runs(self, schedule_id: str, limit: int = 10) -> List[ScheduleRun]:
        """Get recent runs for a schedule."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM schedule_runs
                    WHERE schedule_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (schedule_id, limit))
                
                runs = []
                for row in cursor.fetchall():
                    run = ScheduleRun(
                        idempotency_key=row[0],
                        schedule_id=row[1],
                        run_at=self._str_to_datetime(row[2]),
                        status=row[3],
                        run_id=row[4],
                        created_at=self._str_to_datetime(row[5]),
                        updated_at=self._str_to_datetime(row[6])
                    )
                    runs.append(run)
                
                return runs
                
        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            raise
