import sys
import os

# Add parent directory to Python path to ensure 'app' module is found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tasks.sanctions_tasks import sync_un_sanctions_task

def trigger():
    print("🚀 Triggering UN Sanctions Sync Task manually...")
    try:
        # Send task to Celery worker
        task_un = sync_un_sanctions_task.delay()
        print(f"✅ UN Sanctions Task Dispatched Successfully! Task ID: {task_un.id}")

        from app.tasks.sanctions_tasks import sync_mex_sanctions_task
        task_mex = sync_mex_sanctions_task.delay()
        print(f"✅ Mexican Sanctions Task Dispatched Successfully! Task ID: {task_mex.id}")
        print("\nTo see the progress, check the worker logs:")
        print("docker-compose logs -f worker")
    except Exception as e:
        print(f"❌ Failed to dispatch task: {e}")
        print("Make sure Redis is running.")

if __name__ == "__main__":
    trigger()
