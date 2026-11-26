from django.db import migrations

def verify_merged_structure(apps, schema_editor):
    connection = schema_editor.connection
    tables = set(connection.introspection.table_names())
    for model in apps.get_app_config('procurement').get_models():
        if not model._meta.managed or model._meta.proxy:
            continue
        table = model._meta.db_table
        if table not in tables:
            raise RuntimeError('Reconciliation missing table: ' + table)
        with connection.cursor() as cursor:
            columns = {row[1] for row in cursor.execute('PRAGMA table_info("' + table + '")').fetchall()}
        missing = {field.column for field in model._meta.local_fields} - columns
        if missing:
            raise RuntimeError('Reconciliation missing columns: ' + table + ':' + ','.join(sorted(missing)))
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            violations = cursor.execute('PRAGMA foreign_key_check').fetchall()
        if violations:
            raise RuntimeError('Reconciliation foreign key violations: ' + str(len(violations)))

class Migration(migrations.Migration):
    dependencies = [('procurement', '0028_completed_module_read_permissions'), ('procurement', '0091_formal_production_inbound_source')]
    operations = [migrations.RunPython(verify_merged_structure, verify_merged_structure)]
