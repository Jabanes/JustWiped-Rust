from django.db import models
from django.core.management.base import BaseCommand
from datetime import datetime

class Server(models.Model):
    server_id = models.IntegerField(primary_key=True)  # Make this the primary key
    server_name = models.CharField(max_length=255)  # Name of the server
    max_group = models.IntegerField(null=True, blank=True)  # Max group size, can be null

    class Meta:
        db_table = 'servers'  # This tells Django to use the 'servers' table name

    def __str__(self):
        return self.server_name if self.server_name else "Unnamed Server"

    def update_database(self, servers_data):
        # Update existing wipe times to new format
        all_servers = Server.objects.all()
        for existing in all_servers:
            if isinstance(existing.wipe_time, datetime):
                existing.wipe_time = self.format_wipe_time(existing.wipe_time)
                existing.save()
                self.stdout.write(
                    self.style.SUCCESS(f"Updated wipe time format for: {existing.server_name} to {existing.wipe_time}")
                )

        # Rest of your update_database code...

class WipeSchedule(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='wipe_schedules')
    day_name = models.CharField(max_length=10)  # Monday, Tuesday, etc.
    wipe_hour = models.CharField(max_length=10)  # Store time like "4pm est"

    class Meta:
        db_table = 'wipe_schedules'
        unique_together = ['server', 'day_name', 'wipe_hour']  # Prevent exact duplicates

    def __str__(self):
        return f"{self.server.server_name} - {self.day_name} at {self.wipe_hour}"
