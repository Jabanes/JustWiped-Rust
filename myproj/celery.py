# celery.py
import os
from celery import Celery

# Set the Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproj.settings')

app = Celery('myproj')

# Load Django settings into Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks in all registered Django app configs
app.autodiscover_tasks()

