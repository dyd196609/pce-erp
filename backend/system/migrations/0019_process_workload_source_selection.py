from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('system', '0018_normalize_process_display_order_schema')]

    operations = [
        migrations.AddField(
            model_name='process', name='workload_source_selection',
            field=models.JSONField('正式作业量来源方案引用', null=True, blank=True, default=None,
                help_text='由原工序维护服务保存精确产品/路线范围的完整正式方案引用；为空沿用既有规则。'),
        ),
    ]
