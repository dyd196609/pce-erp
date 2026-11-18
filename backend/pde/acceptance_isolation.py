"""Fail-closed acceptance target verification; no connection is opened here."""
import os
import hashlib
import json
from pathlib import Path


ACCEPTANCE_RUNTIME_PROFILE = 'PCE_UNIFIED_DEVELOPMENT_ACCEPTANCE'


def _verify_pinned_readonly_copy(target, identity, databases, env):
    """Opt-in physical pin for an explicitly authorized readonly delivery copy.

    The existing registered Acceptance target is unchanged. A work copy must
    have a content-addressed activation receipt and an OS-readonly DB factory.
    """
    receipt_path = env.get('PCE_ISOLATED_ACCEPTANCE_PIN', '').strip()
    expected = env.get('PCE_ISOLATED_ACCEPTANCE_PIN_SHA256', '').strip()
    if not receipt_path or not expected:
        return None
    raw = Path(receipt_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('ISOLATED_COPY_ACTIVATION_PIN_HASH_MISMATCH')
    pin = json.loads(raw)
    root = Path(__file__).resolve().parents[2] / 'work'
    if (pin.get('scope') != 'PDE_OEI_STATE_READONLY_DELIVERY' or pin.get('readOnly') is not True
            or pin.get('databaseIdentity') != identity or Path(pin.get('databasePath', '')).resolve() != target
            or not target.is_relative_to(root.resolve()) or not target.name.endswith('-acceptance.sqlite3')):
        raise ValueError('ISOLATED_COPY_ACTIVATION_SCOPE_MISMATCH')
    stat = target.stat()
    if (stat.st_dev, stat.st_ino, stat.st_size) != (pin.get('device'), pin.get('fileId'), pin.get('bytes')):
        raise ValueError('ISOLATED_COPY_PHYSICAL_IDENTITY_MISMATCH')
    if hashlib.sha256(target.read_bytes()).hexdigest() != pin.get('sha256'):
        raise ValueError('ISOLATED_COPY_CONTENT_CHANGED')
    for alias, config in databases.items():
        factory = config.get('OPTIONS', {}).get('factory')
        if (config.get('ENGINE') != 'django.db.backends.sqlite3'
                or Path(str(config.get('NAME', ''))).resolve() != target
                or getattr(factory, 'pce_permanent_readonly', False) is not True):
            raise ValueError('ISOLATED_COPY_PERMANENT_READONLY_REQUIRED:' + alias)
    return {'databaseIdentity': identity, 'databasePath': str(target), 'aliases': sorted(databases),
            'verified': True, 'readOnly': True, 'activationPinSha256': expected}


def verify_acceptance_connections(databases, environ=None):
    env = os.environ if environ is None else environ
    target_text = env.get('PCE_DATABASE_PATH', '').strip()
    identity = env.get('PCE_DATABASE_IDENTITY', '').strip()
    if env.get('PCE_NON_PRODUCTION_ACCEPTANCE') != '1' or not target_text or not identity:
        raise ValueError('ACCEPTANCE_ISOLATION_DECLARATION_REQUIRED')
    target = Path(target_text).resolve()
    if databases and 'default' in databases:
        pinned = _verify_pinned_readonly_copy(target, identity, databases, env)
        if pinned is not None:
            return pinned
    root = Path(__file__).resolve().parents[3] / 'Acceptance'
    if not target.is_relative_to(root.resolve()) or target.suffix != '.sqlite3' or target.name == 'db.sqlite3':
        raise ValueError('ACCEPTANCE_DATABASE_TARGET_FORBIDDEN')
    # An arbitrary database renamed into Acceptance is not an approved environment.
    # Extend this registry only for another explicitly authorized persistent target.
    approved = {'PDE-OPERABLE-ACCEPTANCE-20260912': root/'PDE-Operable-20260912/pde-operable-acceptance.sqlite3'}
    if identity not in approved or target != approved[identity].resolve():
        raise ValueError('ACCEPTANCE_DATABASE_IDENTITY_TARGET_MISMATCH')
    if not target.is_file():
        raise ValueError('ACCEPTANCE_DATABASE_MISSING')
    if not databases or 'default' not in databases:
        raise ValueError('ACCEPTANCE_CONNECTIONS_MISSING')
    for alias, config in databases.items():
        if config.get('ENGINE') != 'django.db.backends.sqlite3' or not config.get('NAME'):
            raise ValueError('ACCEPTANCE_CONNECTION_NOT_ISOLATED:' + alias)
        if Path(str(config['NAME'])).resolve() != target:
            raise ValueError('ACCEPTANCE_CONNECTION_TARGET_MISMATCH:' + alias)
    return {'databaseIdentity': identity, 'databasePath': str(target), 'aliases': sorted(databases), 'verified': True}


def verify_declared_acceptance_runtime(databases, environ=None):
    """Fail closed only when the process declares the protected acceptance profile."""
    env = os.environ if environ is None else environ
    if env.get('PCE_RUNTIME_PROFILE', '').strip() != ACCEPTANCE_RUNTIME_PROFILE:
        return {'declared': False, 'verified': False}
    return {
        'declared': True,
        **verify_acceptance_connections(databases, environ=env),
    }
