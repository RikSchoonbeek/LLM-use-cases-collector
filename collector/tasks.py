import traceback

from celery import shared_task

from django.utils import timezone

from collector.models import CollectSubmissionTaskRun
from collector.services import CollectSubmissionsService


@shared_task(bind=True)
def collect_reddit_submissions(self):
    task_run = CollectSubmissionTaskRun.objects.create(
        celery_task_id=self.request.id,
        result="pending",
        status="started",
        initiated_dt=timezone.now(),
    )
    try:
        CollectSubmissionsService()()
    except Exception as e:
        # Get both error message and full traceback
        error_message = str(e)
        error_traceback = ''.join(traceback.format_tb(e.__traceback__))
        
        task_run.error_message = error_message
        task_run.error_traceback = error_traceback
        task_run.result = 'error'
    else:
        task_run.result = 'success'
    
    task_run.stopped_dt = timezone.now()
    task_run.save()
