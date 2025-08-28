"""
Utility functions for cron expression handling and timezone-aware scheduling.
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def generate_idempotency_key(schedule_id: str, run_at: datetime) -> str:
    """Generate idempotency key for a schedule run."""
    # Convert to epoch seconds for consistency
    epoch_seconds = int(run_at.timestamp())
    key_string = f"{schedule_id}:{epoch_seconds}"
    return hashlib.sha256(key_string.encode()).hexdigest()


def apply_jitter(run_at: datetime, jitter_ms: int) -> datetime:
    """Apply random jitter to a run time."""
    if jitter_ms <= 0:
        return run_at
    
    # Random offset between -jitter_ms and +jitter_ms
    jitter_seconds = random.uniform(-jitter_ms / 1000, jitter_ms / 1000)
    return run_at + timedelta(seconds=jitter_seconds)


def enumerate_due_times(
    cron_expr: str, 
    timezone: str, 
    next_run_at: datetime, 
    now: datetime, 
    lookahead_ms: int,
    catchup_policy: str = "none"
) -> List[datetime]:
    """
    Enumerate all due times for a schedule within the lookahead window.
    
    This is a simplified implementation. In production, you'd want to use
    a proper cron library like croniter with timezone support.
    """
    try:
        # For now, we'll use a simple approach
        # In production, replace this with proper cron parsing
        times = []
        current_time = next_run_at
        horizon = now + timedelta(milliseconds=lookahead_ms)
        
        # Simple cron parsing - this is a placeholder
        # You should use croniter or similar for production
        while current_time <= horizon:
            if current_time >= now or catchup_policy != "none":
                times.append(current_time)
            
            # Calculate next time based on cron expression
            # This is simplified - replace with proper cron logic
            current_time = _get_next_cron_time(cron_expr, current_time)
            
            # Safety check to prevent infinite loops
            if len(times) > 1000:
                logger.warning(f"Too many cron times generated for {cron_expr}, stopping")
                break
        
        # Apply catchup policy
        if catchup_policy == "none":
            times = [t for t in times if t >= now]
        elif catchup_policy == "spread":
            times = _spread_catchup_times(times, now, horizon)
        
        return times
        
    except Exception as e:
        logger.error(f"Error enumerating due times: {e}")
        return []


def _get_next_cron_time(cron_expr: str, current_time: datetime) -> datetime:
    """
    Get the next time based on cron expression.
    
    This is a simplified implementation. In production, use croniter or similar.
    """
    # Parse cron expression (simplified)
    parts = cron_expr.split()
    
    # For now, just add 1 minute as a placeholder
    # This should be replaced with proper cron logic
    return current_time + timedelta(minutes=1)


def _spread_catchup_times(
    times: List[datetime], 
    now: datetime, 
    horizon: datetime
) -> List[datetime]:
    """Spread catchup times across the lookahead window."""
    if not times:
        return times
    
    # Filter out future times
    past_times = [t for t in times if t < now]
    future_times = [t for t in times if t >= now]
    
    if not past_times:
        return future_times
    
    # Spread past times across the window
    window_duration = horizon - now
    if window_duration.total_seconds() <= 0:
        return future_times
    
    spread_times = []
    interval = window_duration / (len(past_times) + 1)
    
    for i, _ in enumerate(past_times):
        spread_time = now + (interval * (i + 1))
        spread_times.append(spread_time)
    
    return spread_times + future_times


def get_next_cron_time(cron_expr: str, timezone: str, after_time: datetime) -> datetime:
    """
    Get the next cron time after a given time.
    
    This is a simplified implementation. In production, use croniter with timezone support.
    """
    try:
        # For now, return a placeholder
        # In production, this should use proper cron parsing
        return after_time + timedelta(minutes=1)
        
    except Exception as e:
        logger.error(f"Error calculating next cron time: {e}")
        # Fallback to adding 1 minute
        return after_time + timedelta(minutes=1)


def validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression format."""
    try:
        parts = cron_expr.split()
        if len(parts) not in [5, 6]:
            return False
        
        # Basic validation - check if parts contain valid characters
        valid_chars = set('0123456789*/,-?')
        for part in parts:
            if not all(c in valid_chars for c in part):
                return False
        
        return True
        
    except Exception:
        return False


def validate_timezone(timezone: str) -> bool:
    """Validate timezone format."""
    import re
    # Basic IANA timezone format validation
    pattern = r'^[A-Za-z_]+/[A-Za-z_]+$'
    return bool(re.match(pattern, timezone))
