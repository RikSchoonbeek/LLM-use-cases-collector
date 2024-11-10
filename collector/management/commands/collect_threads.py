from django.core.management.base import BaseCommand

from collector.use_cases import CollectThreadsUseCase

class Command(BaseCommand):
    help = "Collects and processes threads from the database"

    def handle(self, *args, **options):
        CollectThreadsUseCase()()
        self.stdout.write(self.style.SUCCESS('Successfully collected threads'))
