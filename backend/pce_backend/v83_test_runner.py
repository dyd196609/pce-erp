from django.test.runner import DiscoverRunner


class ExistingIsolatedDatabaseRunner(DiscoverRunner):
    """Run V83 tests only against a pre-copied isolated SQLite database."""

    def setup_databases(self, **kwargs):
        return None

    def teardown_databases(self, old_config, **kwargs):
        return None
