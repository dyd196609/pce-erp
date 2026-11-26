from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('planning', '0092_verified_branch_reconciliation')]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[
            migrations.RunSQL("ALTER TABLE planning_demand ADD COLUMN batch_key varchar(80) NOT NULL DEFAULT ''"),
            migrations.RunSQL("ALTER TABLE planning_demand ADD COLUMN batch_scope text NOT NULL DEFAULT '{}' CHECK (JSON_VALID(batch_scope))"),
            migrations.RunSQL('DROP INDEX planning_demand_item_output_unique'),
            migrations.RunSQL('CREATE UNIQUE INDEX planning_demand_item_output_batch_unique ON planning_demand (sales_order_item_id, manufacturing_output_id, batch_key) WHERE sales_order_item_id IS NOT NULL AND manufacturing_output_id IS NOT NULL'),
        ],
        state_operations=[
            migrations.RemoveConstraint(model_name='demand', name='planning_demand_item_output_unique'),
            migrations.AddField(model_name='demand', name='batch_key', field=models.CharField(blank=True, default='', max_length=80)),
            migrations.AddField(model_name='demand', name='batch_scope', field=models.JSONField(blank=True, default=dict)),
            migrations.AddConstraint(model_name='demand', constraint=models.UniqueConstraint(fields=('sales_order_item','manufacturing_output','batch_key'), condition=models.Q(sales_order_item__isnull=False,manufacturing_output__isnull=False), name='planning_demand_item_output_batch_unique')),
        ])]
