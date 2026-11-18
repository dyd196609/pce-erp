from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('planning', '0093_m09_native_scope_proofs')]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[],
        state_operations=[migrations.AlterField(
            model_name='demand', name='source_type',
            field=models.CharField(max_length=32, choices=[
                ('manual_demand', '人工计划需求'), ('purchase_request', '采购申请'),
                ('sales_order', '销售订单'), ('production_material', '正式生产用料')]))])]
