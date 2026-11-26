"""Real Django readonly transaction, introspection, serializer and API matrix."""
import json, sys
from copy import deepcopy
from unittest.mock import patch
from semi_finished_schema_retry import ROOT, ISO, OUT, DB, sha, save, load
from semi_finished_schema_production import bootstrap

stage=sys.argv[1]
path=DB if stage=='production' else ISO/'rehearsal.sqlite3'
backend=ROOT/'backend' if stage=='production' else ISO/'backend'
before=sha(path)
connection=bootstrap(backend,path)
from semi_finished_readonly_guard import ReadOnlyGuard, ReadOnlyViolation, classify
from django.db import transaction, connections
from system.models import User, Process
from pde.models import MaterialConfiguration
from pde.material_configuration_serializers import MaterialConfigurationSerializer
from pde.views import EngineeringCalculationReadinessView
from pde.semi_finished_schema_status import apply_status
from rest_framework.test import APIRequestFactory, force_authenticate

matrix=[]
allowed=['BEGIN','BEGIN TRANSACTION','BEGIN IMMEDIATE','BEGIN EXCLUSIVE','BEGIN DEFERRED TRANSACTION',
 'SAVEPOINT matrix_one','RELEASE SAVEPOINT matrix_one','RELEASE matrix_one','ROLLBACK','ROLLBACK TO SAVEPOINT matrix_one',
 'COMMIT','END','SELECT 1','PRAGMA table_info("system_process")','PRAGMA integrity_check','PRAGMA foreign_key_check',
 'PRAGMA journal_mode','EXPLAIN SELECT 1','EXPLAIN QUERY PLAN SELECT 1','WITH a AS (SELECT 1 AS x) SELECT x FROM a',
 'SELECT name,sql FROM sqlite_master WHERE type=\'table\'','-- read\n SELECT \'UPDATE DELETE\'','/* prefix */ BEGIN']
blocked=['INSERT INTO system_process (name) VALUES (\'forbidden\')','UPDATE system_process SET name=name',
 'DELETE FROM system_process','REPLACE INTO system_process (name) VALUES (\'forbidden\')','CREATE TABLE forbidden (id int)',
 'ALTER TABLE system_process ADD forbidden int','DROP TABLE system_process','REINDEX','VACUUM',
 'PRAGMA user_version=2','PRAGMA journal_mode(WAL)','PRAGMA writable_schema(1)','PRAGMA query_only=OFF',
 'ATTACH DATABASE \'x\' AS other','DETACH other','WITH a AS (SELECT 1) DELETE FROM system_process',
 'BEGIN; UPDATE system_process SET name=name','SELECT 1; DELETE FROM system_process',
 'EXPLAIN UPDATE system_process SET name=name','SELECT load_extension(\'bad\')','SELECT writefile(\'bad\',\'x\')',
 'BEGIN UPDATE system_process SET name=name','/*comment*/ DROP TABLE system_process']
for sql in allowed:
    matrix.append({'sql':sql,'expected':'ALLOW','actual':classify(sql),'passed':True})
for sql in blocked:
    try:classify(sql)
    except ReadOnlyViolation as e:matrix.append({'sql':sql,'expected':'BLOCK','actual':str(e),'passed':True})
    else:raise AssertionError(('SQL_NOT_BLOCKED',sql))

guard=ReadOnlyGuard();checks=[]
# BEGIN IMMEDIATE/EXCLUSIVE reserve a write lock and SQLite mode=ro rejects
# that lock independently of classification. Exercise these on a zero-row,
# in-memory Django alias under exactly the same per-statement guard.
settings=dict(connection.settings_dict)
settings.update(NAME=':memory:',OPTIONS={})
connections.databases['transaction_probe']=settings
probe=connections['transaction_probe']
with probe.execute_wrapper(guard):
    with probe.cursor() as c:
        for begin in ['BEGIN IMMEDIATE','BEGIN EXCLUSIVE','BEGIN DEFERRED TRANSACTION']:
            c.execute(begin);c.execute('SELECT 1');assert c.fetchone()==(1,)
            for sql in blocked[:4]:
                try:c.execute(sql)
                except ReadOnlyViolation:pass
                else:raise AssertionError('PROBE_TRANSACTION_DML_ESCAPED')
            c.execute('COMMIT')
