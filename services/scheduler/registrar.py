"""
Scheduler Registrar for managing schedule registration and updates.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import logging

from .models import Schedule, ScheduleInput, SchedulePreview
from .database import SchedulerDatabase
from .cron_utils import get_next_cron_time, validate_cron_expression, validate_timezone

logger = logging.getLogger(__name__)


class SchedulerRegistrar:
    """Handles schedule registration, updates, and management."""
    
    def __init__(self, db: SchedulerDatabase):
        """Initialize the registrar with a database connection."""
        self.db = db
    
    def upsert_schedule(self, input_data: ScheduleInput) -> Dict[str, Any]:
        """
        Insert or update a schedule.
        
        Args:
            input_data: Schedule input data
            
        Returns:
            Dict with schedule_id and next_run_at
            
        Raises:
            ValueError: If cron expression or timezone is invalid
        """
        try:
            # Validate inputs
            if not validate_cron_expression(input_data.cron_expr):
                raise ValueError(f"Invalid cron expression: {input_data.cron_expr}")
            
            if not validate_timezone(input_data.timezone):
                raise ValueError(f"Invalid timezone: {input_data.timezone}")
            
            # Generate schedule ID if not provided
            schedule_id = input_data.schedule_id or self._generate_schedule_id(input_data)
            
            # Calculate next run time
            now = datetime.utcnow()
            base_time = max(now, input_data.start_at) if input_data.start_at else now
            next_run_at = get_next_cron_time(input_data.cron_expr, input_data.timezone, base_time)
            
            # Create schedule object
            schedule = Schedule(
                schedule_id=schedule_id,
                workflow_id=input_data.workflow_id,
                version=input_data.version,
                user_id=input_data.user_id,
                cron_expr=input_data.cron_expr,
                timezone=input_data.timezone,
                start_at=input_data.start_at,
                end_at=input_data.end_at,
                next_run_at=next_run_at,
                paused=False,
                jitter_ms=input_data.jitter_ms or 0,
                overlap_policy=input_data.overlap_policy or 'skip',
                catchup_policy=input_data.catchup_policy or 'none',
                updated_at=now
            )
            
            # Store in database
            self.db.upsert_schedule(schedule)
            
            logger.info(f"Schedule {schedule_id} upserted successfully")
            
            return {
                "schedule_id": schedule_id,
                "next_run_at": next_run_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to upsert schedule: {e}")
            raise
    
    def pause_schedule(self, schedule_id: str, paused: bool = True) -> None:
        """
        Pause or unpause a schedule.
        
        Args:
            schedule_id: ID of the schedule to pause/unpause
            paused: True to pause, False to unpause
        """
        try:
            # Check if schedule exists
            schedule = self.db.get_schedule(schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")
            
            self.db.pause_schedule(schedule_id, paused)
            logger.info(f"Schedule {schedule_id} {'paused' if paused else 'unpaused'}")
            
        except Exception as e:
            logger.error(f"Failed to pause/unpause schedule {schedule_id}: {e}")
            raise
    
    def delete_schedule(self, schedule_id: str) -> None:
        """
        Delete a schedule and all its runs.
        
        Args:
            schedule_id: ID of the schedule to delete
        """
        try:
            # Check if schedule exists
            schedule = self.db.get_schedule(schedule_id)
            if not schedule:
                raise ValueError(f"Schedule {schedule_id} not found")
            
            self.db.delete_schedule(schedule_id)
            logger.info(f"Schedule {schedule_id} deleted successfully")
            
        except Exception as e:
            logger.error(f"Failed to delete schedule {schedule_id}: {e}")
            raise
    
    def get_schedule(self, schedule_id: str) -> Optional[SchedulePreview]:
        """
        Get a schedule with preview of next fire times.
        
        Args:
            schedule_id: ID of the schedule to retrieve
            
        Returns:
            SchedulePreview object or None if not found
        """
        try:
            schedule = self.db.get_schedule(schedule_id)
            if not schedule:
                return None
            
            # Calculate next 5 fire times
            next_fire_times = self._calculate_next_fire_times(schedule, 5)
            
            return SchedulePreview(
                schedule=schedule,
                next_fire_times=next_fire_times
            )
            
        except Exception as e:
            logger.error(f"Failed to get schedule {schedule_id}: {e}")
            raise
    
    def list_schedules(
        self, 
        user_id: Optional[str] = None, 
        workflow_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Schedule]:
        """
        List schedules with optional filtering.
        
        Args:
            user_id: Filter by user ID
            workflow_id: Filter by workflow ID
            limit: Maximum number of schedules to return
            
        Returns:
            List of schedules
        """
        try:
            # This is a simplified implementation
            # In production, you'd want to add proper filtering to the database layer
            schedules = []
            
            # For now, we'll get all schedules and filter in memory
            # This should be optimized with proper database queries
            all_schedules = self._get_all_schedules()
            
            for schedule in all_schedules:
                if user_id and schedule.user_id != user_id:
                    continue
                if workflow_id and schedule.workflow_id != workflow_id:
                    continue
                
                schedules.append(schedule)
                if len(schedules) >= limit:
                    break
            
            return schedules
            
        except Exception as e:
            logger.error(f"Failed to list schedules: {e}")
            raise
    
    def _generate_schedule_id(self, input_data: ScheduleInput) -> str:
        """Generate a deterministic schedule ID."""
        # Create a deterministic ID based on workflow and user
        base_string = f"{input_data.workflow_id}:{input_data.user_id}:{input_data.cron_expr}"
        return f"schedule_{hash(base_string) % 1000000:06d}"
    
    def _calculate_next_fire_times(self, schedule: Schedule, count: int = 5) -> list[datetime]:
        """Calculate the next N fire times for a schedule."""
        try:
            times = []
            current_time = schedule.next_run_at
            
            for _ in range(count):
                if current_time:
                    times.append(current_time)
                    current_time = get_next_cron_time(
                        schedule.cron_expr, 
                        schedule.timezone, 
                        current_time
                    )
            
            return times
            
        except Exception as e:
            logger.error(f"Failed to calculate next fire times: {e}")
            return []
    
    def _get_all_schedules(self) -> list[Schedule]:
        """Get all schedules from the database."""
        # This is a placeholder - implement proper database query
        # For now, return empty list
        return []
