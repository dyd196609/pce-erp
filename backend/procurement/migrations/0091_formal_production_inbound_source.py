"""Permit the proven formal production source, retaining exact source XOR.

No data relabeling and no source/state backfill. Existing procurement and TEST
branches retain their conditions. Rollback cannot discard formal stock facts.
"""
from django.db import migrations,models

def guard_reverse(apps,schema_editor):
    inbound=apps.get_model('procurement','WarehouseInbound')
    if inbound.objects.using(schema_editor.connection.alias).filter(
            usage_purpose='PRODUCTION_USE',production_transfer__isnull=False).exists():
        raise RuntimeError('已有正式生产成品入库事实，禁止降级约束丢失来源；请使用一致整库检查点恢复。')

class Migration(migrations.Migration):
    dependencies=[('procurement','0090_test_inventory_purpose')]
    operations=[
        migrations.RemoveConstraint(model_name='warehouseinbound',name='wms_inbound_exact_source'),
        migrations.AddConstraint(model_name='warehouseinbound',constraint=models.CheckConstraint(
            condition=(models.Q(source_inspection__isnull=False,production_transfer__isnull=True)&~models.Q(usage_purpose='TEST_BUSINESS'))
                |models.Q(source_inspection__isnull=True,production_transfer__isnull=False,
                    usage_purpose__in=('TEST_BUSINESS','PRODUCTION_USE')),
            name='wms_inbound_exact_source')),
        migrations.RunPython(migrations.RunPython.noop,reverse_code=guard_reverse),
    ]
