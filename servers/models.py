from django.db import models

class Server(models.Model):
    server_id = models.IntegerField(primary_key=True)  # Make this the primary key
    server_name = models.CharField(max_length=255)  # Name of the server
    wipe_time = models.DateTimeField()  # Wipe time, will store the datetime
    max_group = models.IntegerField(null=True, blank=True)  # Max group size, can be null

    class Meta:
        db_table = 'servers'  # This tells Django to use the 'servers' table name

    def __str__(self):
        return self.server_name if self.server_name else "Unnamed Server"
