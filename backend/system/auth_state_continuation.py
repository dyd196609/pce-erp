"""Operator-only, same-identity encoded authentication preservation for upgrades.

No HTTP endpoint. Secrets remain in database/process memory, never in receipts,
request payloads, audit snapshots, command output or SQL debug logging.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from django.contrib.auth.hashers import identify_hasher, is_password_usable
from django.db import connection, transaction
from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from .models import User, OrganizationOperatingAuditRecord

ACTION = 'system.authentication_state.preserve_upgrade'
ACCOUNT = 'pce_emp_comp001_0002'
CONTRACT = 'PCE-AUTH-STATE-PRESERVATION-V1'


class AuthenticationContinuationError(ValueError):
    pass


def fail(code):
    raise AuthenticationContinuationError(code)


def open_source(path):
    c = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


def comparable_row(row):
    # Django's SQLite connection decodes timestamp columns; the read-only
    # source connection returns their stored ISO text. Compare identical
    # timestamps canonically, without excluding them from identity proof.
    result = {}
    for key, value in dict(row).items():
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif key.endswith('_at') and isinstance(value, str):
            value = value.replace(' ', 'T', 1)
        result[key] = value
    return result


def identity(c, username):
    users = c.execute('SELECT * FROM user_system WHERE username=?', (username,)).fetchall()
    if len(users) != 1:
        fail('ACCOUNT_IDENTITY_NOT_UNIQUE')
    user = comparable_row(users[0])
    companies = c.execute('SELECT * FROM system_company WHERE id=?', (user['company_id'],)).fetchall()
    employees = c.execute('SELECT * FROM employee WHERE user_id=?', (user['id'],)).fetchall()
    if len(companies) != 1 or len(employees) != 1:
        fail('COMPANY_EMPLOYEE_IDENTITY_NOT_UNIQUE')
    company, employee = comparable_row(companies[0]), comparable_row(employees[0])
    if not user['is_active'] or not company['is_active'] or employee['status'] != 'active':
        fail('ACCOUNT_COMPANY_EMPLOYEE_NOT_ACTIVE')
    stable = {'username': user['username'], 'companyCode': company['code'],
        'employeeNo': employee['employee_no'], 'accountCreatedAt': user['created_at'],
        'employeeCreatedAt': employee['created_at'], 'isActive': user['is_active'],
        'isStaff': user['is_staff'], 'isSuperuser': user['is_superuser'],
        'employeeStatus': employee['status'], 'departmentRefId': employee['department_ref_id'],
        'positionRefId': employee['position_ref_id']}
    # Preserve typed role/data scopes and linked employment facts. Stable
    # company/employee/account proof above is independent of numeric user IDs.
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    authority = {}
    for table in tables:
        if not (table.startswith('system_user_role') or table in ('user_system_groups', 'user_system_user_permissions')
                or 'user_organization_role_authority' in table
                or table.startswith(('pfm_', 'system_')) and ('assignment' in table or 'qualification' in table)):
            continue
        cols = {r[1] for r in c.execute('PRAGMA table_info("' + table + '")')}
        key, value = ('user_id', user['id']) if 'user_id' in cols else ('employee_id', employee['id'])
        if key not in cols:
            continue
        rows = [comparable_row(r) for r in c.execute('SELECT * FROM "' + table + '" WHERE "' + key + '"=?', (value,))]
        authority[table] = sorted(rows, key=lambda r: json.dumps(r, sort_keys=True, default=str))
    role_ids = {row['role_id'] for rows in authority.values() for row in rows if row.get('role_id')}
    for role_id in sorted(role_ids):
        for table, key in (('system_role', 'id'), ('system_rolepermission', 'role_id')):
            if table in tables:
                authority[table + ':' + str(role_id)] = [comparable_row(r) for r in c.execute(
                    'SELECT * FROM "' + table + '" WHERE "' + key + '"=? ORDER BY id', (role_id,))]
    for table in tables:
        if table.startswith('system_') and 'responsibility' in table:
            cols = {r[1] for r in c.execute('PRAGMA table_info("' + table + '")')}
            if 'position_id' in cols:
                authority[table] = [comparable_row(r) for r in c.execute('SELECT * FROM "' + table + '" WHERE position_id=? ORDER BY id', (employee['position_ref_id'],))]
    return user, stable, authority


def provenance(c, user, stable):
    result = []
    for pk in (13443, 13444):
        row = c.execute('SELECT * FROM system_organization_operating_audits WHERE id=?', (pk,)).fetchone()
        if row is None or row['action_code'] != 'UPDATE_USER' or row['target_type'] != 'User' or row['target_id'] != user['id'] or row['organization_id'] != user['company_id']:
            fail('MAINTENANCE_SOURCE_MISMATCH')
        before, after = json.loads(row['before_snapshot']), json.loads(row['after_snapshot'])
        for value in (before, after):
            if value.get('username') != stable['username'] or value.get('companyId') != user['company_id']:
                fail('MAINTENANCE_STABLE_IDENTITY_MISMATCH')
        result.append({'auditId': pk, 'passwordChanged': after.get('passwordChanged') is True,
            'sameCompanyAndAccount': True, 'employeeLinkMatches': after.get('employeeId') == c.execute('SELECT id FROM employee WHERE user_id=?', (user['id'],)).fetchone()[0]})
    if not any(r['passwordChanged'] for r in result) or not all(r['employeeLinkMatches'] for r in result):
        fail('MAINTENANCE_AUTHENTICATION_OR_EMPLOYEE_PROOF_MISSING')
    return result


def preserve(*, actor_id, source_database, expected_source_snapshot, username, idempotency_key, reason):
    target = Path(connection.settings_dict['NAME']).resolve()
    source, expected = Path(source_database).resolve(), Path(expected_source_snapshot).resolve()
    if username != ACCOUNT or source == target or expected == target or source == expected:
        fail('EXPLICIT_SINGLE_ACCOUNT_SCOPE_REQUIRED')
    if (Path(os.environ.get('PCE_AUTH_STATE_CONTINUATION_DATABASE', '')).resolve() != target
            or Path(os.environ.get('PCE_AUTH_STATE_CONTINUATION_SOURCE', '')).resolve() != source):
        fail('EXPLICIT_SOURCE_TARGET_BINDING_REQUIRED')
    if not idempotency_key or len(idempotency_key) > 160 or not reason or len(reason) > 300:
        fail('REQUEST_IDENTITY_AND_REASON_REQUIRED')
    with open_source(source) as src, open_source(expected) as frozen:
        current, stable, authorities = identity(src, username)
        original, original_stable, original_authorities = identity(frozen, username)
        if stable != original_stable or authorities != original_authorities or current['password'] != original['password']:
            fail('SOURCE_CHANGED_SINCE_APPROVED_SNAPSHOT')
        proofs = provenance(src, current, stable)
        try:
            hasher = identify_hasher(current['password'])
            hasher.decode(current['password'])
        except Exception:
            fail('AUTHENTICATION_ENCODING_NOT_SUPPORTED')
        if not is_password_usable(current['password']):
            fail('AUTHENTICATION_ENCODING_NOT_USABLE')
        snapshot_id = hashlib.sha256(expected.read_bytes()).hexdigest()
        metadata = {'contractVersion': CONTRACT, 'username': username, 'identity': stable,
            'sourceSnapshotSHA256': snapshot_id, 'sourceAuditIds': [r['auditId'] for r in proofs],
            'changedFields': ['password'], 'algorithm': hasher.algorithm,
            'writeIntent': 'controlled_authentication_upgrade', 'sessionsImported': False}
        digest = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            actor = User.objects.select_for_update().get(pk=actor_id)
            if not actor.is_active or not actor.is_superuser or actor.company_id != current['company_id']:
                fail('CURRENT_DATABASE_ADMINISTRATOR_REQUIRED')
            target_user = User.objects.select_for_update().get(username=username)
            # Use SQLite's parameterized native connection for the one secret
            # UPDATE, avoiding Django's rendered SQL debug query log entirely.
            raw = connection.connection
            old_factory = raw.row_factory
            raw.row_factory = sqlite3.Row
            try:
                previous, target_stable, target_authorities = identity(raw, username)
            finally:
                raw.row_factory = old_factory
            if target_stable != stable or target_authorities != authorities:
                fail('TARGET_IDENTITY_OR_AUTHORITY_MISMATCH')
            record = MasterDataWriteRequest.objects.filter(organization_id=actor.company_id,
                action_code=ACTION, idempotency_key=idempotency_key).first()
            if record and (record.request_hash != digest or record.status != 'COMMITTED' or record.target_entity_id != str(target_user.pk)):
                fail('IDEMPOTENCY_CONFLICT')
            if record and target_user.password != current['password']:
                fail('TARGET_AUTHENTICATION_CHANGED_AFTER_CONTINUATION')
            if target_user.password == current['password']:
                return {'contractVersion': CONTRACT, 'username': username, 'changedFields': [],
                    'authenticationFieldsChanged': 0, 'auditWrites': 0, 'supportWrites': 0,
                    'idempotent': True, 'identityPreserved': True, 'authorityPreserved': True,
                    'algorithm': hasher.algorithm, 'sessionsImported': False}
            identity_row, _ = ExternalIdentity.objects.get_or_create(organization_id=actor.company_id,
                source_system='PCE_CONTROLLED_UPGRADE', source_type='AUTH_STATE_PRESERVATION',
                source_object_type='User', external_id=username + ':' + snapshot_id,
                defaults={'target_entity_type': 'system.User', 'target_entity_id': str(target_user.pk),
                    'mapping_status': 'MATCH', 'source_fingerprint': snapshot_id, 'audit_metadata': metadata})
            count = raw.execute('UPDATE user_system SET password=? WHERE id=? AND password=?',
                (current['password'], target_user.pk, previous['password'])).rowcount
            if count != 1:
                fail('TARGET_AUTHENTICATION_CONCURRENT_CHANGE')
            # Re-read live source before committing; unrelated login timestamps
            # are not credential state and are never copied.
            with open_source(source) as fresh:
                latest, latest_stable, latest_authorities = identity(fresh, username)
                if latest['password'] != current['password'] or latest_stable != stable or latest_authorities != authorities:
                    fail('SOURCE_CHANGED_DURING_CONTINUATION')
            audit = OrganizationOperatingAuditRecord.objects.create(actor=actor, organization_id=actor.company_id,
                action_code=ACTION, target_type='User', target_id=target_user.pk, target_label=username, reason=reason,
                before_snapshot={'identity': stable, 'changedFields': ['password'], 'credentialValueDisclosed': False},
                after_snapshot={**metadata, 'encodedValuePreservedExactly': True, 'rolesOrScopesChanged': False})
            result = {'contractVersion': CONTRACT, 'username': username, 'changedFields': ['password'],
                'authenticationFieldsChanged': 1, 'auditWrites': 1, 'supportWrites': 2,
                'idempotent': False, 'identityPreserved': True, 'authorityPreserved': True,
                'algorithm': hasher.algorithm, 'sourceProofs': proofs, 'sessionsImported': False, 'auditId': audit.pk}
            MasterDataWriteRequest.objects.create(organization_id=actor.company_id, action_code=ACTION,
                entity_type='system.User', idempotency_key=idempotency_key, request_hash=digest,
                source_identity=identity_row, status='COMMITTED', target_entity_id=str(target_user.pk), result=result,
                audit_metadata=metadata)
            return result
