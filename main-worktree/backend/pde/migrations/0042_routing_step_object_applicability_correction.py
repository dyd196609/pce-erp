"""Independent append-only correction table; no existing table or data edits."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pde', '0041_routing_step_object_applicability')]

    operations = [
        migrations.CreateModel(
            name='RoutingStepObjectApplicabilityCorrection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('context_hash', models.CharField(max_length=64)),
                ('root_record_hash', models.CharField(max_length=64)),
                ('predecessor_hash', models.CharField(max_length=64)),
                ('decision', models.CharField(choices=[('REQUIRED', '必须执行'), ('NOT_APPLICABLE', '不适用'), ('PENDING', '待确认')], max_length=16)),
                ('basis', models.JSONField(default=dict)),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='routing_object_corrections', to='system.company')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='routing_object_corrections', to=settings.AUTH_USER_MODEL)),
                ('predecessor', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name='successor', to='pde.routingstepobjectapplicabilitycorrection')),
                ('root_record', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='corrections', to='pde.routingstepobjectapplicability')),
                ('write_request', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                    related_name='routing_object_correction', to='masterdata.masterdatawriterequest')),
            ],
            options={
                'db_table': 'pde_routing_object_applicability_correction',
                'default_permissions': (),
                'ordering': ('root_record_id', 'pk'),
                'constraints': [
                    models.UniqueConstraint(fields=('root_record',), condition=models.Q(predecessor__isnull=True),
                        name='pde_obj_corr_first_unique'),
                    models.CheckConstraint(condition=models.Q(decision__in=('REQUIRED', 'NOT_APPLICABLE', 'PENDING')),
                        name='pde_obj_corr_decision_valid'),
                    models.CheckConstraint(condition=(~models.Q(context_hash='') & ~models.Q(root_record_hash='')
                        & ~models.Q(predecessor_hash='')), name='pde_obj_corr_hash_required'),
                    models.CheckConstraint(condition=~models.Q(id=models.F('predecessor_id')),
                        name='pde_obj_corr_no_self'),
                ],
            },
        ),
    ]
