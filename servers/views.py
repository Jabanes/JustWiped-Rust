from servers.models import Server  # Import from servers.models, not base.models
from .serializers import ServerSerializer
from rest_framework import viewsets

class ServerViewSet(viewsets.ModelViewSet):
    queryset = Server.objects.all()  # Query all servers
    serializer_class = ServerSerializer  # Use the ServerSerializer