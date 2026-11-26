import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[("planning","0002_planning_access_workflow_v1"),("sales","0001_initial")]
    operations=[
        migrations.AlterField(model_name="demand",name="source_type",field=models.CharField(choices=[("manual_demand","人工计划需求"),("purchase_request","采购申请"),("sales_order","销售订单")],max_length=32)),
        migrations.AddField(model_name="demand",name="sales_order_item",field=models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="planning_demand",to="sales.salesorderitem")),
    ]
