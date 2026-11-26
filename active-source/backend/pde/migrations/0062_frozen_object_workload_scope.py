from django.db import migrations

def forward(apps,editor):
    if editor.connection.vendor!='sqlite':raise RuntimeError('Reviewed SQLite scope protection required')
    sql=editor.connection.cursor().execute("SELECT sql FROM sqlite_master WHERE name='pde_workload_cross_requirement_scope'").fetchone()[0]
    old="NEW.component_key!=''"
    assert old in sql
    editor.execute('DROP TRIGGER pde_workload_cross_requirement_scope')
    editor.execute(sql.replace(old,"(NEW.component_key!='' OR JSON_EXTRACT(NEW.trace,'$.proof.scopeMode')='BASELINE_ITEM_TOTAL')"))
    editor.execute("CREATE UNIQUE INDEX pde_test_object_scope_once ON pde_engineering_operation_requirement(execution_arrangement_id,arrangement_revision,arrangement_edit_version,routing_step_id,baseline_item_id) WHERE usage_purpose='TEST_BUSINESS' AND component_key=''")

def backward(apps,editor):
    if editor.connection.cursor().execute("SELECT 1 FROM pde_engineering_operation_requirement WHERE usage_purpose='TEST_BUSINESS' AND component_key='' LIMIT 1").fetchone():raise RuntimeError('Preserve aggregate history; use backup restoration or reviewed forward recovery')
    sql=editor.connection.cursor().execute("SELECT sql FROM sqlite_master WHERE name='pde_workload_cross_requirement_scope'").fetchone()[0]
    editor.execute('DROP TRIGGER pde_workload_cross_requirement_scope')
    editor.execute(sql.replace("(NEW.component_key!='' OR JSON_EXTRACT(NEW.trace,'$.proof.scopeMode')='BASELINE_ITEM_TOTAL')","NEW.component_key!=''"))
    editor.execute('DROP INDEX pde_test_object_scope_once')

class Migration(migrations.Migration):
    dependencies=[('pde','0061_workload_cross_table_guards')]
    operations=[migrations.RunPython(forward,backward)]
