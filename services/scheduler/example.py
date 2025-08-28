#!/usr/bin/env python3
"""
Example usage of the Cron Scheduler service.
"""

import time
import requests
import json
from datetime import datetime, timedelta

# Configuration
SCHEDULER_URL = "http://localhost:8003"


def wait_for_service():
    """Wait for the scheduler service to be ready."""
    print("Waiting for scheduler service to be ready...")
    
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{SCHEDULER_URL}/health", timeout=5)
            if response.status_code == 200:
                print("✓ Scheduler service is ready")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"Attempt {attempt + 1}/{max_attempts}: Service not ready, waiting...")
        time.sleep(2)
    
    print("✗ Service failed to start within timeout")
    return False


def start_worker():
    """Start the scheduler worker."""
    try:
        response = requests.post(f"{SCHEDULER_URL}/worker/start")
        if response.status_code == 200:
            print("✓ Worker started successfully")
            return True
        else:
            print(f"✗ Failed to start worker: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error starting worker: {e}")
        return False


def create_schedule(workflow_id, cron_expr, timezone="UTC"):
    """Create a new schedule."""
    schedule_data = {
        "workflow_id": workflow_id,
        "version": 1,
        "user_id": "example_user",
        "cron_expr": cron_expr,
        "timezone": timezone,
        "overlap_policy": "skip",
        "catchup_policy": "none",
        "jitter_ms": 1000
    }
    
    try:
        response = requests.post(
            f"{SCHEDULER_URL}/schedules/upsert",
            json=schedule_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Schedule created: {result['schedule_id']}")
            print(f"  Next run at: {result['next_run_at']}")
            return result['schedule_id']
        else:
            print(f"✗ Failed to create schedule: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"✗ Error creating schedule: {e}")
        return None


def list_schedules():
    """List all schedules."""
    try:
        response = requests.get(f"{SCHEDULER_URL}/schedules")
        if response.status_code == 200:
            schedules = response.json()['schedules']
            print(f"✓ Found {len(schedules)} schedules:")
            for schedule in schedules:
                print(f"  - {schedule['schedule_id']}: {schedule['cron_expr']} ({schedule['timezone']})")
            return schedules
        else:
            print(f"✗ Failed to list schedules: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"✗ Error listing schedules: {e}")
        return []


def get_schedule(schedule_id):
    """Get schedule details with next fire times."""
    try:
        response = requests.get(f"{SCHEDULER_URL}/schedules/{schedule_id}")
        if response.status_code == 200:
            schedule = response.json()
            print(f"✓ Schedule {schedule_id}:")
            print(f"  Workflow: {schedule['schedule']['workflow_id']} v{schedule['schedule']['version']}")
            print(f"  Cron: {schedule['schedule']['cron_expr']}")
            print(f"  Timezone: {schedule['schedule']['timezone']}")
            print(f"  Status: {'Paused' if schedule['schedule']['paused'] else 'Active'}")
            print(f"  Next fire times:")
            for i, fire_time in enumerate(schedule['next_fire_times'][:3]):
                print(f"    {i+1}. {fire_time}")
            return schedule
        else:
            print(f"✗ Failed to get schedule: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ Error getting schedule: {e}")
        return None


def pause_schedule(schedule_id, paused=True):
    """Pause or unpause a schedule."""
    try:
        response = requests.post(
            f"{SCHEDULER_URL}/schedules/{schedule_id}/pause",
            json={"paused": paused}
        )
        
        if response.status_code == 200:
            action = "paused" if paused else "unpaused"
            print(f"✓ Schedule {schedule_id} {action}")
            return True
        else:
            print(f"✗ Failed to pause/unpause schedule: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error pausing/unpausing schedule: {e}")
        return False


def get_worker_status():
    """Get the current worker status."""
    try:
        response = requests.get(f"{SCHEDULER_URL}/worker/status")
        if response.status_code == 200:
            status = response.json()
            print(f"✓ Worker status: {status['status']}")
            print(f"  Tick interval: {status['worker_status']['tick_ms']}ms")
            print(f"  Lookahead: {status['worker_status']['lookahead_ms']}ms")
            print(f"  Leader lock: {status['worker_status']['leader_lock']}")
            return status
        else:
            print(f"✗ Failed to get worker status: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ Error getting worker status: {e}")
        return None


def get_metrics():
    """Get scheduler metrics."""
    try:
        response = requests.get(f"{SCHEDULER_URL}/metrics")
        if response.status_code == 200:
            metrics = response.json()
            print("✓ Scheduler metrics:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")
            return metrics
        else:
            print(f"✗ Failed to get metrics: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ Error getting metrics: {e}")
        return None


def main():
    """Main example function."""
    print("=== Cron Scheduler Service Example ===\n")
    
    # Wait for service to be ready
    if not wait_for_service():
        return
    
    # Start the worker
    if not start_worker():
        return
    
    print("\n--- Creating Example Schedules ---")
    
    # Create a schedule that runs every minute
    schedule1_id = create_schedule(
        "example_workflow_1",
        "0 * * * * *",  # Every minute
        "UTC"
    )
    
    # Create a schedule that runs every 5 minutes
    schedule2_id = create_schedule(
        "example_workflow_2", 
        "0 */5 * * * *",  # Every 5 minutes
        "America/New_York"
    )
    
    # Create a schedule that runs daily at 9 AM
    schedule3_id = create_schedule(
        "daily_report_workflow",
        "0 0 9 * * *",  # Daily at 9 AM
        "UTC"
    )
    
    if not schedule1_id or not schedule2_id or not schedule3_id:
        print("Failed to create some schedules, exiting")
        return
    
    print("\n--- Listing All Schedules ---")
    list_schedules()
    
    print("\n--- Schedule Details ---")
    get_schedule(schedule1_id)
    print()
    get_schedule(schedule2_id)
    print()
    get_schedule(schedule3_id)
    
    print("\n--- Worker Status ---")
    get_worker_status()
    
    print("\n--- Metrics ---")
    get_metrics()
    
    print("\n--- Pausing a Schedule ---")
    pause_schedule(schedule1_id, paused=True)
    
    print("\n--- Updated Schedule Details ---")
    get_schedule(schedule1_id)
    
    print("\n--- Unpausing Schedule ---")
    pause_schedule(schedule1_id, paused=False)
    
    print("\n--- Final Schedule Details ---")
    get_schedule(schedule1_id)
    
    print("\n=== Example Complete ===")
    print("\nThe scheduler is now running with your example schedules.")
    print("You can:")
    print("  - Monitor the logs to see schedule executions")
    print("  - Use the API endpoints to manage schedules")
    print("  - Check the metrics endpoint for statistics")
    print("  - Stop the service with Ctrl+C")
    
    # Keep the service running
    try:
        while True:
            time.sleep(10)
            print("\n--- Checking Status ---")
            get_worker_status()
            get_metrics()
    except KeyboardInterrupt:
        print("\n\nShutting down...")


if __name__ == "__main__":
    main()
