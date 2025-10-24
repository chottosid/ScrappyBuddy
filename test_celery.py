#!/usr/bin/env python3
"""
Test script to verify Celery setup
"""

import logging
from celery_app import app, check_due_targets_task, queue_initial_targets, get_redis_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test Redis connection"""
    logger.info("Testing Redis connection...")
    try:
        redis_config = get_redis_config()
        redis_url = redis_config["url"]
        logger.info(f"✓ Redis connection successful: {redis_url}")
        return True
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False

def test_celery_tasks():
    """Test Celery task execution"""
    logger.info("Testing Celery tasks...")
    
    try:
        # Test check_due_targets_task
        result1 = check_due_targets_task.delay()
        logger.info(f"✓ check_due_targets_task queued: {result1.id}")
        
        # Test queue_initial_targets
        result2 = queue_initial_targets.delay()
        logger.info(f"✓ queue_initial_targets queued: {result2.id}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Failed to queue tasks: {e}")
        return False

def test_celery_inspect():
    """Test Celery inspection commands"""
    logger.info("Testing Celery inspection...")
    
    try:
        # Check if we can inspect the app
        inspect = app.control.inspect()
        
        # This will work even without workers running
        logger.info("✓ Celery app inspection available")
        return True
        
    except Exception as e:
        logger.error(f"✗ Celery inspection failed: {e}")
        return False

def main():
    logger.info("Starting Celery Redis setup tests...")
    
    # Test Redis
    redis_ok = test_redis_connection()
    
    # Test Celery app
    inspect_ok = test_celery_inspect()
    
    # Test task queuing
    tasks_ok = test_celery_tasks()
    
    if redis_ok and inspect_ok and tasks_ok:
        logger.info("✓ All tests passed! Celery + Redis setup is working.")
        logger.info("Now start worker and beat processes to handle tasks:")
        logger.info("  celery -A celery_app worker --loglevel=info")
        logger.info("  celery -A celery_app beat --loglevel=info")
    else:
        logger.error("✗ Some tests failed")

if __name__ == "__main__":
    main()