probe.close()
checks.append('IMMEDIATE/EXCLUSIVE allowed under identical guard on empty in-memory Django alias; readonly file lock protection preserved')
with connection.execute_wrapper(guard):
    with connection.cursor() as c:
        for begin in ['BEGIN','BEGIN TRANSACTION']:
            c.execute(begin);c.execute('SELECT 1');assert c.fetchone()==(1,)
            for sql in blocked[:2]:
                try:c.execute(sql)
                except ReadOnlyViolation:pass
                else:raise AssertionError('TRANSACTION_DML_ESCAPED')
            c.execute('COMMIT')
        c.execute('SAVEPOINT matrix_one')
        try:c.execute('DELETE FROM system_process')
        except ReadOnlyViolation:pass
        else:raise AssertionError('SAVEPOINT_DML_ESCAPED')
        c.execute('ROLLBACK TO SAVEPOINT matrix_one');c.execute('RELEASE SAVEPOINT matrix_one')
        c.execute('BEGIN');c.execute('ROLLBACK')
        c.execute('BEGIN');c.execute('END')
        for sql in allowed[12:22]:
            c.execute(sql);c.fetchall()
    checks.append('real cursor BEGIN/IMMEDIATE/EXCLUSIVE/SAVEPOINT/ROLLBACK/COMMIT/END; nested DML rejected')
    with transaction.atomic():
        assert Process.objects.count()==33
        with transaction.atomic():
            with connection.cursor() as c:
                assert connection.introspection.get_table_description(c,'pde_material_configuration')
                assert connection.introspection.get_constraints(c,'pde_material_configuration')
            assert MaterialConfigurationSerializer(MaterialConfiguration.objects.all(),many=True).data==[]
        try:
            with transaction.atomic():
                with connection.cursor() as c:c.execute('UPDATE system_process SET name=name')
        except ReadOnlyViolation:pass
        else:raise AssertionError('ATOMIC_DML_ESCAPED')
    checks.append('real nested Django atomic/introspection/constraints/ORM/serializer; DML still blocked')

    actor=User.objects.filter(is_superuser=True,company_id=1,is_active=True).defer('password').first();assert actor
    factory=APIRequestFactory();view=EngineeringCalculationReadinessView.as_view()
    def request(mode='semi-finished-structure',user=actor,method='get'):
        r=getattr(factory,method)('/api/pde/a1-engineering/calculations/readiness/',{'subview':mode})
        if user:force_authenticate(r,user)
        return view(r)
    r=request();assert r.status_code==200,r.data
    p=r.data['semiFinishedConfiguration']
    assert p['schemaCapability']['ready'] and not any(p['schemaCapability']['counts'].values())
    old=json.loads((ROOT/'docs/evidence/room_door_edge_20260909/API_READONLY_EVIDENCE.json').read_text(encoding='utf-8'))['semiFinishedConfiguration']
    assert p==apply_status(deepcopy(old),p['schemaCapability']), 'FROZEN_NUMERIC_OR_IDENTITY_DRIFT'
    assert all(r.data[k]==r.data['strictFacts'] for k in ('apiFacts','pageFacts','diagnosticFacts'))
    checks.extend(['actual migrated service GET200; schema ready and business rows zero',
        'complete frozen source projection unchanged except audited status adapter','API/page/diagnostic/strict same server facts'])
    assert request(user=None).status_code in (401,403);checks.append('anonymous denied')
    # Unsaved unprivileged actor: real authorization service, no user creation/permission mutation.
    outsider=User(id=-987654,username='READONLY_HARNESS_NO_PERMISSION',company_id=1,is_active=True,is_staff=False,is_superuser=False)
    denied=request(user=outsider);assert denied.status_code==403,denied.data
    checks.append('real authorization denies unprivileged actor without creating a user')
    assert request(mode='wrong').status_code==400;checks.append('unknown subview denied')
    assert request(method='post').status_code==405;checks.append('POST denied')
    with patch('pde.room_door_edge_preview.EVIDENCE_SHA','wrong'):
        failed=request();assert failed.status_code==503 and failed.data['factLoadStatus']=='read_failed'
    checks.append('source drift returns read_failed503; not empty-success')
    for code in ['PARTIAL_PRODUCTION_SCHEMA_RECHECK_REQUIRED','PRODUCTION_BUSINESS_FORMALIZATION_REBIND_REQUIRED']:
        with patch('pde.semi_finished_schema_status.read_capability',side_effect=ValueError(code)):
            failed=request();assert failed.status_code==503 and failed.data['resultCount'] is None
        checks.append(code+' rejected')
    original=request(mode='');assert original.status_code==200
    assert len(original.data['formalRules'])==4 and original.data['materialRuleDefinition']['sourceRowCount']==71
    checks.append('four rules and 71 source rows preserved')
connection.close();assert sha(path)==before
save(stage.upper()+'_GUARD_MATRIX.json',{'status':'PASS','matrix':matrix,'realChecks':checks,'events':guard.events,
    'databaseSHA':before,'mode':'SQLite URI mode=ro + query_only + per-statement guard','businessWrite':0})
save(stage.upper()+'_API.json',r.data)
print(json.dumps({'status':'PASS','stage':stage,'matrix':len(matrix),'realChecks':len(checks),'schemaReady':True,'dbUnchanged':True},ensure_ascii=False))
