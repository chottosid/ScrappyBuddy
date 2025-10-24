from celery import Celery
import logging
from datetime import datetime, timedelta, timezone
import ssl
import sys
from pathlib import Path

# Ensure project root is on sys.path so worker subprocesses can import modules
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Create Celery app
app = Celery('monitoring_system')

def get_redis_config():
    """Resolve Redis connection details and ensure connectivity."""
    from config import Config

    redis_url = Config.REDIS_URL
    if not redis_url:
        raise ValueError("REDIS_URL not configured")

    try:
        import redis
    except ImportError as exc:
        logger.error("Redis client library is not installed: %s", exc)
        raise

    ssl_attempt_config = {
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_check_hostname': False,
    }

    def test_connection(url: str, ssl_options: dict | None):
        client_kwargs = ssl_options or {}
        client = redis.from_url(url, **client_kwargs)
        client.ping()

    attempts = []

    if redis_url.startswith('rediss://'):
        attempts.append((redis_url, ssl_attempt_config.copy()))
    else:
        # Always try the provided URL first
        attempts.append((redis_url, None))

        # If the provided URL is non-SSL, prepare a TLS fallback in case the
        # broker requires it (common with managed Redis services).
        if redis_url.startswith('redis://'):
            rediss_url = redis_url.replace('redis://', 'rediss://', 1)
            attempts.append((rediss_url, ssl_attempt_config.copy()))

    errors = []

    for attempt_url, ssl_options in attempts:
        try:
            test_connection(attempt_url, ssl_options)
            logger.debug("Successfully connected to Redis: %s", attempt_url)
            if attempt_url != redis_url:
                logger.debug("Redis connection fallback applied (%s)", attempt_url)
            return {
                "url": attempt_url,
                "ssl_options": ssl_options,
            }
        except Exception as err:
            errors.append(f"{attempt_url}: {err}")
            logger.warning("Failed to connect to Redis %s: %s", attempt_url, err)

    error_message = "; ".join(errors)
    logger.error("Could not establish Redis connection. Attempts: %s", error_message)
    raise ConnectionError(f"Unable to connect to Redis. Attempts: {error_message}")

# Resolve Redis configuration
redis_config = get_redis_config()
redis_url = redis_config["url"]
ssl_config = redis_config.get("ssl_options")

# Configure Celery
app.conf.update(
    # Broker and backend
    broker_url=redis_url,
    result_backend=redis_url,
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # SSL for Redis Cloud
    broker_use_ssl=ssl_config.copy() if ssl_config else None,
    redis_backend_use_ssl=ssl_config.copy() if ssl_config else None,
    
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    
    # Worker settings - Windows specific
    worker_pool='solo',  # Use solo pool for Windows
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    
    # Task execution settings
    task_always_eager=False,
    task_eager_propagates=True,
)

@app.task(bind=True, max_retries=3)
def monitor_target_task(self, target_url: str):
    """Celery task to monitor a single target using LangGraph workflow"""
    try:
        from database import db
        from workflows.monitoring_workflow import monitoring_workflow
        from config import Config

        logger.info(f"[TASK] Starting LangGraph monitoring for {target_url}")

        # Connect to database
        db.connect()

        # Get target from database
        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        target_data = targets_collection.find_one({"url": target_url, "active": True})

        if not target_data:
            logger.warning(f"[TASK] Target {target_url} not found or inactive")
            return {"status": "error", "message": f"Target {target_url} not found"}

        # Get previous content for comparison
        previous_content = target_data.get("last_content", "")

        # Prepare target data for workflow
        workflow_target_data = {
            "url": target_data["url"],
            "target_type": target_data["target_type"],
            "frequency_minutes": target_data.get("frequency_minutes", 60),
            "name": target_data.get("name")
        }

        # Run LangGraph workflow
        result = monitoring_workflow.run_monitoring_sync(workflow_target_data, previous_content)

        # Schedule next monitoring task
        next_run_time = datetime.now(timezone.utc) + timedelta(minutes=workflow_target_data["frequency_minutes"])
        monitor_target_task.apply_async(
            args=[target_url],
            eta=next_run_time
        )

        logger.info(f"[TASK] LangGraph monitoring completed for {target_url}: success={result['success']}")

        return {
            "status": "success" if result["success"] else "error",
            "target": target_url,
            "workflow_id": result.get("workflow_id"),
            "next_check": next_run_time.isoformat(),
            "changes_detected": len(result.get("changes_detected", [])),
            "error": result.get("error"),
            "step": result.get("step")
        }

    except Exception as e:
        logger.error(f"[TASK] Failed to monitor {target_url}: {e}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries  # 2, 4, 8 seconds
            logger.info(f"[TASK] Retrying {target_url} in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)

        return {"status": "error", "message": str(e), "target": target_url}

@app.task
def check_due_targets_task():
    """Celery task to check for targets that are due for monitoring"""
    try:
        from database import db
        from config import Config



        # Connect to database
        db.connect()

        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        current_time = datetime.now(timezone.utc)

        # Get all active targets
        all_targets = list(targets_collection.find({"active": True}))
        due_targets = []



        for target_data in all_targets:
            target_url = target_data.get('url')
            frequency_minutes = target_data.get('frequency_minutes', 60)
            last_checked = target_data.get('last_checked')

            # Check if target is due
            is_due = False

            if not last_checked:
                # Never checked
                is_due = True
            else:
                # Ensure timezone awareness
                if last_checked.tzinfo is None:
                    last_checked = last_checked.replace(tzinfo=timezone.utc)

                next_check_time = last_checked + timedelta(minutes=frequency_minutes)

                if current_time >= next_check_time:
                    is_due = True

            if is_due:
                due_targets.append(target_url)

        # Queue monitoring tasks for due targets
        queued_count = 0
        for target_url in due_targets:
            try:
                monitor_target_task.delay(target_url)
                queued_count += 1

            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to queue task for {target_url}: {e}")



        return {
            "status": "success",
            "total_targets": len(all_targets),
            "due_targets": len(due_targets),
            "queued_tasks": queued_count
        }

    except Exception as e:
        logger.error(f"[SCHEDULER] Failed to check due targets: {e}")
        return {"status": "error", "message": str(e)}

@app.task
def queue_initial_targets():
    """Queue all targets for immediate monitoring (used on startup)"""
    try:
        from database import db
        from config import Config



        # Connect to database
        db.connect()

        targets_collection = db.get_collection(Config.TARGETS_COLLECTION)
        all_targets = list(targets_collection.find({"active": True}))

        queued_count = 0
        for target_data in all_targets:
            target_url = target_data.get('url')
            try:
                # Queue with a small delay to spread the load
                monitor_target_task.apply_async(
                    args=[target_url],
                    countdown=queued_count * 2  # 0, 2, 4, 6 seconds delay
                )
                queued_count += 1

            except Exception as e:
                logger.error(f"[STARTUP] Failed to queue initial task for {target_url}: {e}")



        return {
            "status": "success",
            "queued_tasks": queued_count
        }

    except Exception as e:
        logger.error(f"[STARTUP] Failed to queue initial targets: {e}")
        return {"status": "error", "message": str(e)}

# Beat schedule - check for due targets every minute
app.conf.beat_schedule = {
    'check-due-targets': {
        'task': 'celery_app.check_due_targets_task',
        'schedule': 60.0,  # Every 60 seconds
    },
}

if __name__ == '__main__':
    app.start()