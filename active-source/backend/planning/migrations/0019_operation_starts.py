"""Daily extension only: create the independent actual-start table."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('planning', '0017_workshop_tasks')]
    operations = [migrations.CreateModel(name='ProductionOperationStart', fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('workload_quantity', models.CharField(max_length=100)),
        ('task_version', models.PositiveIntegerField()),
        ('source_snapshot', models.JSONField()), ('source_snapshot_hash', models.CharField(max_length=64)),
        ('assignment_snapshot', models.JSONField()), ('assignment_hash', models.CharField(max_length=64)),
        ('started_at', models.DateTimeField()), ('start_qualification', models.JSONField()),
        ('reason', models.TextField()),
        ('status', models.CharField(choices=[('started', '已开工')], default='started', max_length=20)),
        ('version', models.PositiveIntegerField(default=0)), ('created_at', models.DateTimeField(auto_now_add=True)),
        ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='system.company')),
        ('task', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='operation_start', to='planning.productionworkshoptask')),
        ('work_order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='planning.productionworkorder')),
        ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='planning.productionworkorderworkshopreceipt')),
        ('source_operation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='planning.productionworkorderoperation')),
        ('workshop', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='system.workshop')),
        ('work_center', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pde.workcenter')),
        ('workload_uom', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='masterdata.unitofmeasure')),
        ('execution_position', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='system.position')),
        ('execution_employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='pfm.employee')),
        ('started_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='started_production_operations', to=settings.AUTH_USER_MODEL)),
    ], options={'db_table': 'planning_production_operation_start', 'default_permissions': (),
        'constraints': [models.CheckConstraint(condition=models.Q(('status', 'started')), name='operation_start_only_started')]})]
