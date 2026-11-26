"""One-column exact quantity migration; preserve original SQLite schema objects."""
from decimal import Decimal
import re
from django.db import migrations, transaction
from django.db.migrations.exceptions import IrreversibleError
import planning.fields


def _rebuild(schema_editor,reverse=False):
    connection=schema_editor.connection
    if connection.vendor!='sqlite':
        raise RuntimeError('This approved exact-storage migration is verified for SQLite only')
    field=planning.fields.ExactDemandQuantityField(max_digits=20,decimal_places=6)
    table='planning_demand';temporary='new__planning_demand_exact_quantity'
    with connection.cursor() as c:
        if c.execute('PRAGMA foreign_keys').fetchone()[0]:
            raise RuntimeError('Use the native migration schema editor with foreign-key checks safely suspended')
        original=c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=%s",[table]).fetchone()[0]
        expected='text' if reverse else 'decimal';target='decimal' if reverse else 'text'
        pattern=r'("required_qty"\s+)'+expected+r'(\s+NOT NULL)'
        sql,n=re.subn(pattern,lambda m:m.group(1)+target+m.group(2),original,flags=re.I)
        if n!=1:raise RuntimeError('Unexpected original Demand quantity column contract')
        zero='00000000000000.000000'
        old_check='"required_qty" > '+("'"+zero+"'" if reverse else "'0'")
        new_check='"required_qty" > '+("'0'" if reverse else "'"+zero+"'")
        if sql.count(old_check)!=1:raise RuntimeError('Unexpected original positive quantity constraint')
        sql=sql.replace(old_check,new_check)
        prefix='CREATE TABLE "planning_demand"'
        if not sql.startswith(prefix):raise RuntimeError('Unexpected original Demand table declaration')
        sql=sql.replace(prefix,'CREATE TABLE "'+temporary+'"',1)
        auxiliaries=c.execute("SELECT sql FROM sqlite_master WHERE tbl_name=%s AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name",[table]).fetchall()
        sequence=c.execute('SELECT seq FROM sqlite_sequence WHERE name=%s',[table]).fetchone()
        columns=[x[1] for x in c.execute('PRAGMA table_info(planning_demand)').fetchall()]
        column_sql=','.join('"'+x+'"' for x in columns)
        rows=c.execute('SELECT id,CAST(required_qty AS TEXT) FROM planning_demand ORDER BY id').fetchall()
        if reverse:
            for pk,raw in rows:
                value=Decimal(raw)
                if value!=value.quantize(Decimal('.0001')):
                    raise IrreversibleError('New exact six-decimal Demand exists; use forward-compatible recovery')
                numeric=c.execute('SELECT CAST(%s AS NUMERIC)',[raw]).fetchone()[0]
                if Decimal(str(numeric))!=value:
                    raise IrreversibleError('SQLite NUMERIC would lose saved Demand quantity; use compatible approved code')
        legacy=c.execute('PRAGMA legacy_alter_table').fetchone()[0]
        foreign_keys=c.execute('PRAGMA foreign_key_check').fetchall()
        c.execute('PRAGMA legacy_alter_table=ON')
        try:
            with transaction.atomic(using=connection.alias):
                c.execute(sql)
                selection=','.join('%s' if x=='required_qty' else '"'+x+'"' for x in columns)
                for pk,raw in rows:
                    exact=raw if reverse else field.get_db_prep_value(Decimal(raw),connection)
                    if Decimal(exact)!=Decimal(raw):raise ValueError('Quantity migration would change a value')
                    c.execute(f'INSERT INTO "{temporary}" ({column_sql}) SELECT {selection} FROM "{table}" WHERE id=%s',[exact,pk])
                c.execute(f'DROP TABLE "{table}"')
                c.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
                for (statement,) in auxiliaries:c.execute(statement)
                if sequence:c.execute('UPDATE sqlite_sequence SET seq=%s WHERE name=%s',[sequence[0],table])
                if c.execute('PRAGMA foreign_key_check').fetchall()!=foreign_keys:
                    raise RuntimeError('Demand migration changed foreign-key integrity')
        finally:
            c.execute('PRAGMA legacy_alter_table='+str(int(legacy)))


def forward(apps,schema_editor):_rebuild(schema_editor)
def reverse(apps,schema_editor):_rebuild(schema_editor,reverse=True)


class Migration(migrations.Migration):
    dependencies=[('planning','0094_production_material_source')]
    operations=[migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunPython(forward,reverse)],
        state_operations=[migrations.AlterField(model_name='demand',name='required_qty',
            field=planning.fields.ExactDemandQuantityField(max_digits=20,decimal_places=6))])]
