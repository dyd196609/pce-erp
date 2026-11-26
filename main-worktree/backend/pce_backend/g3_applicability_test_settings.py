from .settings import *  # noqa: F401,F403


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
