"""Explicit, audited TEST receiving configuration; no automatic runtime grants."""
from django.db import transaction
from django.utils import timezone
from system.models import Permission,Role,RolePermission,Company,UserRoleScopeAssignment,OrganizationOperatingAuditRecord
from pfm.formal_employee import formal_employee_queryset
from workflow_runtime.models import ProcessDefinition
from workflow_runtime.definition_service import WorkflowDefinitionOperatingService
from .operation_handover_configuration import admin,_definition,_assign_existing_node,_append_grant,foundation
from .finished_goods_contract import RECEIVE,PROCESS,NODE,DUTY,DEFINITION,NODES
from .operation_handover_core import fail
from procurement.inventory_purpose import TEST,test_purpose_write_scope
from procurement.models import Warehouse,WarehouseLocation

@transaction.atomic
def configure_test_finished_goods_receiving(*,user,account_id,warehouse_code,warehouse_name,location_code,location_name,reason,request_identity):
    authorization=admin(user)
    from .test_operation_start_service import _boundary
    _boundary()
    if not isinstance(reason,str) or not 2<=len(reason.strip())<=300 or not request_identity:
        fail('FG_CONFIG_REASON_REQUIRED','TEST成品资源维护须有明确原因和请求标识。',400)
    for value,size in ((warehouse_code,50),(warehouse_name,100),(location_code,80),(location_name,120)):
        if not isinstance(value,str) or not 1<=len(value.strip())<=size:fail('FG_CONFIG_RESOURCE_REQUIRED','请明确填写测试仓及库位编码名称，不自动猜填。',400)
    people=list(formal_employee_queryset(company_id=user.company_id).filter(user_id=account_id).select_related('position_ref','department_ref','user')[:2])
    if len(people)!=1 or people[0].user.is_superuser or not people[0].user.is_active:
        fail('FG_CONFIG_ACTOR_REQUIRED','须选择本公司唯一既有普通在职仓管账号。',403)
    employee=people[0]
    # Existing warehouse I/O duty is mandatory; no title inference or fabricated duty.
    from system.models import PositionResponsibility
    if not PositionResponsibility.objects.filter(position=employee.position_ref,active=True,responsibility__code=DUTY,
        responsibility__status='ACTIVE',responsibility__is_active=True).exists():
        fail('FG_CONFIG_WAREHOUSE_DUTY_REQUIRED','所选岗位尚无既有仓库出入库职责。',403)
    original={x.pk:x.definition_hash for x in ProcessDefinition.objects.all()}
    permission=Permission.objects.filter(code=RECEIVE).first()
    if not permission:
        permission=Permission.objects.create(code=RECEIVE,name='TEST生产成品接收并入库',module='WMS')
        WorkflowDefinitionOperatingService._audit(user=user,action='REGISTER_TEST_PRODUCTION_PUTAWAY_PERMISSION',target=permission,
            target_type='Permission',label=permission.name,reason=reason,before={},after={'permissionCode':RECEIVE,'configurationOnly':True})
    elif permission.module!='WMS':fail('FG_CONFIG_PERMISSION_CONFLICT','同码入库权限来源不同，不能覆盖。')
    _definition(user,dict(DEFINITION),[dict(x) for x in NODES],reason,request_identity+'-definition')
    _assign_existing_node(user,employee,PROCESS,NODE,DUTY,'EXECUTOR',reason,request_identity+'-warehouse-duty')
    label=Company.objects.get(pk=user.company_id).code+' TEST生产成品仓管'
    description='仅本人被明确指定的TEST成品单、同用途仓库入库；保留既有仓库职责，不授予管理员或正式生产资格。'
    role=Role.objects.filter(name=label).first()
    if not role:
        created=foundation(user,'SAVE_ROLE',{'name':label,'description':description},reason)
        role=Role.objects.get(pk=created['id'])
        foundation(user,'SET_ROLE_PERMISSIONS',{'roleId':role.pk,'permissionCodes':[RECEIVE]},reason)
    elif role.description!=description or set(RolePermission.objects.filter(role=role).values_list('permission__code',flat=True))!={RECEIVE}:
        fail('FG_CONFIG_ROLE_CONFLICT','既有同名角色不同，不能扩大或覆盖。')
    _append_grant(user,employee,role,reason,request_identity+'-actor')
    with test_purpose_write_scope():
        warehouse=Warehouse.all_objects.filter(code=warehouse_code.strip()).first()
        if warehouse and (warehouse.company_id!=user.company_id or warehouse.usage_purpose!=TEST or warehouse.name!=warehouse_name.strip()):
            fail('FG_CONFIG_WAREHOUSE_CONFLICT','同码仓已有其他公司或用途，不转换已有资源。')
        if warehouse is None:
            warehouse=Warehouse.all_objects.create(code=warehouse_code.strip(),name=warehouse_name.strip(),company_id=user.company_id,usage_purpose=TEST,is_active=True)
            WorkflowDefinitionOperatingService._audit(user=user,action='REGISTER_TEST_FINISHED_GOODS_WAREHOUSE',target=warehouse,
                target_type='Warehouse',label=warehouse.code,reason=reason,before={},after={'usagePurpose':TEST,'warehouseId':warehouse.pk,'configurationOnly':True})
        location=WarehouseLocation.all_objects.filter(warehouse=warehouse,code=location_code.strip()).first()
        if location and location.name!=location_name.strip():fail('FG_CONFIG_LOCATION_CONFLICT','同码库位名称不同，不覆盖。')
        if location is None:
            location=WarehouseLocation.all_objects.create(warehouse=warehouse,code=location_code.strip(),name=location_name.strip(),is_active=True)
            WorkflowDefinitionOperatingService._audit(user=user,action='REGISTER_TEST_FINISHED_GOODS_LOCATION',target=location,
                target_type='WarehouseLocation',label=location.code,reason=reason,before={},after={'warehouseId':warehouse.pk,'locationId':location.pk,'usagePurpose':TEST,'configurationOnly':True})
    for pk,old_hash in original.items():
        if ProcessDefinition.objects.get(pk=pk).definition_hash!=old_hash:fail('FG_CONFIG_EXISTING_TEMPLATE_CHANGED','既有模板被改变，事务回滚。')
    from .finished_goods_permissions import warehouse_qualification
    q=warehouse_qualification(employee.user)
    return {'configurationOnly':True,'usagePurpose':TEST,'warehouseId':warehouse.pk,'locationId':location.pk,
        'receiverUserId':employee.user_id,'receiverEmployeeId':employee.pk,'receiverRoleCode':role.code,
        'qualification':q,'existingTemplatesPreserved':len(original)}
