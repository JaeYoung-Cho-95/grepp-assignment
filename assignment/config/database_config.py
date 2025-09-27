import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "assignment_db"),
        "USER": os.environ.get("POSTGRES_USER", "master"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "1234"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": int(os.environ.get("POSTGRES_PORT", "5432")),
        "CONN_MAX_AGE": 600,
    }
}