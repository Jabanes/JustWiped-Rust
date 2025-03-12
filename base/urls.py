from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView
from base import views

# Create a DefaultRouter instance

# Register the ServerViewSet with the router

# Include the router URLs
urlpatterns = [
    path('register',views.signUp),
    path('login', TokenObtainPairView.as_view()),  
]
