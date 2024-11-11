from .base import *

# Database for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'develop',
        'USER': 'develop',
        'PASSWORD': 'develop',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Redis for local development
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
