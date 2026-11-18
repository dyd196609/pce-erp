from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pde', '0046_engineering_calculation_continuation'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='ManufacturingTimePolicyRevision',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('company', models.ForeignKey('system.company', on_delete=models.PROTECT)),
            ('kind', models.CharField(max_length=32, choices=[('SHARED_ARRANGEMENT', '共用工作安排'), ('WC_APPLICATION', '工作中心适用'), ('OPERATION_RESTRICTION', '工序时间限制'), ('CAPACITY_TIME_BASIS', '产能时间依据')])),
            ('code', models.CharField(max_length=80)),
            ('name', models.CharField(max_length=160)),
            ('revision', models.PositiveIntegerField(default=1)),
            ('version', models.PositiveIntegerField(default=1)),
            ('scope_key', models.CharField(max_length=64)),
            ('predecessor', models.ForeignKey('pde.manufacturingtimepolicyrevision', null=True, blank=True, on_delete=models.PROTECT, related_name='successors')),
            ('shared_version', models.ForeignKey('pde.manufacturingtimepolicyrevision', null=True, blank=True, on_delete=models.PROTECT, related_name='policy_applications')),
            ('work_center', models.ForeignKey('pde.workcenter', null=True, blank=True, on_delete=models.PROTECT, related_name='time_policy_revisions')),
            ('operation', models.ForeignKey('system.process', null=True, blank=True, on_delete=models.PROTECT, related_name='time_policy_revisions')),
            ('standard_capacity', models.ForeignKey('pde.standardcapacity', null=True, blank=True, on_delete=models.PROTECT, related_name='time_policy_revisions')),
            ('effective_from', models.DateField(null=True, blank=True)),
            ('effective_to', models.DateField(null=True, blank=True)),
            ('status', models.CharField(max_length=16, choices=(('draft', '待完善'), ('confirmed', '已确认')), default='draft')),
            ('schema_version', models.CharField(max_length=64, default='PCE-MANUFACTURING-TIME-POLICY-V1')),
            ('payload', models.JSONField(default=dict, blank=True)),
            ('reference_snapshot', models.JSONField(default=dict, blank=True)),
            ('content_hash', models.CharField(max_length=64)),
            ('confirmation_basis', models.CharField(max_length=1000, blank=True, default='')),
            ('creation_write_request', models.OneToOneField('masterdata.masterdatawriterequest', on_delete=models.PROTECT, related_name='created_time_policy_revision')),
            ('confirmation_write_request', models.OneToOneField('masterdata.masterdatawriterequest', null=True, blank=True, on_delete=models.PROTECT, related_name='confirmed_time_policy_revision')),
            ('confirmation_audit', models.ForeignKey('system.organizationoperatingauditrecord', null=True, blank=True, on_delete=models.PROTECT, related_name='confirmed_time_policies')),
            ('created_by', models.ForeignKey('system.user', on_delete=models.PROTECT, related_name='created_time_policies')),
            ('updated_by', models.ForeignKey('system.user', on_delete=models.PROTECT, related_name='updated_time_policies')),
            ('confirmed_by', models.ForeignKey('system.user', null=True, blank=True, on_delete=models.PROTECT, related_name='confirmed_time_policies')),
            ('confirmed_at', models.DateTimeField(null=True, blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ],
        options={
            'db_table': 'pde_manufacturing_time_policy_revision',
            'default_permissions': (),
            'ordering': ('company_id', 'kind', 'scope_key', 'revision'),
            'constraints': [models.CheckConstraint(condition=models.Q(kind__in=('SHARED_ARRANGEMENT', 'WC_APPLICATION', 'OPERATION_RESTRICTION', 'CAPACITY_TIME_BASIS')), name='pde_timepolicy_kind_valid'), models.CheckConstraint(condition=models.Q(kind='SHARED_ARRANGEMENT', work_center__isnull=True, operation__isnull=True, standard_capacity__isnull=True, shared_version__isnull=True) | models.Q(kind='WC_APPLICATION', work_center__isnull=False, operation__isnull=True, standard_capacity__isnull=True, shared_version__isnull=False) | models.Q(kind='OPERATION_RESTRICTION', operation__isnull=False, standard_capacity__isnull=True, shared_version__isnull=True) | models.Q(kind='CAPACITY_TIME_BASIS', work_center__isnull=True, operation__isnull=True, standard_capacity__isnull=False), name='pde_timepolicy_scope_valid'), models.CheckConstraint(condition=models.Q(status__in=('draft', 'confirmed')), name='pde_timepolicy_state_valid'), models.CheckConstraint(condition=models.Q(revision__gte=1, version__gte=1), name='pde_timepolicy_versions_valid'), models.CheckConstraint(condition=models.Q(effective_from__isnull=True) | models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from')), name='pde_timepolicy_period_valid'), models.CheckConstraint(condition=models.Q(status='draft') | models.Q(effective_from__isnull=False, confirmed_by__isnull=False, confirmed_at__isnull=False, confirmation_audit__isnull=False, confirmation_write_request__isnull=False), name='pde_timepolicy_confirm_proven'), models.CheckConstraint(condition=~models.Q(content_hash='') & ~models.Q(scope_key=''), name='pde_timepolicy_hash_required'), models.UniqueConstraint(fields=('company', 'kind', 'scope_key', 'revision'), name='pde_timepolicy_scope_revision'), models.UniqueConstraint(fields=('predecessor',), condition=models.Q(predecessor__isnull=False), name='pde_timepolicy_single_successor')],
            'indexes': [models.Index(fields=('company', 'kind', 'status', 'scope_key'), name='pde_timepolicy_scope_idx')],
        },
    )]
