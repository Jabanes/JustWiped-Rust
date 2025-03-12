from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from datetime import timedelta

class Command(BaseCommand):
    help = 'Sets up the periodic task for scraping servers'

    def handle(self, *args, **kwargs):
        # Create a schedule every 1 hour
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=15, period=IntervalSchedule.MINUTES
        )

        # Create the periodic task
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name="Scrape Server Data",
            task="servers.tasks.scrape_and_store_server_data"
        )

        self.stdout.write(self.style.SUCCESS('Periodic task setup successfully!'))
