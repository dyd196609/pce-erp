"""One independent preparation table; no data migration or existing table edits."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pde', '0042_routing_step_object_applicability_correction')]

    operations = [migrations.CreateModel(
        name='OperationInputPreparationDraft',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('object_coverage', models.JSONField()),
            ('objects_hash', models.CharField(max_length=64)),
            ('context_hash', models.CharField(max_length=64, unique=True)),
            ('status', models.CharField(choices=[('draft', '准备草稿')], max_length=12)),
            ('input_standard_status', models.CharField(choices=[('PENDING_CONFIRMATION', '待确认')], max_length=24)),
            ('capacity_measurement_status', models.CharField(choices=[('UNMEASURED', '尚未测定')], max_length=16)),
            ('draft_selection', models.JSONField(blank=True, null=True)),
            ('business_basis', models.JSONField()),
            ('revision', models.PositiveIntegerField(default=1)),
            ('content_hash', models.CharField(max_length=64)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='operation_input_preparations', to='system.company')),
            ('operation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='system.process')),
            ('product_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.capacityproducttype')),
            ('production_plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='operation_input_preparations', to='planning.productionplan')),
            ('manufacturing_output', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.productmanufacturingoutput')),
            ('main_calculation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.engineeringcalculationrecord')),
            ('engineering_baseline', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='operation_input_preparations', to='pde.orderengineeringbaseline')),
            ('routing_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.routingversion')),
            ('routing_step', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.routingstep')),
            ('producer_rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.engineeringruledefinition')),
            ('manufacturing_mode', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.manufacturingmode')),
            ('work_center', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.workcenter')),
            ('standard_capacity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='input_preparations', to='pde.standardcapacity')),
            ('creation_write_request', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name='operation_input_preparation', to='masterdata.masterdatawriterequest')),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='created_operation_input_preparations', to=settings.AUTH_USER_MODEL)),
            ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='updated_operation_input_preparations', to=settings.AUTH_USER_MODEL)),
        ],
        options={
            'db_table': 'pde_operation_input_preparation_draft', 'default_permissions': (),
            'ordering': ('production_plan_id', 'routing_step_id', 'pk'),
            'indexes': [models.Index(fields=['company', 'production_plan', 'routing_step'], name='pde_opprep_plan_step_idx')],
            'constraints': [
                models.UniqueConstraint(fields=('company', 'operation', 'product_type', 'production_plan',
                    'manufacturing_output', 'main_calculation', 'engineering_baseline', 'routing_version',
                    'routing_step'), name='pde_opprep_real_scope_uniq'),
                models.CheckConstraint(condition=models.Q(status='draft', input_standard_status='PENDING_CONFIRMATION',
                    capacity_measurement_status='UNMEASURED'), name='pde_opprep_states_valid'),
                models.CheckConstraint(condition=models.Q(revision__gte=1), name='pde_opprep_revision_positive'),
                models.CheckConstraint(condition=(~models.Q(context_hash='') & ~models.Q(objects_hash='')
                    & ~models.Q(content_hash='')), name='pde_opprep_hashes_required'),
            ],
        },
    )]
