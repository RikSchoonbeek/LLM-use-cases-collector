from .base import *

# Database for containerized environment
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'develop',
        'USER': 'develop',
        'PASSWORD': 'develop',
        'HOST': 'db',
        'PORT': '5432',
    }
}

# Redis for containerized environment
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
