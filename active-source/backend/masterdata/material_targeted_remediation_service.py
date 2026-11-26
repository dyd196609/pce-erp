"""User-authorized Group 2 material remediation with exact source identity scope."""

from hashlib import sha256
import json

from django.db import transaction

from pde.production_foundation_service import ProductionFoundationService
from system.authorization import AuthorizationService
from system.master_data_executor_formalization_service import (
    EMPLOYEE_NO, ROLE_CODE, RESPONSIBILITY_CODE, USERNAME,
)
from system.models import (
    OrganizationOperatingAuditRecord, Permission, Responsibility, Role,
    RolePermission, User,
)

from .models import ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure


VERSION = "GROUP2-MATERIAL-TARGETED-REMEDIATION-V1.0"
ACTION = "production.master_data.material.maintain"
SOURCE_FILE = "05半成品板材.xlsx"
SOURCE_TYPE = "APPROVED_XLSX"
SOURCE_OBJECT_TYPE = "SEMI_FINISHED_MATERIAL_SOURCE"
EXCLUDED_CODES = ("DD4708001", "DD4708002", "DD4708003")


class MaterialRemediationError(Exception):
    pass


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


class MaterialTargetedRemediationService:
    @classmethod
    @transaction.atomic
    def extend_executor_permission(cls, *, admin):
        if not admin or not admin.is_superuser or admin.username != "admin":
            raise MaterialRemediationError("必须由技术管理员定向扩展既有职责权限。")
        role = Role.objects.select_for_update().get(code=ROLE_CODE)
        responsibility = Responsibility.objects.select_for_update().get(code=RESPONSIBILITY_CODE)
        permission, _ = Permission.objects.get_or_create(
            code=ACTION,
            defaults={"name": "定向维护已验收物料的计量单位与来源映射", "module": "PRODUCTION"},
        )
        binding, created = RolePermission.objects.get_or_create(role=role, permission=permission)
        required = (
            "当前全屋定制/整木基础数据建立阶段的最小维护职责。"
            "允许 view/create/update/activate-deactivate/source mapping/readback；"
            "对象仅限客户/经销商、供应商、UOM Mapping、Product Category，以及人工验收后"
            "Material 的查看、定向UOM更新、来源映射与回读；不含物料删除、批量新增、重命名、"
            "MAKE/BUY或Material Type任意修改。Product、BOM、Routing、WorkCenter、Capacity、Working Time、Staffing"
            "及其它制造基础资料须另行人工确认授权。"
            "不含 delete、计划发布、采购审批、生产任务下达、财务审批、组织管理、用户管理或角色管理。"
        )
        description_changed = responsibility.description != required
        if description_changed:
            before = responsibility.description
            responsibility.description = required
            responsibility.full_clean()
            responsibility.save(update_fields=["description"])
        if created or description_changed:
            OrganizationOperatingAuditRecord.objects.create(
                action_code="EXTEND_MASTER_DATA_EXECUTOR_MATERIAL_SCOPE",
                actor=admin, organization_id=admin.company_id,
                target_type="RolePermission", target_id=binding.pk,
                target_label=f"{ROLE_CODE} / {ACTION}",
                reason="用户明确授权物料人工验收后的定向整改",
                before_snapshot={"permissionBound": not created, "responsibilityDescriptionChanged": description_changed},
                after_snapshot={
                    "permissionBound": True, "responsibilityCode": RESPONSIBILITY_CODE,
                    "allowed": ["Material view", "targeted UOM update", "source mapping", "readback"],
                    "denied": ["delete", "bulk create", "rename", "arbitrary MAKE/BUY update", "arbitrary material type update"],
                    "version": VERSION,
                },
            )
        return {"permissionBound": True, "created": created, "descriptionChanged": description_changed}

    @classmethod
    def preview(cls, *, company_id):
        identities = list(ExternalIdentity.objects.filter(
            organization_id=company_id, source_system="PCE_FOUNDATION_WAVE1",
            source_type=SOURCE_TYPE, source_object_type=SOURCE_OBJECT_TYPE,
            audit_metadata__sourceFile=SOURCE_FILE, mapping_status=ExternalIdentity.MappingStatus.MATCH,
        ).order_by("audit_metadata__sourceRow"))
        if len(identities) != 58:
            raise MaterialRemediationError(f"精确来源身份数量漂移：期望58，实际{len(identities)}。")
        material_ids = [int(row.target_entity_id) for row in identities]
        materials = {row.pk: row for row in Material.objects.filter(company_id=company_id, pk__in=material_ids)}
        rows = []
        for identity in identities:
            material = materials.get(int(identity.target_entity_id))
            if not material or material.material_type != "semi" or not material.is_produced or material.is_purchased:
                raise MaterialRemediationError(f"来源身份 {identity.pk} 的正式物料边界已漂移。")
            rows.append({
                "sourceIdentityId": identity.pk,
                "sourceRow": identity.audit_metadata.get("sourceRow"),
                "sourceCode": identity.audit_metadata.get("sourceCode"),
                "materialId": material.pk, "formalCode": material.code, "formalName": material.name,
                "currentUomId": material.base_uom_id, "currentUom": material.base_uom.name if material.base_uom_id else "",
                "proposedUom": "平方米", "makeBuy": "MAKE", "materialType": "semi",
            })
        return rows

    @classmethod
    @transaction.atomic
    def execute(cls, *, admin):
        cls.extend_executor_permission(admin=admin)
        executor = User.objects.get(username=USERNAME, is_active=True)
        if not executor.employee_profile or executor.employee_profile.employee_no != EMPLOYEE_NO:
            raise MaterialRemediationError("EMP047 实名执行链缺失。")
        decision = AuthorizationService.decide(user=executor, action_code=ACTION, organization_id=executor.company_id)
        if not decision.get("allowed"):
            raise MaterialRemediationError("EMP047 未通过正式授权服务。")
        uom = UnitOfMeasure.objects.get(company_id=executor.company_id, code="m2", name="平方米", is_active=True)
        rows = cls.preview(company_id=executor.company_id)
        changed = replayed = 0
        for row in rows:
            identity = ExternalIdentity.objects.select_for_update().get(pk=row["sourceIdentityId"])
            key = f"{VERSION}:UOM:{identity.pk}"
            request = {"materialId": row["materialId"], "baseUomId": uom.pk, "unitStatus": "confirmed"}
            ledger = MasterDataWriteRequest.objects.select_for_update().filter(
                organization_id=executor.company_id, action_code=ACTION, idempotency_key=key,
            ).first()
            if ledger and ledger.status == MasterDataWriteRequest.Status.COMMITTED:
                replayed += 1
                continue
            result = ProductionFoundationService.save(
                "materials", user=executor, object_id=row["materialId"],
                payload={"base_uom_id": uom.pk, "unit_status": "confirmed", "reason": "Group 2物料人工验收后自制半成品板材UOM定向整改"},
            )
            MasterDataWriteRequest.objects.create(
                organization_id=executor.company_id, action_code=ACTION, entity_type="materials",
                idempotency_key=key, request_hash=_hash(request), source_identity=identity,
                status=MasterDataWriteRequest.Status.COMMITTED, target_entity_id=str(row["materialId"]),
                result={"materialId": row["materialId"], "uomId": uom.pk, "auditId": result["auditId"]},
                audit_metadata={"executor": USERNAME, "responsibility": RESPONSIBILITY_CODE, "version": VERSION},
            )
            changed += 1
        excluded = []
        for code, source_row in (("DD4708003", 2), ("DD4708002", 3), ("DD4708001", 5)):
            if Material.objects.filter(company_id=executor.company_id, code=code).exists():
                raise MaterialRemediationError(f"{code} 意外存在正式物料，停止排除登记。")
            identity, created = ExternalIdentity.objects.get_or_create(
                organization_id=executor.company_id, source_system="PCE_GROUP2_ACCEPTANCE",
                source_type="USER_VALIDATED_XLSX", source_object_type=SOURCE_OBJECT_TYPE,
                external_id=f"{SOURCE_FILE}|半成品板材|CODE:{code}",
                defaults={"target_entity_type": "materials", "mapping_status": ExternalIdentity.MappingStatus.BLOCK},
            )
            metadata = {
                "sourceFile": SOURCE_FILE, "sourceSheet": "半成品板材", "sourceRow": source_row,
                "sourceCode": code, "decisionStatus": "USER_EXCLUDED_INCOMPLETE_SOURCE",
                "importEligible": False, "planningEligible": False, "formalMaterialCreate": 0,
                "decisionBasis": "用户人工裁决：不再进入主数据建立流程；保留来源证据。",
            }
            if created or identity.audit_metadata != metadata or identity.mapping_status != ExternalIdentity.MappingStatus.BLOCK:
                identity.mapping_status = ExternalIdentity.MappingStatus.BLOCK
                identity.target_entity_id = ""
                identity.audit_metadata = metadata
                identity.source_fingerprint = _hash(metadata)
                identity.full_clean(); identity.save()
                OrganizationOperatingAuditRecord.objects.create(
                    action_code="EXCLUDE_INCOMPLETE_MATERIAL_SOURCE", actor=executor,
                    organization_id=executor.company_id, target_type="ExternalIdentity", target_id=identity.pk,
                    target_label=code, reason="用户明确排除不完整来源",
                    before_snapshot={}, after_snapshot={**metadata, "executionChain": {"account": USERNAME, "employeeNo": EMPLOYEE_NO, "responsibilityCode": RESPONSIBILITY_CODE}},
                )
            excluded.append(metadata)
        readback = cls.preview(company_id=executor.company_id)
        pass_count = sum(row["currentUomId"] == uom.pk for row in readback)
        if pass_count != 58:
            raise MaterialRemediationError(f"UOM回读失败：{pass_count}/58。")
        return {"changed": changed, "idempotentReplay": replayed, "targetCount": 58, "uomPassCount": pass_count, "excluded": excluded}
