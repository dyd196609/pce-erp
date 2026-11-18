#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


EXPECTED_RUNTIME_PROFILE = 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE'
EXPECTED_DATABASE_IDENTITY = 'PDE-OPERABLE-ACCEPTANCE-20260912'
EXPECTED_DATABASE = Path(
    r'D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3'
).resolve()


def verify_runserver_contract():
    """Prevent an interactive server from silently creating/using db.sqlite3."""
    if len(sys.argv) < 2 or sys.argv[1] != 'runserver':
        return
    configured = os.environ.get('PCE_DATABASE_PATH', '').strip()
    if os.environ.get('PCE_ISOLATED_RUNSERVER_TEST') == '1' and configured:
        isolated_target = Path(configured).resolve()
        isolated_root = (Path(__file__).resolve().parents[1] / 'work').resolve()
        if (
            isolated_target.is_relative_to(isolated_root)
            and isolated_target.is_file()
            and isolated_target.name != 'db.sqlite3'
        ):
            return
    if (
        os.environ.get('PCE_RUNTIME_PROFILE', '').strip() != EXPECTED_RUNTIME_PROFILE
        or os.environ.get('PCE_DATABASE_IDENTITY', '').strip() != EXPECTED_DATABASE_IDENTITY
        or os.environ.get('PCE_NON_PRODUCTION_ACCEPTANCE') != '1'
        or os.environ.get('PCE_RUNTIME_LAUNCHER_VERIFIED') != '1'
        or not configured
        or Path(configured).resolve() != EXPECTED_DATABASE
        or not EXPECTED_DATABASE.is_file()
    ):
        raise SystemExit(
            'RUNSERVER_RUNTIME_CONTRACT_REQUIRED: use '
            'tools/Start-PceUnifiedDevelopment.ps1; default db.sqlite3 fallback is forbidden.'
        )


def main():
    """Run administrative tasks."""
    verify_runserver_contract()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pce_backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
