from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('system','0019_process_workload_source_selection')]
    operations=[migrations.AddIndex(model_name='organizationoperatingauditrecord',
        index=models.Index(fields=['organization','target_type','target_id','action_code'],name='sys_audit_object_action_idx'))]
