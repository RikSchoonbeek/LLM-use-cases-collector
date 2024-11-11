from celery import shared_task

from collector.services import CollectThreadsService


@shared_task
def collect_reddit_submissions():
    print("celery task 'collect_reddit_submissions' initiated\n")
    CollectThreadsService()()
    print("celery task 'collect_reddit_submissions' finished\n")
