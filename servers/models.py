from django.db import models

class Server(models.Model):
    server_id = models.IntegerField(unique=True)  # The server's unique ID
    server_name = models.CharField(max_length=255)  # Name of the server
    wipe_time = models.DateTimeField()  # Wipe time, will store the datetime
    max_group = models.IntegerField(null=True, blank=True)  # Max group size, can be null

    def __str__(self):
        return self.server_name if self.server_name else "Unnamed Server"
