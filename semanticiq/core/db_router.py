import os

class EnvironmentRouter:
    """
    Routes reads/writes to the environment-specific DB,
    but always allows migrations on the 'default' DB.
    """

    def _get_env_db(self):
        # DJANGO_ENV = development, testing, staging, production
        return os.getenv("DJANGO_ENV", "development").lower()

    def db_for_read(self, model, **hints):
        # Route reads to the environment DB
        return "default"

    def db_for_write(self, model, **hints):
        # Route writes to the environment DB
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        # Relations allowed within the same DB
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Always run migrations on the default DB
        return db == "default"