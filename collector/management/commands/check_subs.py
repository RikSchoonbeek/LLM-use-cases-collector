from django.core.management.base import BaseCommand
from django.db.models import Prefetch

from collector.models import Comment, Submission
from collector.services import CheckSubmissionForInformationService

class Command(BaseCommand):
    help = 'Checks subscription status'

    def handle(self, *args, **options):
        submissions = Submission.objects.prefetch_related(
            Prefetch(
                'comments',
                queryset=Comment.objects.order_by('tree_id', 'lft')
            )
        ).all()
        CheckSubmissionForInformationService()(submissions=submissions)
