from django.core.management.base import BaseCommand

from collector.services import CollectThreadsService

class Command(BaseCommand):
    help = "Collects and processes threads from the database"

    def handle(self, *args, **options):
        CollectThreadsService()()
        self.stdout.write(self.style.SUCCESS('Successfully collected threads'))
