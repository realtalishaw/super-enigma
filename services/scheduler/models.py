"""
Data models for the Cron Scheduler service.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
import re


class Schedule(BaseModel):
    """Schedule model for cron-based workflow execution."""
    
    schedule_id: str = Field(..., description="Unique identifier for the schedule")
    workflow_id: str = Field(..., description="ID of the workflow to execute")
    version: int = Field(..., description="Version of the workflow")
    user_id: str = Field(..., description="ID of the user who owns the schedule")
    cron_expr: str = Field(..., description="Cron expression (5 or 6 field)")
    timezone: str = Field(..., description="IANA timezone identifier")
    start_at: Optional[datetime] = Field(None, description="When to start the schedule")
    end_at: Optional[datetime] = Field(None, description="When to end the schedule")
    next_run_at: datetime = Field(..., description="Next scheduled run time (UTC)")
    paused: bool = Field(False, description="Whether the schedule is paused")
    jitter_ms: int = Field(0, description="Random jitter in milliseconds")
    overlap_policy: str = Field("skip", description="Policy for handling overlapping runs")
    catchup_policy: str = Field("none", description="Policy for handling missed runs")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('cron_expr')
    def validate_cron_expr(cls, v):
        """Validate cron expression format."""
        # Basic validation for 5 or 6 field cron expressions
        parts = v.split()
        if len(parts) not in [5, 6]:
            raise ValueError("Cron expression must have 5 or 6 fields")
        
        # Validate field ranges
        field_ranges = [
            (0, 59),    # minute
            (0, 23),    # hour  
            (1, 31),    # day of month
            (1, 12),    # month
            (0, 7),     # day of week (0=Sunday, 7=Sunday)
        ]
        
        if len(parts) == 6:
            field_ranges.insert(0, (0, 59))  # second field
            
        for i, (part, (min_val, max_val)) in enumerate(zip(parts, field_ranges)):
            if part == '*' or part == '?':
                continue
            if '/' in part:
                base, step = part.split('/', 1)
                if base != '*' and not base.isdigit():
                    raise ValueError(f"Invalid base value in field {i}: {base}")
                if not step.isdigit() or int(step) <= 0:
                    raise ValueError(f"Invalid step value in field {i}: {step}")
            elif ',' in part:
                for val in part.split(','):
                    if not val.isdigit() or not (min_val <= int(val) <= max_val):
                        raise ValueError(f"Invalid value in field {i}: {val}")
            elif '-' in part:
                start, end = part.split('-', 1)
                if not start.isdigit() or not end.isdigit():
                    raise ValueError(f"Invalid range in field {i}: {part}")
                if not (min_val <= int(start) <= int(end) <= max_val):
                    raise ValueError(f"Invalid range in field {i}: {part}")
            elif not part.isdigit() or not (min_val <= int(part) <= max_val):
                raise ValueError(f"Invalid value in field {i}: {part}")
        
        return v
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate IANA timezone identifier."""
        # Basic validation - in production you might want to use pytz or zoneinfo
        if not re.match(r'^[A-Za-z_]+/[A-Za-z_]+$', v):
            raise ValueError("Invalid timezone format. Use IANA format like 'America/New_York'")
        return v
    
    @validator('overlap_policy')
    def validate_overlap_policy(cls, v):
        """Validate overlap policy."""
        if v not in ['allow', 'skip', 'queue']:
            raise ValueError("Overlap policy must be one of: allow, skip, queue")
        return v
    
    @validator('catchup_policy')
    def validate_catchup_policy(cls, v):
        """Validate catchup policy."""
        if v not in ['none', 'fire_immediately', 'spread']:
            raise ValueError("Catchup policy must be one of: none, fire_immediately, spread")
        return v


class ScheduleRun(BaseModel):
    """Schedule run execution record."""
    
    idempotency_key: str = Field(..., description="Unique idempotency key")
    schedule_id: str = Field(..., description="ID of the schedule that triggered this run")
    run_at: datetime = Field(..., description="Planned execution time")
    status: str = Field(..., description="Status of the run")
    run_id: Optional[str] = Field(None, description="ID assigned by the executor")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('status')
    def validate_status(cls, v):
        """Validate run status."""
        if v not in ['ENQUEUED', 'STARTED', 'SUCCESS', 'FAILED', 'SKIPPED']:
            raise ValueError("Status must be one of: ENQUEUED, STARTED, SUCCESS, FAILED, SKIPPED")
        return v


class ScheduleInput(BaseModel):
    """Input model for creating/updating schedules."""
    
    schedule_id: Optional[str] = Field(None, description="Optional schedule ID for updates")
    workflow_id: str = Field(..., description="ID of the workflow to execute")
    version: int = Field(..., description="Version of the workflow")
    user_id: str = Field(..., description="ID of the user who owns the schedule")
    cron_expr: str = Field(..., description="Cron expression")
    timezone: str = Field(..., description="IANA timezone identifier")
    start_at: Optional[datetime] = Field(None, description="When to start the schedule")
    end_at: Optional[datetime] = Field(None, description="When to end the schedule")
    jitter_ms: Optional[int] = Field(0, description="Random jitter in milliseconds")
    overlap_policy: Optional[str] = Field("skip", description="Policy for handling overlapping runs")
    catchup_policy: Optional[str] = Field("none", description="Policy for handling missed runs")


class SchedulePreview(BaseModel):
    """Schedule preview with next fire times."""
    
    schedule: Schedule
    next_fire_times: List[datetime] = Field(..., description="Next 5 fire times")
