"""Reusable isolated test DB only; never connects the default business database."""
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
test_dir = root / "work/do4-isolated"
test_dir.mkdir(parents=True, exist_ok=True)
os.environ["PCE_DATABASE_PATH"] = str(test_dir / "unused-default.sqlite3")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")
sys.path.insert(0, str(root / "backend"))
import django
django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner

settings.DATABASES["default"]["TEST"]["NAME"] = str(test_dir / "tests.sqlite3")
runner = DiscoverRunner(verbosity=2, keepdb=True, interactive=False)
raise SystemExit(bool(runner.run_tests(sys.argv[1:] or ["sales", "planning"])))
