#!/usr/bin/env python3
"""
Start both frontend and backend servers for Weave
"""

import subprocess
import time
import signal
import sys
import os
import threading
import queue
from datetime import datetime

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Backend colors (blue theme)
    BACKEND = "\033[94m"  # Blue
    BACKEND_BOLD = "\033[1;94m"  # Bold Blue
    
    # Frontend colors (green theme)
    FRONTEND = "\033[92m"  # Green
    FRONTEND_BOLD = "\033[1;92m"  # Bold Green
    
    # Status colors
    SUCCESS = "\033[92m"  # Green
    WARNING = "\033[93m"  # Yellow
    ERROR = "\033[91m"    # Red
    INFO = "\033[96m"     # Cyan

def log_backend(message, level="INFO"):
    """Log backend messages with blue color and backend emoji"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = "🔧"
    color = Colors.BACKEND
    bold_color = Colors.BACKEND_BOLD
    
    if level == "ERROR":
        emoji = "❌"
        color = Colors.ERROR
    elif level == "WARNING":
        emoji = "⚠️"
        color = Colors.WARNING
    elif level == "SUCCESS":
        emoji = "✅"
        color = Colors.SUCCESS
    
    print(f"{color}{emoji} BACKEND [{timestamp}] {message}{Colors.RESET}")

def log_frontend(message, level="INFO"):
    """Log frontend messages with green color and frontend emoji"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = "🎨"
    color = Colors.FRONTEND
    bold_color = Colors.FRONTEND_BOLD
    
    if level == "ERROR":
        emoji = "❌"
        color = Colors.ERROR
    elif level == "WARNING":
        emoji = "⚠️"
        color = Colors.WARNING
    elif level == "SUCCESS":
        emoji = "✅"
        color = Colors.SUCCESS
    
    print(f"{color}{emoji} FRONTEND [{timestamp}] {message}{Colors.RESET}")

def log_system(message, level="INFO"):
    """Log system messages with neutral color"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = "🌟"
    color = Colors.INFO
    
    if level == "ERROR":
        emoji = "💥"
        color = Colors.ERROR
    elif level == "WARNING":
        emoji = "⚠️"
        color = Colors.WARNING
    elif level == "SUCCESS":
        emoji = "🎉"
        color = Colors.SUCCESS
    
    print(f"{color}{emoji} SYSTEM [{timestamp}] {message}{Colors.RESET}")

def stream_logs(process, process_name, log_func):
    """Stream logs from a subprocess in real-time"""
    try:
        while True:
            # Read stdout line by line
            output = process.stdout.readline()
            if output:
                # Decode bytes to string
                line = output.decode('utf-8').strip()
                if line:
                    log_func(line)
            
            # Check if process has ended
            if process.poll() is not None:
                break
                
    except Exception as e:
        log_func(f"Error reading logs: {e}", "ERROR")

def start_backend():
    """Start the backend API server"""
    log_system("Starting Backend API...", "INFO")
    
    # Load environment variables from .env file
    env_vars = os.environ.copy()
    env_vars["PYTHONPATH"] = os.getcwd()
    
    # Try to load .env file if python-dotenv is available
    try:
        from dotenv import load_dotenv
        env_file = os.path.join(os.getcwd(), '.env')
        if os.path.exists(env_file):
            load_dotenv(env_file)
            log_system("✅ Loaded .env file", "SUCCESS")
        else:
            log_system("⚠️  .env file not found", "WARNING")
    except ImportError:
        log_system("⚠️  python-dotenv not available", "WARNING")
    except Exception as e:
        log_system(f"⚠️  Error loading .env: {e}", "WARNING")
    
    # Use unbuffered output for real-time logging
    backend_process = subprocess.Popen(
        ["python", "-u", "api/run.py"],
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Redirect stderr to stdout
        bufsize=1,
        env=env_vars
    )
    
    # Start log streaming in a separate thread
    backend_log_thread = threading.Thread(
        target=stream_logs,
        args=(backend_process, "Backend", log_backend),
        daemon=True
    )
    backend_log_thread.start()
    
    return backend_process, backend_log_thread

def start_frontend():
    """Start the frontend UI server"""
    log_system("Starting Frontend UI...", "INFO")
    
    # Use unbuffered output for real-time logging
    frontend_process = subprocess.Popen(
        ["python", "-u", "run.py"],
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Redirect stderr to stdout
        bufsize=1
    )
    
    # Start log streaming in a separate thread
    frontend_log_thread = threading.Thread(
        target=stream_logs,
        args=(frontend_process, "Frontend", log_frontend),
        daemon=True
    )
    frontend_log_thread.start()
    
    return frontend_process, frontend_log_thread

def main():
    log_system("Starting Weave - Workflow Automation Engine", "SUCCESS")
    print("=" * 70)
    
    # Show current working directory and environment status
    log_system(f"Working directory: {os.getcwd()}", "INFO")
    log_system(f"Python path: {os.environ.get('PYTHONPATH', 'Not set')}", "INFO")
    
    # Check if .env file exists
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        log_system(f"✅ .env file found at: {env_file}", "SUCCESS")
    else:
        log_system(f"⚠️  .env file not found at: {env_file}", "WARNING")
    
    # Start backend first
    backend_process, backend_log_thread = start_backend()
    log_system(f"Backend started (PID: {backend_process.pid})", "SUCCESS")
    
    # Wait a moment for backend to start
    time.sleep(3)
    
    # Start frontend
    frontend_process, frontend_log_thread = start_frontend()
    log_system(f"Frontend started (PID: {frontend_process.pid})", "SUCCESS")
    
    print("\n" + "=" * 70)
    log_system("Both servers are running!", "SUCCESS")
    log_system("Frontend: http://localhost:8000", "INFO")
    log_system("Backend:  http://localhost:8001", "INFO")
    log_system("API Docs: http://localhost:8001/docs", "INFO")
    log_system("Press Ctrl+C to stop both servers", "WARNING")
    print("=" * 70)
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if backend_process.poll() is not None:
                log_system("Backend server stopped unexpectedly", "ERROR")
                break
                
            if frontend_process.poll() is not None:
                log_system("Frontend server stopped unexpectedly", "ERROR")
                break
                
    except KeyboardInterrupt:
        log_system("Shutting down servers...", "WARNING")
        
        # Stop backend
        if backend_process.poll() is None:
            backend_process.terminate()
            backend_process.wait()
            log_system("Backend stopped", "SUCCESS")
        
        # Stop frontend
        if frontend_process.poll() is None:
            frontend_process.terminate()
            frontend_process.wait()
            log_system("Frontend stopped", "SUCCESS")
        
        log_system("Goodbye!", "SUCCESS")

if __name__ == "__main__":
    main()
