from django.db import migrations
from procurement.fields import ExactNativeQuantityField
from procurement.exact_quantity_migration import convert, forward_only

DEFINITIONS={'planning_requirement': {'demand_qty': [20, 6, False], 'available_qty': [20, 6, True], 'net_required_qty': [20, 6, False]}, 'planning_purchase_plan': {'required_qty': [20, 6, False], 'available_qty': [20, 6, True], 'net_required_qty': [20, 6, False]}}

def forward(apps,schema_editor):
    convert(schema_editor,DEFINITIONS)

class Migration(migrations.Migration):
    dependencies=[('planning', '0095_demand_exact_quantity'), ('procurement', '0104_exact_purchase_stock_quantities')]
    operations=[migrations.SeparateDatabaseAndState(database_operations=[migrations.RunPython(forward,forward_only)],state_operations=[
        migrations.AlterField(model_name='planningrequirement',name='demand_qty',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='planningrequirement',name='available_qty',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,null=True,blank=True)),
        migrations.AlterField(model_name='planningrequirement',name='net_required_qty',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='purchaseplan',name='required_qty',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='purchaseplan',name='available_qty',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,null=True,blank=True)),
        migrations.AlterField(model_name='purchaseplan',name='net_required_qty',field=ExactNativeQuantityField(max_digits=20,decimal_places=6))
    ])]
