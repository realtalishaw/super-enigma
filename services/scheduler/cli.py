#!/usr/bin/env python3
"""
Interactive command-line interface for the Cron Scheduler service.
"""

import requests
import json
import sys
import cmd
import shlex
from datetime import datetime
from typing import Optional

# Configuration
DEFAULT_SCHEDULER_URL = "http://localhost:8003"


def make_request(method: str, endpoint: str, data: Optional[dict] = None, base_url: str = DEFAULT_SCHEDULER_URL):
    """Make an HTTP request to the scheduler service."""
    url = f"{base_url}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            print(f"Unsupported HTTP method: {method}")
            return None
        
        return response
        
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to scheduler service at {base_url}")
        print("Make sure the service is running and accessible.")
        return None
    except requests.exceptions.Timeout:
        print("Error: Request timed out")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def format_json(data):
    """Format JSON data for display."""
    return json.dumps(data, indent=2, default=str)


class SchedulerCLI(cmd.Cmd):
    """Interactive CLI for the Cron Scheduler service."""
    
    intro = """
╔══════════════════════════════════════════════════════════════╗
║                 Cron Scheduler Service CLI                   ║
║                                                              ║
║  Type 'help' to see available commands                      ║
║  Type 'quit' or 'exit' to exit                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    prompt = 'scheduler> '
    
    def __init__(self):
        super().__init__()
        self.base_url = DEFAULT_SCHEDULER_URL
    
    def do_url(self, arg):
        """Set the scheduler service URL: url <new_url>"""
        if arg:
            self.base_url = arg.strip()
            print(f"Service URL set to: {self.base_url}")
        else:
            print(f"Current service URL: {self.base_url}")
    
    def do_health(self, arg):
        """Check service health"""
        response = make_request("GET", "/health", base_url=self.base_url)
        if response and response.status_code == 200:
            print("✓ Service is healthy")
            print(format_json(response.json()))
        else:
            print("✗ Service is unhealthy")
    
    def do_status(self, arg):
        """Get worker status"""
        response = make_request("GET", "/worker/status", base_url=self.base_url)
        if response and response.status_code == 200:
            data = response.json()
            print(f"Worker Status: {data['status']}")
            print(format_json(data['worker_status']))
        else:
            print("✗ Failed to get worker status")
    
    def do_start_worker(self, arg):
        """Start the scheduler worker"""
        response = make_request("POST", "/worker/start", base_url=self.base_url)
        if response and response.status_code == 200:
            print("✓ Worker started successfully")
            print(format_json(response.json()))
        else:
            print("✗ Failed to start worker")
    
    def do_stop_worker(self, arg):
        """Stop the scheduler worker"""
        response = make_request("POST", "/worker/stop", base_url=self.base_url)
        if response and response.status_code == 200:
            print("✓ Worker stopped successfully")
            print(format_json(response.json()))
        else:
            print("✗ Failed to stop worker")
    
    def do_create_schedule(self, arg):
        """Create a new schedule: create_schedule <workflow_id> <user_id> <cron_expr> [timezone] [options]"""
        if not arg:
            print("Usage: create_schedule <workflow_id> <user_id> <cron_expr> [timezone] [options]")
            print("Example: create_schedule daily_report user123 '0 0 9 * * *' UTC")
            return
        
        try:
            parts = shlex.split(arg)
            if len(parts) < 3:
                print("Error: Need at least workflow_id, user_id, and cron_expr")
                return
            
            workflow_id = parts[0]
            user_id = parts[1]
            cron_expr = parts[2]
            timezone = parts[3] if len(parts) > 3 else "UTC"
            
            schedule_data = {
                "workflow_id": workflow_id,
                "version": 1,
                "user_id": user_id,
                "cron_expr": cron_expr,
                "timezone": timezone,
                "overlap_policy": "skip",
                "catchup_policy": "none",
                "jitter_ms": 0
            }
            
            response = make_request("POST", "/schedules/upsert", schedule_data, base_url=self.base_url)
            if response and response.status_code == 200:
                print("✓ Schedule created successfully")
                print(format_json(response.json()))
            else:
                print("✗ Failed to create schedule")
                if response:
                    print(f"Status: {response.status_code}")
                    print(f"Response: {response.text}")
                    
        except Exception as e:
            print(f"Error creating schedule: {e}")
    
    def do_get_schedule(self, arg):
        """Get schedule details: get_schedule <schedule_id>"""
        if not arg:
            print("Usage: get_schedule <schedule_id>")
            return
        
        schedule_id = arg.strip()
        response = make_request("GET", f"/schedules/{schedule_id}", base_url=self.base_url)
        if response and response.status_code == 200:
            data = response.json()
            print(f"Schedule: {schedule_id}")
            print(format_json(data))
        else:
            print(f"✗ Failed to get schedule {schedule_id}")
            if response:
                print(f"Status: {response.status_code}")
    
    def do_list_schedules(self, arg):
        """List all schedules: list_schedules [--user_id <user_id>] [--workflow_id <workflow_id>] [--limit <limit>]"""
        # Parse optional arguments
        user_id = None
        workflow_id = None
        limit = 100
        
        if arg:
            parts = shlex.split(arg)
            i = 0
            while i < len(parts):
                if parts[i] == "--user_id" and i + 1 < len(parts):
                    user_id = parts[i + 1]
                    i += 2
                elif parts[i] == "--workflow_id" and i + 1 < len(parts):
                    workflow_id = parts[i + 1]
                    i += 2
                elif parts[i] == "--limit" and i + 1 < len(parts):
                    limit = int(parts[i + 1])
                    i += 2
                else:
                    i += 1
        
        params = []
        if user_id:
            params.append(f"user_id={user_id}")
        if workflow_id:
            params.append(f"workflow_id={workflow_id}")
        if limit:
            params.append(f"limit={limit}")
        
        endpoint = "/schedules"
        if params:
            endpoint += "?" + "&".join(params)
        
        response = make_request("GET", endpoint, base_url=self.base_url)
        if response and response.status_code == 200:
            data = response.json()
            schedules = data.get('schedules', [])
            print(f"Found {len(schedules)} schedules:")
            for schedule in schedules:
                print(f"  {schedule['schedule_id']}: {schedule['cron_expr']} ({schedule['timezone']})")
        else:
            print("✗ Failed to list schedules")
            if response:
                print(f"Status: {response.status_code}")
    
    def do_pause_schedule(self, arg):
        """Pause or unpause a schedule: pause_schedule <schedule_id> [--unpause]"""
        if not arg:
            print("Usage: pause_schedule <schedule_id> [--unpause]")
            return
        
        parts = shlex.split(arg)
        schedule_id = parts[0]
        paused = "--unpause" not in parts
        
        data = {"paused": paused}
        action = "pause" if paused else "unpause"
        
        response = make_request("POST", f"/schedules/{schedule_id}/pause", data, base_url=self.base_url)
        if response and response.status_code == 200:
            print(f"✓ Schedule {schedule_id} {action}d successfully")
            print(format_json(response.json()))
        else:
            print(f"✗ Failed to {action} schedule {schedule_id}")
            if response:
                print(f"Status: {response.status_code}")
    
    def do_delete_schedule(self, arg):
        """Delete a schedule: delete_schedule <schedule_id>"""
        if not arg:
            print("Usage: delete_schedule <schedule_id>")
            return
        
        schedule_id = arg.strip()
        response = make_request("DELETE", f"/schedules/{schedule_id}", base_url=self.base_url)
        if response and response.status_code == 200:
            print(f"✓ Schedule {schedule_id} deleted successfully")
            print(format_json(response.json()))
        else:
            print(f"✗ Failed to delete schedule {schedule_id}")
            if response:
                print(f"Status: {response.status_code}")
    
    def do_get_runs(self, arg):
        """Get recent runs for a schedule: get_runs <schedule_id> [limit]"""
        if not arg:
            print("Usage: get_runs <schedule_id> [limit]")
            return
        
        parts = shlex.split(arg)
        schedule_id = parts[0]
        limit = int(parts[1]) if len(parts) > 1 else 10
        
        endpoint = f"/schedules/{schedule_id}/runs?limit={limit}"
        response = make_request("GET", endpoint, base_url=self.base_url)
        if response and response.status_code == 200:
            data = response.json()
            runs = data.get('runs', [])
            print(f"Recent runs for schedule {schedule_id}:")
            for run in runs:
                print(f"  {run['idempotency_key'][:8]}... - {run['status']} at {run['run_at']}")
        else:
            print(f"✗ Failed to get runs for schedule {schedule_id}")
            if response:
                print(f"Status: {response.status_code}")
    
    def do_metrics(self, arg):
        """Get service metrics"""
        response = make_request("GET", "/metrics", base_url=self.base_url)
        if response and response.status_code == 200:
            data = response.json()
            print("Service Metrics:")
            print(format_json(data))
        else:
            print("✗ Failed to get metrics")
            if response:
                print(f"Status: {response.status_code}")
    
    def do_start_workflow(self, arg):
        """Start a workflow execution: start_workflow <workflow_id> <version> <user_id> <scheduled_for> <idempotency_key>"""
        if not arg:
            print("Usage: start_workflow <workflow_id> <version> <user_id> <scheduled_for> <idempotency_key>")
            return
        
        try:
            parts = shlex.split(arg)
            if len(parts) < 5:
                print("Error: Need workflow_id, version, user_id, scheduled_for, and idempotency_key")
                return
            
            workflow_id = parts[0]
            version = parts[1]
            user_id = parts[2]
            scheduled_for = parts[3]
            idempotency_key = parts[4]
            
            endpoint = f"/run-launcher/start?workflow_id={workflow_id}&version={version}&user_id={user_id}&scheduled_for={scheduled_for}&idempotency_key={idempotency_key}"
            response = make_request("POST", endpoint, base_url=self.base_url)
            if response and response.status_code == 200:
                print("✓ Workflow started successfully")
                print(format_json(response.json()))
            else:
                print("✗ Failed to start workflow")
                if response:
                    print(f"Status: {response.status_code}")
                    print(f"Response: {response.text}")
                    
        except Exception as e:
            print(f"Error starting workflow: {e}")
    
    def do_clear(self, arg):
        """Clear the screen"""
        import os
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def do_quit(self, arg):
        """Exit the CLI"""
        print("Goodbye!")
        return True
    
    def do_exit(self, arg):
        """Exit the CLI"""
        return self.do_quit(arg)
    
    def do_EOF(self, arg):
        """Exit on EOF (Ctrl+D)"""
        return self.do_quit(arg)
    
    def default(self, line):
        """Handle unknown commands"""
        print(f"Unknown command: {line}")
        print("Type 'help' to see available commands")
    
    def emptyline(self):
        """Do nothing on empty line"""
        pass


def main():
    """Main entry point"""
    print("Starting Cron Scheduler Service CLI...")
    print(f"Default service URL: {DEFAULT_SCHEDULER_URL}")
    print("Use 'url <new_url>' to change the service URL")
    print()
    
    cli = SchedulerCLI()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
