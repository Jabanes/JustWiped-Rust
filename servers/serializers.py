from rest_framework import serializers
from .models import Server  # Import the Server model


class ServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server  # The model to serialize
        fields = ['server_id', 'server_name', 'wipe_time', 'max_group']  # The fields to include in the serialization

