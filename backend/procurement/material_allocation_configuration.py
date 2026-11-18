"""Approved existing-role/duty increments via the original maintenance services."""
from django.db import transaction
from system.models import Role,RolePermission,UserRoleScopeAssignment,PositionResponsibility
from pfm.formal_employee import formal_employee_queryset
from planning.operation_handover_configuration import admin,foundation,_definition,_assign_existing_node,fail
PERMISSION='warehouse.material.allocate'
PROCESS='WMS_PRODUCTION_MATERIAL_ALLOCATION'
NODE='CONFIRM_PRODUCTION_MATERIAL_ALLOCATION'
DUTY='RESP_WH_IO_001'
DEFINITION={'definitionCode':PROCESS,'definitionName':'生产用料原料分配确认','businessDomain':'WMS',
 'documentType':'ProductionMaterialStockAllocation','version':1,'active':True,
 'description':'已确认正式需求与原采购合格库存的显式分配；仅供给占用，不是备料/领料/释放，不增加审批层级。'}
NODES=[{'nodeCode':NODE,'nodeName':'确认生产用料原料分配','sequence':1,'businessActionCode':PERMISSION,
 'active':True,'description':'原有效仓管职责显式选择准确库存来源和需求，原账不扣减；原事务、审计和同次结果。'}]

@transaction.atomic
def configure(*,user,reason,request_identity):
 admin(user)
 if not reason or not request_identity:fail('MATERIAL_CONFIG_REASON_REQUIRED','维护须明确授权依据及同次标识。',400)
 additions={'warehouse':{PERMISSION,'warehouse.inventory.read','warehouse.inventory_transaction.read'},
            'quality_inspector':{'quality.purchase_inspection.read'}}
 out=[]
 for code,codes in additions.items():
  role=Role.objects.get(code=code)
  previous=set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))
  if not codes<=previous:
   result=foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':sorted(previous|codes),'appendOnly':True,'expectedPermissionCodes':sorted(previous)},reason)
   out.append({'role':code,'added':sorted(codes-previous),'maintenance':result})
 _definition(user,DEFINITION,NODES,reason,request_identity+'-definition')
 accounts=UserRoleScopeAssignment.objects.filter(role__code='warehouse',organization_id=user.company_id,active=True).values('user_id')
 employees=formal_employee_queryset(company_id=user.company_id).filter(user_id__in=accounts).select_related('position_ref','user')
 positions=set();links=[]
 for e in employees:
  if e.position_ref_id in positions:continue
  if not PositionResponsibility.objects.filter(position=e.position_ref,active=True,responsibility__code=DUTY,responsibility__is_active=True,responsibility__status='ACTIVE').exists():
   fail('MATERIAL_CONFIG_EXISTING_DUTY_REQUIRED','只维护已有仓库出入库职责，不补造岗位。')
  positions.add(e.position_ref_id)
  links.append(_assign_existing_node(user,e,PROCESS,NODE,DUTY,'EXECUTOR',reason,request_identity+'-position-'+str(e.position_ref_id)))
 if not positions:fail('MATERIAL_CONFIG_NO_EXISTING_WAREHOUSE_ACTOR','未找到当前企业原角色、在职仓管及原职责。')
 return {'configurationOnly':True,'roleChanges':out,'workflowResponsibilityIds':links,'newPeopleAccountsRolesScopes':0,'dailyBusinessActions':0}

@transaction.atomic
def configure_resources(*,user,warehouse_code,warehouse_name,location_code,location_name,reason):
 """Explicitly approved raw warehouse resources, through the original audit service."""
 from .models import Warehouse,WarehouseLocation
 from workflow_runtime.definition_service import WorkflowDefinitionOperatingService
 admin(user)
 for value,size in [(warehouse_code,50),(warehouse_name,100),(location_code,80),(location_name,120),(reason,300)]:
  if not isinstance(value,str) or not 1<=len(value.strip())<=size:fail('MATERIAL_RESOURCE_INPUT_REQUIRED','须明确原料仓、库位及维护依据。',400)
 warehouse=Warehouse.all_objects.select_for_update().filter(code=warehouse_code).first()
 if warehouse and (warehouse.company_id!=user.company_id or warehouse.name!=warehouse_name or warehouse.usage_purpose!='PRODUCTION_USE' or not warehouse.is_active):fail('MATERIAL_RESOURCE_CONFLICT','同码资源归属、用途或状态不同，不能覆盖旧资源。')
 if not warehouse:
  warehouse=Warehouse.all_objects.create(code=warehouse_code,name=warehouse_name,company_id=user.company_id,usage_purpose='PRODUCTION_USE',is_active=True)
  WorkflowDefinitionOperatingService._audit(user=user,action='REGISTER_FORMAL_RAW_MATERIAL_WAREHOUSE',target=warehouse,target_type='Warehouse',label=warehouse.code,reason=reason,before={},after={'warehouseId':warehouse.pk,'usagePurpose':'PRODUCTION_USE','configurationOnly':True})
 location=WarehouseLocation.all_objects.select_for_update().filter(warehouse=warehouse,code=location_code).first()
 if location and (location.name!=location_name or not location.is_active):fail('MATERIAL_RESOURCE_CONFLICT','同码库位不同，不覆盖旧资源。')
 if not location:
  location=WarehouseLocation.all_objects.create(warehouse=warehouse,code=location_code,name=location_name,is_active=True)
  WorkflowDefinitionOperatingService._audit(user=user,action='REGISTER_FORMAL_RAW_MATERIAL_LOCATION',target=location,target_type='WarehouseLocation',label=location.code,reason=reason,before={},after={'warehouseId':warehouse.pk,'locationId':location.pk,'configurationOnly':True})
 return {'configurationOnly':True,'warehouseId':warehouse.pk,'locationId':location.pk,'existingResourcesReclassified':0,'scopesAdded':0}
