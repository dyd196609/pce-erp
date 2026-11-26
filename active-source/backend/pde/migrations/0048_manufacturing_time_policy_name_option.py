from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('pde', '0047_manufacturing_time_policy_revision')]
    operations = [migrations.CreateModel(
        name='ManufacturingTimePolicyNameOption',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='system.company')),
            ('name', models.CharField(max_length=160)),
            ('is_active', models.BooleanField(default=True)),
            ('sort_order', models.PositiveIntegerField(default=0)),
            ('version', models.PositiveIntegerField(default=1)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ],
        options={
            'db_table': 'pde_manufacturing_time_policy_name_option',
            'default_permissions': (), 'ordering': ('company_id', 'sort_order', 'pk'),
            'constraints': [
                models.UniqueConstraint(fields=('company', 'name'), name='pde_timepolicy_name_company_unique'),
                models.CheckConstraint(condition=models.Q(version__gte=1), name='pde_timepolicy_name_version_valid'),
                models.CheckConstraint(condition=models.Q(sort_order__gte=0), name='pde_timepolicy_name_sort_valid'),
                models.CheckConstraint(condition=~models.Q(name=''), name='pde_timepolicy_name_required'),
            ],
        },
    )]
