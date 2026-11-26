from django.db import migrations,models

KINDS=['return_request','return_decide','return_handover']
def reverse_guard(apps,schema_editor):
 if apps.get_model('procurement','IncomingQualityExceptionFact').objects.filter(kind__in=KINDS).exists():
  raise RuntimeError('INCOMING_RETURN_FACTS_EXIST_KEEP_CURRENT_DB_AND_COMPATIBLE_CODE')
 if apps.get_model('system','RolePermission').objects.filter(permission__code__in=[
  'procurement.incoming_exception.return_request','procurement.incoming_exception.return_decide',
  'warehouse.incoming_exception.return_handover']).exists():
  raise RuntimeError('INCOMING_RETURN_CONFIGURATION_EXISTS_KEEP_COMPATIBLE_CODE')
 if apps.get_model('workflow_runtime','WorkflowNodeDefinition').objects.filter(process_definition__definition_code='PROCUREMENT_INCOMING_RETURN').exists():
  raise RuntimeError('INCOMING_RETURN_NODES_EXIST_KEEP_CURRENT_DB')

class Migration(migrations.Migration):
 dependencies=[('procurement','0102_incoming_exception_supplier_opinion')]
 operations=[migrations.AlterField(model_name='incomingqualityexceptionfact',name='kind',field=models.CharField(max_length=16,
  choices=[('register','异常登记'),('custody','实物保管核对'),('opinion','供应商意见'),
   ('return_request','企业退供申请'),('return_decide','企业退供决定'),('return_handover','现场签收交付')])),
  migrations.RunPython(migrations.RunPython.noop,reverse_guard)]
