from django.db import models


class TaskRun(models.Model):
    """
    Represents a celery task that was initiated at a given moment.
    """
    STATUS_CHOICES = [
        ('notstarted', 'Not Started'),
        ('started', 'Started'),
        ('finished', 'Finished'),
    ]
    RESULT_CHOICES = [
        ('error', 'Error'),
        ('pending', 'Pending'),
        ('success', 'Success'),
    ]

    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='not-started'
    )
    result = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField()
    error_traceback = models.TextField()
    created_dt = models.DateTimeField(auto_now_add=True)
    modified_dt = models.DateTimeField(auto_now=True)
    initiated_dt = models.DateTimeField(blank=True, null=True)
    stopped_dt = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True