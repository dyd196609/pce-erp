from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies=[('pde','0045_engineering_version_handoff'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(
        name='EngineeringCalculationContinuation',
        fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('status',models.CharField(choices=[('draft','办理中'),('committed','已正式接续')],default='draft',max_length=20)),
            ('version',models.PositiveIntegerField(default=0)),
            ('context_hash',models.CharField(max_length=64)),('basis_hash',models.CharField(max_length=64)),
            ('source_snapshot',models.JSONField(default=dict)),('result_snapshot',models.JSONField(blank=True,default=dict)),
            ('reason',models.CharField(max_length=240)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('company',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='system.company')),
            ('adoption',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='calculation_continuations',to='pde.legacyinflightorderadoption')),
            ('sales_order_item',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='sales.salesorderitem')),
            ('engineering_instance',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='pde.orderengineeringinstance')),
            ('previous_calculation',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                related_name='formal_version_successor',to='pde.engineeringcalculationrecord')),
            ('new_calculation',models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,
                related_name='formal_version_admission',to='pde.engineeringcalculationrecord')),
            ('baseline',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='pde.orderengineeringbaseline')),
            ('write_request',models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,to='masterdata.masterdatawriterequest')),
            ('audit_record',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,
                to='system.organizationoperatingauditrecord')),
            ('created_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL)),
        ],
        options={'db_table':'pde_engineering_calculation_continuation','default_permissions':(),
            'constraints':[
                models.CheckConstraint(condition=models.Q(status__in=('draft','committed')),name='pde_calc_cont_status_valid'),
                models.CheckConstraint(condition=models.Q(status='draft')|models.Q(audit_record__isnull=False,new_calculation__isnull=False),
                    name='pde_calc_cont_commit_proven'),
            ]},
    )]
