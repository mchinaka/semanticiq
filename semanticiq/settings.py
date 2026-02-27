import os
import environ
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse
env = environ.Env()
environ.Env.read_env()


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-not-for-prod')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'semanticiq.core',
    'semanticiq.tenant_admin',
    'django_recaptcha',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = 'semanticiq.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

WSGI_APPLICATION = 'semanticiq.wsgi.application'

ENV = os.getenv("DJANGO_ENV", "development").lower()

DATABASES = {
    'default': env.db('DATABASE_URL')
}

#DATABASES = {
    #"development": {
        #"ENGINE": "django.db.backends.postgresql",
        #"NAME": os.getenv("DEV_DB_NAME"),
        #"USER": os.getenv("DEV_DB_USER"),
        #"PASSWORD": os.getenv("DEV_DB_PASSWORD"),
        #"HOST": os.getenv("DEV_DB_HOST", "localhost"),
        #"PORT": os.getenv("DEV_DB_PORT", "5432"),
    #},
    #"testing": {
        #"ENGINE": "django.db.backends.postgresql",
        #"NAME": os.getenv("TEST_DB_NAME"),
        #"USER": os.getenv("TEST_DB_USER"),
        #"PASSWORD": os.getenv("TEST_DB_PASSWORD"),
        #"HOST": os.getenv("TEST_DB_HOST", "localhost"),
        #"PORT": os.getenv("TEST_DB_PORT", "5432"),
    #},
    #"production": {
        #"ENGINE": "django.db.backends.postgresql",
        #"NAME": os.getenv("PROD_DB_NAME"),
        #"USER": os.getenv("PROD_DB_USER"),
        #"PASSWORD": os.getenv("PROD_DB_PASSWORD"),
        #"HOST": os.getenv("PROD_DB_HOST", "localhost"),
        #"PORT": os.getenv("PROD_DB_PORT", "5432"),
#},
#}

#DATABASES["default"] = DATABASES[ENV]

#DATABASE_ROUTERS = ["semanticiq.core.db_router.EnvironmentRouter"]

DATABASE_URL = os.getenv('DATABASE_URL')
#if DATABASE_URL:
    #url = urlparse(DATABASE_URL)
    #DATABASES = {
        #'default': {
            #'ENGINE': 'django.db.backends.postgresql',
            #'NAME': url.path.lstrip('/'),
            #'USER': url.username,
            #'PASSWORD': url.password,
            #'HOST': url.hostname,
            #'PORT': url.port or '5432',
        #}
    #}
#else:
    #DATABASES = {
        #'default': {
            #'ENGINE': 'django.db.backends.sqlite3',
            #'NAME': BASE_DIR / 'db.sqlite3',
        #}
    #}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

RESOURCES_DIR = BASE_DIR / 'resources'

STATICFILES_DIRS = [
    BASE_DIR / "semanticiq/core/static",
]

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.postmarkapp.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("POSTMARK_API_KEY")
EMAIL_HOST_PASSWORD = os.getenv("POSTMARK_API_KEY")

DEFAULT_FROM_EMAIL = "malvern@semanticiq.co"

RECAPTCHA_PUBLIC_KEY = os.getenv("RECAPTCHA_PUBLIC_KEY")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error'] # Ignore recaptcha test key warning in development/testing environments




