from django.db import migrations
from procurement.fields import ExactNativeQuantityField
from procurement.exact_quantity_migration import convert, forward_only

DEFINITIONS={'scm_purchase_request': {'quantity': [20, 6, False]}, 'scm_purchase_request_item': {'quantity': [20, 6, False]}, 'scm_purchase_inquiry': {'quantity': [20, 6, False]}, 'scm_supplier_quotation': {'quantity': [20, 6, False]}, 'scm_quote_comparison_fact': {'quantity': [20, 6, False]}, 'purchase_order_item': {'quantity': [16, 6, False], 'actual_quantity': [16, 6, True]}, 'scm_purchase_receipt': {'quantity': [20, 6, False]}, 'scm_purchase_inspection': {'quantity': [20, 6, False], 'qualified_quantity': [20, 6, False], 'rejected_quantity': [20, 6, False]}, 'scm_warehouse_inbound': {'quantity': [20, 6, False]}, 'scm_inventory_balance': {'quantity': [20, 6, False]}, 'scm_inventory_transaction': {'quantity': [20, 6, False], 'before_quantity': [20, 6, False], 'after_quantity': [20, 6, False]}}

def forward(apps,schema_editor):
    convert(schema_editor,DEFINITIONS)

class Migration(migrations.Migration):
    dependencies=[('procurement', '0103_incoming_exception_return'), ('planning', '0095_demand_exact_quantity')]
    operations=[migrations.SeparateDatabaseAndState(database_operations=[migrations.RunPython(forward,forward_only)],state_operations=[
        migrations.AlterField(model_name='purchaserequest',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='purchaserequestitem',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='purchaseinquiry',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='supplierquotation',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='quotecomparisonfact',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='purchaseorderitem',name='quantity',field=ExactNativeQuantityField('计划数量',max_digits=16,decimal_places=6,legacy_decimal_places=2)),
        migrations.AlterField(model_name='purchaseorderitem',name='actual_quantity',field=ExactNativeQuantityField('实际交货数量',max_digits=16,decimal_places=6,legacy_decimal_places=2,null=True,blank=True)),
        migrations.AlterField(model_name='purchasereceipt',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='purchaseinspection',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='purchaseinspection',name='qualified_quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='purchaseinspection',name='rejected_quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='warehouseinbound',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='inventorybalance',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6,default=0)),
        migrations.AlterField(model_name='inventorytransaction',name='quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='inventorytransaction',name='before_quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6)),
        migrations.AlterField(model_name='inventorytransaction',name='after_quantity',field=ExactNativeQuantityField(max_digits=20,decimal_places=6))
    ])]
