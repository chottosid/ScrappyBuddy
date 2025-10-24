#!/usr/bin/env python3
"""
Content Monitoring System - Event-Driven Redis + Celery Setup
Main entry point for running the system
"""

import logging
import argparse
import threading
import time
import signal
import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _stream_subprocess_output(process: subprocess.Popen, name: str) -> None:
    """Forward subprocess stdout to logger on a background thread."""

    def _reader():
        try:
            for raw_line in iter(process.stdout.readline, ''):
                if not raw_line:
                    break
                logger.info("[%s] %s", name, raw_line.rstrip())
        except Exception as exc:  # safeguard logging thread
            logger.debug("Output reader for %s stopped: %s", name, exc)

    if process.stdout:
        threading.Thread(target=_reader, name=f"{name}-stdout", daemon=True).start()

# Global flag for graceful shutdown
shutdown_flag = threading.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received. Stopping all services...")
    shutdown_flag.set()

def start_api_server():
    """Start the FastAPI server in a thread"""
    import uvicorn
    from api import app
    
    logger.info("Starting API server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

def start_celery_worker():
    """Start Celery worker process"""
    logger.info("Starting Celery worker...")
    try:
        project_root = Path(__file__).resolve().parent
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{str(project_root)}{os.pathsep}{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = str(project_root)

        # Start Celery worker with solo pool for Windows
        worker_process = subprocess.Popen(
            'celery -A celery_app worker --loglevel=info --pool=solo',
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            cwd=str(project_root),
            env=env
        )
        
        # Give it time to start
        time.sleep(3)
        _stream_subprocess_output(worker_process, "celery-worker")
        
        if worker_process.poll() is not None:
            # Process died, get output
            try:
                stdout, _ = worker_process.communicate(timeout=5)
                logger.error(f"Celery worker failed to start: {stdout}")
            except subprocess.TimeoutExpired:
                logger.error("Celery worker failed to start (timeout getting output)")
            return None
            
        logger.info("Celery worker started successfully")
        return worker_process
        
    except Exception as e:
        logger.error(f"Failed to start Celery worker: {e}")
        return None

def start_celery_beat():
    """Start Celery beat scheduler"""
    logger.info("Starting Celery beat scheduler...")
    try:
        project_root = Path(__file__).resolve().parent
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{str(project_root)}{os.pathsep}{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = str(project_root)

        # Start Celery beat
        beat_process = subprocess.Popen(
            'celery -A celery_app beat --loglevel=info',
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            cwd=str(project_root),
            env=env
        )
        
        # Give it time to start
        time.sleep(3)
        _stream_subprocess_output(beat_process, "celery-beat")
        
        if beat_process.poll() is not None:
            # Process died, get output
            try:
                stdout, _ = beat_process.communicate(timeout=5)
                logger.error(f"Celery beat failed to start: {stdout}")
            except subprocess.TimeoutExpired:
                logger.error("Celery beat failed to start (timeout getting output)")
            return None
            
        logger.info("Celery beat started successfully")
        return beat_process
        
    except Exception as e:
        logger.error(f"Failed to start Celery beat: {e}")
        return None

def queue_initial_monitoring():
    """Queue initial monitoring tasks for all targets"""
    try:
        logger.info("Queuing initial monitoring tasks...")
        from celery_app import queue_initial_targets
        
        # Queue the initial targets task
        result = queue_initial_targets.delay()
        logger.info(f"Queued initial targets task: {result.id}")
        
    except Exception as e:
        logger.error(f"Failed to queue initial monitoring: {e}")

def start_monitoring_system():
    """Start the complete monitoring system with Celery"""
    logger.info("Starting Content Monitoring System...")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize database connection
    try:
        from database import db
        db.connect()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return
    
    # Start API server in a separate thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    logger.info("API server thread started")
    
    # Give API server time to start
    time.sleep(2)
    
    # Start Celery worker
    worker_process = start_celery_worker()
    if not worker_process:
        logger.error("Failed to start Celery worker. Exiting.")
        return
    
    # Start Celery beat scheduler
    beat_process = start_celery_beat()
    if not beat_process:
        logger.error("Failed to start Celery beat. Stopping worker and exiting.")
        if worker_process and worker_process.poll() is None:
            worker_process.terminate()
        return
    
    # Wait a bit for services to fully start
    time.sleep(5)
    
    # Queue initial monitoring tasks
    queue_initial_monitoring()
    
    # Keep main thread alive and monitor processes
    try:
        logger.info("All services started. Monitoring system is running...")
        
        while not shutdown_flag.is_set():
            # Check if processes are still running
            if worker_process.poll() is not None:
                logger.error("Celery worker died unexpectedly!")
                break
            
            if beat_process.poll() is not None:
                logger.error("Celery beat died unexpectedly!")
                break
            
            # Wait 30 seconds before next check
            shutdown_flag.wait(30)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Shutting down services...")
        
        # Terminate processes gracefully
        if worker_process and worker_process.poll() is None:
            logger.info("Stopping Celery worker...")
            worker_process.terminate()
            try:
                worker_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Force killing Celery worker...")
                worker_process.kill()
        
        if beat_process and beat_process.poll() is None:
            logger.info("Stopping Celery beat...")
            beat_process.terminate()
            try:
                beat_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Force killing Celery beat...")
                beat_process.kill()
        
        logger.info("Shutdown complete")

def run_single_monitoring_cycle():
    """Run a single monitoring cycle (for testing)"""
    try:
        logger.info("Running single monitoring cycle...")
        
        # Initialize database
        from database import db
        db.connect()
        
        # Create coordinator and run monitoring
        from agents.coordinator_agent import CoordinatorAgent
        coordinator = CoordinatorAgent()
        coordinator.run_monitoring_cycle()
        
        logger.info("Monitoring cycle completed")
        
    except Exception as e:
        logger.error(f"Monitoring cycle failed: {e}")
        raise
    finally:
        from database import db
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Content Monitoring System - Redis + Celery")
    parser.add_argument(
        "command",
        nargs='?',
        default="start",
        choices=["start", "monitor", "api", "worker", "beat", "test"],
        help="Command to run (default: start)"
    )
    
    args = parser.parse_args()
    
    if args.command == "start":
        start_monitoring_system()
    elif args.command == "monitor":
        run_single_monitoring_cycle()
    elif args.command == "api":
        start_api_server()
    elif args.command == "worker":
        # Start only Celery worker
        import os
        os.system('celery -A celery_app worker --loglevel=info --concurrency=4')
    elif args.command == "beat":
        # Start only Celery beat
        import os
        os.system('celery -A celery_app beat --loglevel=info')
    elif args.command == "test":
        # Test Celery setup
        import os
        os.system('python test_celery.py')

if __name__ == "__main__":
    main()