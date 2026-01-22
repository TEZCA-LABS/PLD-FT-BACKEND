import sys
import os

# Add current directory to Python path to ensure 'app' module is found
sys.path.append(os.getcwd())

from app.tasks.sanctions_tasks import sync_un_sanctions_task

def trigger():
    print("🚀 Triggering UN Sanctions Sync Task manually...")
    try:
        # Send task to Celery worker
        task = sync_un_sanctions_task.delay()
        print(f"✅ Task Dispatched Successfully!")
        print(f"🆔 Task ID: {task.id}")
        print("\nTo see the progress, check the worker logs:")
        print("docker-compose logs -f worker")
    except Exception as e:
        print(f"❌ Failed to dispatch task: {e}")
        print("Make sure Redis is running.")

if __name__ == "__main__":
    trigger()
