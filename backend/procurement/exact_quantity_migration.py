"""Preserve existing SQLite rows, identities, indexes and constraints exactly."""
from decimal import Decimal
import re
from django.db import transaction
from planning.fields import ExactDemandQuantityField


def convert(schema_editor, definitions):
    connection = schema_editor.connection
    if connection.vendor != 'sqlite':
        raise RuntimeError('Exact native quantity migration is verified for SQLite only')
    with connection.cursor() as c:
        if c.execute('PRAGMA foreign_keys').fetchone()[0]:
            raise RuntimeError('Use the native migration schema editor with FK checks suspended')
        baseline_fk = c.execute('PRAGMA foreign_key_check').fetchall()
        for table, fields in definitions.items():
            original = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=%s", [table]).fetchone()[0]
            temporary = 'new__' + table + '_exact_quantity'
            sql = original
            for name, (digits, places, nullable) in fields.items():
                pattern = r'("' + re.escape(name) + r'"\s+)decimal(\s+NOT NULL)?'
                sql, count = re.subn(pattern, lambda m: m.group(1) + 'text' + ('' if nullable else (m.group(2) or '')), sql, flags=re.I)
                if count != 1:
                    raise RuntimeError(f'Unexpected quantity column contract: {table}.{name}')
                zero = format(Decimal(0), f'0{digits+1}.{places}f')
                # Comparisons remain numeric in meaning on fixed-width exact TEXT.
                sql = re.sub(r'("' + re.escape(name) + r'"\s*(?:>=|>)\s*)[\'\"]?0[\'\"]?(?=[ )])', lambda m: m.group(1) + "'" + zero + "'", sql)
            prefix = 'CREATE TABLE "' + table + '"'
            if not sql.startswith(prefix):
                raise RuntimeError('Unexpected table identity')
            sql = sql.replace(prefix, 'CREATE TABLE "' + temporary + '"', 1)
            auxiliaries = c.execute("SELECT sql FROM sqlite_master WHERE tbl_name=%s AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name", [table]).fetchall()
            sequence = c.execute('SELECT seq FROM sqlite_sequence WHERE name=%s', [table]).fetchone()
            information = c.execute('PRAGMA table_info("' + table + '")').fetchall()
            columns = [r[1] for r in information]
            primary = [r[1] for r in information if r[5]]
            if len(primary) != 1:
                raise RuntimeError('Expected one original primary identity')
            pk = primary[0]
            column_sql = ','.join('"' + name + '"' for name in columns)
            values = c.execute('SELECT "' + pk + '",' + ','.join('CAST("' + name + '" AS TEXT)' for name in fields) + ' FROM "' + table + '" ORDER BY "' + pk + '"').fetchall()
            legacy = c.execute('PRAGMA legacy_alter_table').fetchone()[0]
            c.execute('PRAGMA legacy_alter_table=ON')
            try:
                with transaction.atomic(using=connection.alias):
                    c.execute(sql)
                    selection = ','.join('%s' if name in fields else '"' + name + '"' for name in columns)
                    for row in values:
                        raw_values = dict(zip(fields, row[1:]))
                        exact_values = {}
                        for name, (digits, places, nullable) in fields.items():
                            raw = raw_values[name]
                            value = None if raw is None else Decimal(raw)
                            exact = ExactDemandQuantityField(max_digits=digits, decimal_places=places, null=nullable).get_db_prep_value(value, connection)
                            if (None if exact is None else Decimal(exact)) != value:
                                raise RuntimeError('Migration would change an existing numeric fact')
                            exact_values[name] = exact
                        c.execute(f'INSERT INTO "{temporary}" ({column_sql}) SELECT {selection} FROM "{table}" WHERE "{pk}"=%s', [exact_values[name] for name in columns if name in fields] + [row[0]])
                    c.execute('DROP TABLE "' + table + '"')
                    c.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
                    for (statement,) in auxiliaries:
                        c.execute(statement)
                    if sequence:
                        c.execute('UPDATE sqlite_sequence SET seq=%s WHERE name=%s', [sequence[0], table])
                    if c.execute('PRAGMA foreign_key_check').fetchall() != baseline_fk:
                        raise RuntimeError('Foreign key integrity changed')
            finally:
                c.execute('PRAGMA legacy_alter_table=' + str(int(legacy)))


def forward_only(apps, schema_editor):
    from django.db.migrations.exceptions import IrreversibleError
    raise IrreversibleError('Preserve new exact quantities and facts; recover with compatible code or a forward repair')
