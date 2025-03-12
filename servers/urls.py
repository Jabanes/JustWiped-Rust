from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ServerViewSet
from rest_framework_simplejwt.views import TokenObtainPairView
from servers import views

# Create a DefaultRouter instance
router = DefaultRouter()

# Register the ServerViewSet with the router
router.register(r'servers', ServerViewSet)

# Include the router URLs
urlpatterns = [
    path('', include(router.urls)),  # Prefix the API paths with 'api/'
    
]
