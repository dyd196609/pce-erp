import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pde', '0039_manufacturing_mode_eor_configuration'),
    ]

    operations = [
        migrations.AddField(
            model_name='engineeringcalculationrecord',
            name='origin_calculation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='fact_extensions', to='pde.engineeringcalculationrecord',
                                    verbose_name='固定原订单工程核算'),
        ),
        migrations.AlterField(
            model_name='engineeringcalculationrecord',
            name='scope',
            field=models.CharField(choices=[('validation', '规则技术验证'), ('order_engineering', '正式订单工程核算'),
                                            ('fact_extension', '固定工程事实增量承接'),
                                            ('operation_requirement', '工程工序需求承接')],
                                   default='order_engineering', max_length=24, verbose_name='计算范围'),
        ),
        migrations.AddConstraint(
            model_name='engineeringcalculationrecord',
            constraint=models.CheckConstraint(
                condition=(models.Q(scope='fact_extension', origin_calculation__isnull=False, supersedes__isnull=True)
                           | (~models.Q(scope='fact_extension') & models.Q(origin_calculation__isnull=True))),
                name='pde_eng_calc_extension_origin_valid',
            ),
        ),
        migrations.CreateModel(
            name='EngineeringFactInput',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('input_name', models.CharField(max_length=160, verbose_name='规范输入名')),
                ('sequence', models.PositiveIntegerField(default=1, verbose_name='来源顺序')),
                ('source_hash', models.CharField(max_length=64, verbose_name='来源输入证据哈希')),
                ('input_snapshot', models.JSONField(default=dict, verbose_name='固定输入快照')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('fact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inputs',
                                          to='pde.engineeringderivedfact', verbose_name='目标工程事实')),
                ('source_fact', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                 related_name='input_consumptions', to='pde.engineeringderivedfact',
                                                 verbose_name='固定来源工程事实')),
            ],
            options={
                'db_table': 'pde_engineering_fact_input',
                'ordering': ('fact_id', 'input_name', 'sequence'),
                'default_permissions': (),
                'constraints': [
                    models.UniqueConstraint(fields=('fact', 'input_name', 'sequence'),
                                            name='pde_eng_fact_input_identity_unique'),
                    models.CheckConstraint(condition=models.Q(sequence__gt=0),
                                           name='pde_eng_fact_input_sequence_positive'),
                    models.CheckConstraint(condition=~models.Q(fact=models.F('source_fact')),
                                           name='pde_eng_fact_input_no_self'),
                ],
            },
        ),
    ]
