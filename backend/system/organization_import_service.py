"""Governed XLSX import orchestration for departments, positions and employees.

Parsing and preview are read-only.  Confirmed writes are deliberately delegated
to OrganizationOperatingService so the normal authorization, validation and
audit trail remain authoritative.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime
from hashlib import sha256

from django.db import transaction
from django.db.models import Q
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from pfm.models import Employee, EmployeeReportingRelation

from .models import Company, Department, JobFamily, JobLevel, OrganizationUnit, Position, Role
from .organization_operating import ACTION_PERMISSIONS, OrganizationOperatingError, OrganizationOperatingService
from .authorization import AuthorizationService


class OrganizationImportError(Exception):
    def __init__(self, code, message, *, http_status=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def field(name, label, *, required=False, kind="text", choices=None, help_text="", example=""):
    return {
        "name": name,
        "label": label,
        "header": f"{label}{'*' if required else ''}",
        "required": required,
        "kind": kind,
        "choices": choices or {},
        "help": help_text,
        "example": example,
    }


ACTIVE_CHOICES = {"启用": True, "停用": False}
DEPARTMENT_TYPES = {
    "职能部门": "FUNCTIONAL", "业务部门": "BUSINESS", "生产部门": "PRODUCTION",
    "支持部门": "SUPPORT", "团队/班组": "TEAM",
}
EMPLOYEE_STATUS = {"在职": "active", "停用": "inactive", "休假": "leave", "离职": "quit"}

SCHEMAS = {
    "departments": {
        "label": "部门", "sheet": "部门导入", "identity": "code", "action": "SAVE_DEPARTMENT",
        "fields": [
            field("code", "部门编码", required=True, help_text="沿用正式部门编码规则；当前模型不自动生成。", example="DEPT-001"),
            field("name", "部门名称", required=True, example="生产管理部"),
            field("company_code", "所属公司编码", required=True, help_text="必须为当前登录公司。", example="COMPANY-01"),
            field("department_type", "部门类型", required=True, choices=DEPARTMENT_TYPES, example="生产部门"),
            field("parent_code", "上级部门编码", help_text="可引用同一文件中先后任意位置的部门。", example="DEPT-ROOT"),
            field("organization_unit_code", "所属组织单元编码", example="OU-001"),
            field("responsible_position_code", "责任岗位编码", example="POS-001"),
            field("effective_from", "生效日期", kind="date", example="2026-09-14"),
            field("effective_to", "失效日期", kind="date", example="2027-12-31"),
            field("is_active", "有效状态", required=True, choices=ACTIVE_CHOICES, example="启用"),
        ],
    },
    "positions": {
        "label": "岗位", "sheet": "岗位导入", "identity": "code", "action": "SAVE_POSITION",
        "fields": [
            field("code", "岗位编码", required=True, help_text="沿用正式岗位编码规则；当前模型不自动生成。", example="POS-001"),
            field("name", "岗位名称", required=True, example="工程师"),
            field("company_code", "所属公司编码", required=True, help_text="必须为当前登录公司。", example="COMPANY-01"),
            field("department_code", "所属部门编码", required=True, example="DEPT-001"),
            field("job_family_code", "岗位族编码", example="JF-001"),
            field("job_level_code", "岗位等级编码", example="JL-01"),
            field("parent_position_code", "上级岗位编码", help_text="可引用同一文件中的岗位。", example="POS-ROOT"),
            field("default_role_code", "默认角色编码", help_text="仅引用已有角色；导入不会创建或授权角色。", example="engineer"),
            field("description", "岗位说明", example="负责工程设计"),
            field("responsibility_summary", "岗位职责摘要", example="工程核算与拆单"),
            field("effective_from", "生效日期", kind="date", example="2026-09-14"),
            field("effective_to", "失效日期", kind="date", example="2027-12-31"),
            field("is_active", "有效状态", required=True, choices=ACTIVE_CHOICES, example="启用"),
        ],
    },
    "employees": {
        "label": "员工", "sheet": "员工导入", "identity": "employee_no", "action": "SAVE_EMPLOYEE",
        "fields": [
            field("employee_no", "员工编号", required=True, help_text="沿用正式工号规则；导入不会创建登录账号。", example="EMP-001"),
            field("full_name", "姓名", required=True, example="张三"),
            field("company_code", "所属公司编码", required=True, help_text="必须为当前登录公司。", example="COMPANY-01"),
            field("department_code", "所属部门编码", required=True, example="DEPT-001"),
            field("position_code", "所属岗位编码", required=True, example="POS-001"),
            field("status", "在职状态", required=True, choices=EMPLOYEE_STATUS, example="在职"),
            field("phone", "联系电话", help_text="非建档必需，可留空。", example="13800000000"),
            field("direct_manager_employee_no", "直属主管工号", help_text="可引用同一文件中的员工。", example="EMP-ROOT"),
            field("manager_effective_from", "主管关系生效日期", kind="date", example="2026-09-14"),
            field("manager_effective_to", "主管关系失效日期", kind="date", example="2027-12-31"),
        ],
    },
}


REFERENCE_LABELS = {
    'company_code': '所属公司', 'parent_code': '上级部门', 'organization_unit_code': '所属组织单元',
    'responsible_position_code': '责任岗位', 'department_code': '所属部门', 'position_code': '正式岗位',
    'job_family_code': '岗位族', 'job_level_code': '岗位等级', 'parent_position_code': '上级岗位',
    'default_role_code': '默认角色', 'direct_manager_employee_no': '直属主管',
}
for entity, schema in SCHEMAS.items():
    for item in schema['fields']:
        item['aliases'] = [item['header'], item['label']]
        if item['name'] in REFERENCE_LABELS:
            item['label'] = '正式部门' if entity == 'employees' and item['name'] == 'department_code' else REFERENCE_LABELS[item['name']]
            item['header'] = item['label'] + ('*' if item['required'] else '')
            item['help'] = '填写引用资料中的完整编码或唯一名称；名称与编码有歧义时须确认。' + ('可留空，不清除已有关系。' if not item['required'] else '')
        if item['name'] == 'company_code':
            item['help'] = '使用下载前显示的目标公司编码或准确名称；由正式维护权限再次校验。'

READ_ONLY_FIELDS = {
    'departments': [('实际负责人', '部门管理的负责人维护，需明确任命，不随本次新增导入'), ('序号、操作', '页面显示，不导入')],
    'positions': [('任职人数', '按员工任职关系统计，不导入'), ('序号、操作', '页面显示，不导入')],
    'employees': [('职能主管', '员工汇报关系维护，不随本次员工新增导入'), ('关联登录账户', '员工账户关联维护，不自动建号或授权'), ('序号、操作', '页面显示，不导入')],
}


class OrganizationImportService:
    VERSION = "PCE-ORGANIZATION-IMPORT-V1.1"
    DEPARTMENT_SOURCE_DECISIONS = {
        "MGC": "REFERENCE_EXISTING_NO_CHANGE",
        "KLG": "PROCESS_TEAM_SEPARATION_REVIEW",
        "PPG": "PROCESS_TEAM_SEPARATION_REVIEW",
    }
    MAX_BYTES = 5 * 1024 * 1024
    MAX_ROWS = 1000

    @classmethod
    def schema(cls, entity):
        schema = SCHEMAS.get(entity)
        if not schema:
            raise OrganizationImportError("IMPORT_ENTITY_NOT_APPLICABLE", "仅支持部门、岗位和员工档案导入。")
        return schema

    @staticmethod
    def actor_binding(user):
        return {"userId": user.pk, "username": user.username, "companyId": user.company_id}

    @classmethod
    def target_context(cls, entity, user):
        company = Company.objects.get(pk=user.company_id)
        permission = ACTION_PERMISSIONS[cls.schema(entity)['action']]
        decision = AuthorizationService.decide(user=user, action_code=permission, organization_id=str(company.pk))
        allowed = bool(user.is_superuser and company.is_active and decision['allowed'])
        # The canonical maintenance service writes in the actor's current company.
        # Read scope across companies is not a second writable context.
        return {'targetCompany': {'id':company.pk,'code':company.code,'name':company.name},
                'allowed':allowed,'requiredPermission':permission,
                'reason': '原组织维护链仅接受当前业务公司；查看其他公司不代表可跨公司导入。' if allowed else decision.get('reason') or '当前身份没有组织导入维护资格。',
                'readOnlyFields':READ_ONLY_FIELDS[entity]}

    @classmethod
    def _target(cls, entity, value, user):
        candidates=list(Company.objects.filter(Q(code=value)|Q(name=value))[:3])
        context=cls.target_context(entity,user)
        target=context['targetCompany']
        suggestion=f"本次目标公司为{target['name']}（{target['code']}）；确认目标正确后填写该编码或准确名称。"
        if len(candidates)!=1:
            return None, '公司名称或编码没有唯一匹配，目标公司未确定。', suggestion
        company=candidates[0]
        decision=AuthorizationService.decide(user=user,action_code=ACTION_PERMISSIONS[cls.schema(entity)['action']],organization_id=str(company.pk))
        if not user.is_superuser or not decision['allowed']:
            return None, '当前账号未通过该目标公司的正式维护授权。', '请使用已有合法组织维护身份；所需权限：'+context['requiredPermission']+'。'
        if company.pk != user.company_id or not company.is_active:
            return None, '所填公司不在当前正式维护链允许的写入范围。', suggestion
        return company, None, None

    @classmethod
    def template_bytes(cls, entity, *, user):
        schema = cls.schema(entity)
        context=cls.target_context(entity,user)
        if not context['allowed']:
            raise OrganizationImportError('IMPORT_TARGET_FORBIDDEN',context['reason'],http_status=403)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = schema["sheet"]
        sheet.append([item["header"] for item in schema["fields"]])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = f"A1:{sheet.cell(1, len(schema['fields'])).column_letter}1"
        header_fill = PatternFill("solid", fgColor="1F4E78")
        for index, item in enumerate(schema["fields"], 1):
            cell = sheet.cell(1, index)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            sheet.column_dimensions[cell.column_letter].width = min(32, max(15, len(item["header"]) * 2 + 5))
            if item["choices"]:
                formula = '"' + ",".join(item["choices"].keys()) + '"'
                validation = DataValidation(type="list", formula1=formula, allow_blank=not item["required"])
                validation.errorTitle = "取值无效"
                validation.error = f"请选择{item['label']}的允许值。"
                sheet.add_data_validation(validation)
                validation.add(f"{cell.column_letter}2:{cell.column_letter}{cls.MAX_ROWS + 1}")
        instructions = workbook.create_sheet("填写说明")
        instructions.append(["模板版本", cls.VERSION])
        instructions.append(["重要说明", "主数据填写区必须从第2行开始；本说明页示例不会导入。导入不会创建账号、角色或权限。"])
        instructions.append(['目标公司',context['targetCompany']['name']+'（'+context['targetCompany']['code']+'）'])
        instructions.append([])
        instructions.append(["列名", "是否必填", "允许值/填写说明", "独立示例（不会导入）"])
        for item in schema["fields"]:
            allowed = "、".join(item["choices"].keys()) if item["choices"] else item["help"]
            instructions.append([item["label"], "是" if item["required"] else "否", allowed, item["example"]])
        for label, help_text in READ_ONLY_FIELDS[entity]:
            instructions.append([label,'不导入',help_text,''])
        instructions.append(['旧模板兼容','支持','原V1.0列名仍可按名称映射，列顺序可调整；未知列明确报错，不丢弃内容。',''])
        references = workbook.create_sheet("引用资料")
        references.append(["资料类型", "业务编码", "名称", "状态", "说明"])
        for row in cls._reference_rows(entity, user):
            references.append(row)
        for ws in (instructions, references):
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
            for col, width in zip("ABCDE", (20, 24, 30, 12, 48)):
                ws.column_dimensions[col].width = width
            for cells in ws:
                for cell in cells:
                    cell.alignment=Alignment(wrap_text=True,vertical='top')
                ws.row_dimensions[cells[0].row].height=max(32, min(150, 18*(1+max(len(str(c.value or ''))//22 for c in cells))))
        instructions.column_dimensions['C'].width=66
        instructions.column_dimensions['D'].width=28
        # These three explanatory values are not tabular data. Let them use
        # the full explanation width without changing the import header row.
        for row_number in (1, 2, 3):
            instructions.merge_cells(start_row=row_number,start_column=2,end_row=row_number,end_column=4)
            instructions.row_dimensions[row_number].height=36
        stream = io.BytesIO()
        workbook.save(stream)
        return stream.getvalue()

    @classmethod
    def _reference_rows(cls, entity, user):
        company = Company.objects.get(pk=user.company_id)
        rows = [["所属公司", company.code, company.name, "启用" if company.is_active else "停用", "只允许导入当前登录公司范围"]]
        def extend(label, queryset):
            for item in queryset:
                rows.append([label, item.code, item.name, "启用", "当前账号所在公司可见的有效资料"])
        if entity == "departments":
            extend("上级部门", Department.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            extend("组织单元", OrganizationUnit.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            extend("责任岗位", Position.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
        elif entity == "positions":
            extend("所属部门", Department.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            extend("岗位族", JobFamily.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            extend("岗位等级", JobLevel.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            extend("上级岗位", Position.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            for item in Role.objects.order_by("code"):
                rows.append(["默认角色", item.code, item.name, "可引用", "仅引用，不创建或授权"])
        else:
            extend("所属部门", Department.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            extend("所属岗位", Position.objects.filter(company_id=user.company_id, is_active=True).order_by("code"))
            for item in Employee.objects.filter(department_ref__company_id=user.company_id, status="active").order_by("employee_no"):
                rows.append(["直属主管", item.employee_no, item.full_name, item.get_status_display(), "仅建立员工汇报关系，不授予权限"])
        return rows

    @classmethod
    def _read_file(cls, uploaded_file):
        name = str(getattr(uploaded_file, "name", "") or "")
        content = uploaded_file.read()
        if not name.lower().endswith(".xlsx"):
            raise OrganizationImportError("IMPORT_FILE_TYPE_UNSUPPORTED", "仅支持当前页面下载的.xlsx模板。")
        if len(content) > cls.MAX_BYTES:
            raise OrganizationImportError("IMPORT_FILE_TOO_LARGE", "导入文件不能超过5MB。")
        if not content.startswith(b"PK\x03\x04"):
            raise OrganizationImportError("IMPORT_FILE_SIGNATURE_INVALID", "文件不是有效的.xlsx工作簿。")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = [name.lower() for name in archive.namelist()]
                if sum(item.file_size for item in archive.infolist()) > 25 * 1024 * 1024:
                    raise OrganizationImportError("IMPORT_FILE_EXPANDED_TOO_LARGE", "工作簿解压内容超过25MB限制。")
                if any("vbaproject" in name or name.startswith("xl/externallinks/") for name in names):
                    raise OrganizationImportError("UNSAFE_WORKBOOK_CONTENT", "模板不得包含宏或外部链接。")
        except zipfile.BadZipFile as exc:
            raise OrganizationImportError("IMPORT_FILE_INVALID", "文件不是有效的Excel工作簿。") from exc
        return name, content

    @classmethod
    def _parse(cls, schema, content):
        try:
            workbook = load_workbook(io.BytesIO(content), data_only=False, read_only=False, keep_links=False)
        except Exception as exc:
            raise OrganizationImportError("IMPORT_FILE_INVALID", "无法读取Excel文件，请重新下载当前模板。") from exc
        expected = {schema["sheet"], "填写说明", "引用资料"}
        if set(workbook.sheetnames) != expected:
            raise OrganizationImportError("WORKSHEET_MISMATCH", f"工作表必须为：{'、'.join(sorted(expected))}。")
        sheet = workbook[schema["sheet"]]
        actual = [str(cell.value or "").strip() for cell in sheet[1]]
        aliases={alias.rstrip('*'):item['name'] for item in schema['fields'] for alias in [item['header'],item['label'],*item.get('aliases',[])]}
        mapped=[aliases.get(label.rstrip('*')) for label in actual]
        unknown=[label for label,key in zip(actual,mapped) if not key]
        missing=[item['label'] for item in schema['fields'] if item['name'] not in mapped]
        if unknown or missing or len(mapped)!=len(set(mapped)):
            raise OrganizationImportError('SCHEMA_MISMATCH','模板列无法对应：'+('未知列：'+'、'.join(unknown)+'。' if unknown else '')+('缺少列：'+'、'.join(missing)+'。' if missing else '')+('同一业务字段重复出现。' if len(mapped)!=len(set(mapped)) else ''))
        rows = []
        for row_number, cells in enumerate(sheet.iter_rows(min_row=2), 2):
            if row_number > cls.MAX_ROWS + 1:
                if any(cell.value not in (None, "") for cell in cells):
                    raise OrganizationImportError("IMPORT_ROW_LIMIT", "单次最多导入1000行。")
                break
            if any(cell.data_type == "f" or cell.hyperlink for cell in cells):
                raise OrganizationImportError("UNSAFE_CELL_CONTENT", f"第{row_number}行包含公式或外部链接，不予执行。")
            values = [cell.value for cell in cells[:len(mapped)]]
            if any(value not in (None, "") for value in values):
                rows.append((row_number, dict(zip(mapped, values))))
        if not rows:
            raise OrganizationImportError("IMPORT_FILE_EMPTY", "填写区没有待导入记录。")
        return rows

    @staticmethod
    def _error(row, field_name, code, message, suggested="修正后重新预览。"):
        return {"rowNumber": row, "field": field_name, "fieldLabel": field_name, "errorType": code, "message": message, "suggestedAction": suggested}

    @staticmethod
    def _date(value, label):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise ValueError(f"{label}必须为YYYY-MM-DD日期。") from exc

    @classmethod
    def _convert(cls, item, value):
        if value in (None, ""):
            return None
        if item["kind"] == "date":
            return cls._date(value, item["label"])
        text = str(value).strip()
        if item["choices"]:
            if text not in item["choices"]:
                raise ValueError(f"{item['label']}必须为：{'、'.join(item['choices'])}。")
            return item["choices"][text]
        return text

    @classmethod
    def preview(cls, entity, *, uploaded_file, user):
        schema = cls.schema(entity)
        name, content = cls._read_file(uploaded_file)
        parsed = cls._parse(schema, content)
        binding = cls.actor_binding(user)
        fingerprint = sha256(entity.encode() + b"\0" + content + b"\0" + json.dumps(binding, sort_keys=True).encode()).hexdigest()
        file_identities = {str(raw.get(schema["identity"]) or "").strip() for _, raw in parsed}
        file_names={}
        for _, raw in parsed:
            file_names.setdefault(str(raw.get('name' if entity!='employees' else 'full_name') or '').strip(),set()).add(str(raw.get(schema['identity']) or '').strip())
        seen = set()
        results = []
        for row_number, raw in parsed:
            data, errors, notes = {}, [], []
            for item in schema["fields"]:
                try:
                    value = cls._convert(item, raw.get(item["name"]))
                except ValueError as exc:
                    errors.append(cls._error(row_number, item["label"], "TYPE_OR_ENUM_INVALID", str(exc)))
                    continue
                if item["required"] and value in (None, ""):
                    errors.append(cls._error(row_number, item["label"], "REQUIRED", f"{item['label']}不能为空。"))
                data[item["name"]] = value
            identity = str(data.get(schema["identity"]) or "")
            if identity in seen:
                errors.append(cls._error(row_number, schema["identity"], "DUPLICATE_IN_FILE", "文件内业务编码重复。"))
            seen.add(identity)
            company, reason, suggestion = cls._target(entity,data.get('company_code'),user)
            source_decision = None
            if company:
                if data['company_code'] != company.code:
                    notes.append({'fieldLabel':'所属公司','rawValue':data['company_code'],'resolvedValue':company.name+'（'+company.code+'）','message':'按准确名称唯一匹配正式公司。'})
                data['company_code']=company.code
                if entity == "departments" and company.code == "COMP001":
                    source_decision = cls.DEPARTMENT_SOURCE_DECISIONS.get(identity)
                # Keep stable parent/reference resolution even when the source
                # row is excluded from department persistence.  This lets
                # KLG/PPG continue to point at the existing MGC identity and
                # lets the MGC no-change row show every excluded difference.
                cls._normalize_references(
                    entity, data, row_number, errors, notes,
                    company.pk, file_identities, file_names,
                )
                if source_decision == "REFERENCE_EXISTING_NO_CHANGE":
                    notes.append({
                        'fieldLabel': '本次业务裁决',
                        'rawValue': identity,
                        'resolvedValue': '引用已有部门，不修改',
                        'message': 'MGC仅用于上级解析；原文件中的组织单元、有效期等差异均不进入本次更新。',
                    })
                elif source_decision == "PROCESS_TEAM_SEPARATION_REVIEW":
                    notes.append({
                        'fieldLabel': '本次业务裁决',
                        'rawValue': f"{identity} / {data.get('name') or ''}",
                        'resolvedValue': '不按部门或工序自动新增',
                        'message': '开料、拼皮工序与实际班组分别维护；来源标识不能直接充当正式班组编码。',
                    })
            else:
                errors.append(cls._error(row_number,'company_code','TARGET_COMPANY_UNRESOLVED',reason,suggestion))
                notes.append({'fieldLabel':'引用校验','message':'目标公司未确定，组织单元、部门和岗位等引用暂无法校验。'})
            cls._validate_dates(data, row_number, errors)
            if company and not source_decision:
                cls._validate_references(entity, data, row_number, errors, company.pk, file_identities)
            existing = cls._existing(entity, identity, company.pk) if identity and company else None
            if company and not source_decision and entity == "departments" and data.get("name") and Department.objects.filter(company_id=user.company_id, name=data["name"]).exclude(code=identity).exists():
                errors.append(cls._error(row_number, "部门名称", "IDENTITY_CONFLICT", "当前公司已存在同名但不同编码的部门。", "人工核对正式部门编码。"))
            if company and entity == "positions" and identity and Position.objects.filter(code=identity).exclude(company_id=user.company_id).exists():
                errors.append(cls._error(row_number, "岗位编码", "CROSS_SCOPE_CONFLICT", "该岗位编码已被其他公司使用。"))
            if company and entity == "positions" and data.get("name") and Position.objects.filter(name=data["name"]).exclude(code=identity).exists():
                errors.append(cls._error(row_number, "岗位名称", "IDENTITY_CONFLICT", "正式模型中已存在同名但不同编码的岗位。"))
            if company and entity == "employees" and identity and Employee.objects.filter(employee_no=identity).exclude(department_ref__company_id=user.company_id).exists():
                errors.append(cls._error(row_number, "员工编号", "CROSS_SCOPE_CONFLICT", "该员工编号已被其他公司使用。"))
            decision, state = "CREATE", "READY"
            differences=[]
            if source_decision == "REFERENCE_EXISTING_NO_CHANGE":
                if existing and existing.name == "木工车间":
                    decision, state = "REFERENCE", "READY"
                    differences = cls._differences(entity, existing, data, user.company_id)
                    for difference in differences:
                        difference['impact'] = '依据用户裁决排除：保留已有MGC身份、关系和日期，不执行更新。'
                        notes.append({
                            'fieldLabel': difference['fieldLabel'],
                            'rawValue': difference['inputValue'],
                            'resolvedValue': difference['existingValue'],
                            'message': difference['impact'],
                        })
                else:
                    decision, state = "REFERENCE", "BLOCKED"
                    errors.append(cls._error(
                        row_number, "code", "MGC_REFERENCE_NOT_FOUND",
                        "当前合法公司范围内没有找到稳定身份为MGC／木工车间的已有部门。",
                        "先在部门管理核对既有MGC；不得通过本文件新建同名部门。",
                    ))
            elif source_decision == "PROCESS_TEAM_SEPARATION_REVIEW":
                decision, state = "EXCLUDED", "BLOCKED"
                errors.append(cls._error(
                    row_number, "code", "TEAM_DETAILS_REQUIRED",
                    "该来源行同时带有工序与班组语义，不能作为部门或工序自动新增。",
                    "请补充实际班组名称、所属车间和承担工序后，在班组及工序班组能力入口维护。",
                ))
            elif existing:
                differences=cls._differences(entity,existing,data,user.company_id)
                if not differences:
                    decision = "MATCH"
                else:
                    decision, state = "CONFLICT", "REVIEW"
                    for difference in differences:
                        error=cls._error(row_number,difference['field'],'IDENTITY_CONFLICT','已有记录与本次填写不同；保留已有记录，不执行更新。','请核对已有值与本次值；确需修改时在原维护页面明确保存，本批不覆盖。')
                        error['resolvedValue']=difference['existingValue']; errors.append(error)
            if any(error['errorType']!='IDENTITY_CONFLICT' for error in errors):
                state = "BLOCKED"
            results.append({
                "rowNumber": row_number, "identity": identity, 'objectName':data.get('name') or data.get('full_name') or '', 'rawData':cls._json_data(raw), "data": cls._json_data(data),
                'normalizations':notes, 'differences':differences, 'existingId':existing.pk if existing else None,
                "displayData": [{"label": item["label"], "value": cls._display(item, data.get(item["name"]))} for item in schema["fields"][:6]],
                "state": state, "stateLabel": {"READY": "可导入", "REVIEW": "需复核", "BLOCKED": "已阻断"}[state],
                "decision": decision, "decisionLabel": {"CREATE": "拟新增", "MATCH": "匹配已有，跳过创建", "CONFLICT": "已有记录待复核", "REFERENCE": "引用已有，不修改", "EXCLUDED": "不作为部门导入"}[decision],
                "errors": errors,
            })
        cls._validate_cycles(entity, results)
        by_id={row['identity']:row for row in results}
        parent_key={'departments':'parent_code','positions':'parent_position_code','employees':'direct_manager_employee_no'}[entity]
        for _ in range(len(results)):
            changed=False
            for row in results:
                parent=by_id.get(row['data'].get(parent_key))
                if parent and parent['state']!='READY' and not parent['existingId'] and row['state']=='READY':
                    row['errors'].append(cls._error(row['rowNumber'],parent_key,'PARENT_NOT_READY','同文件上级尚未通过校验，不能建立关联。','先处理上级 '+parent['identity']+' 的具体问题，再重新预览。'))
                    row['state']='BLOCKED'; row['stateLabel']='已阻断'; changed=True
            if not changed: break
        labels={item['name']:item for item in schema['fields']}
        for row in results:
            for error in row['errors']:
                item=labels.get(error['field']) or next((f for f in schema['fields'] if error['field'] in [f['label'],*f.get('aliases',[])]),None)
                error['fieldLabel']=item['label'] if item else error['field']
                error['rawValue']=cls._display(item,row['rawData'].get(item['name'])) if item else ''
                error.setdefault('resolvedValue',cls._display(item,row['data'].get(item['name'])) if item else '')
                error['objectCode']=row['identity']; error['objectName']=row['objectName']
        errors = [item for row in results for item in row["errors"]]
        counts = {
            "total": len(results), "ready": sum(r["state"] == "READY" for r in results),
            "review": sum(r["state"] == "REVIEW" for r in results), "blocked": sum(r["state"] == "BLOCKED" for r in results),
            "create": sum(r["decision"] == "CREATE" and r['state']=='READY' for r in results), "match": sum(r["decision"] == "MATCH" and r['state']=='READY' for r in results),
            "reference": sum(r["decision"] == "REFERENCE" and r['state']=='READY' for r in results),
            "excluded": sum(r["decision"] == "EXCLUDED" for r in results),
            'errorRows':sum(bool(r['errors']) for r in results),
            "validationErrors": len(errors), "identityConflicts": sum(r["decision"] == "CONFLICT" for r in results),
        }
        return {
            "entity": entity, "schemaVersion": cls.VERSION, "fileName": name, "fileType": "xlsx", "worksheetName": schema["sheet"],
            "previewFingerprint": fingerprint, "previewActorBinding": binding, "writeCount": 0, "counts": counts,
            "canCommit": bool(results) and not errors, "rows": results, "errors": errors, "warnings": [], 'targetContext':cls.target_context(entity,user),
        }, content

    @classmethod
    def _normalize_references(cls,entity,data,row,errors,notes,company_id,same_file,file_names):
        specs={'departments':[('parent_code',Department,True),('organization_unit_code',OrganizationUnit,False),('responsible_position_code',Position,False)],
               'positions':[('department_code',Department,False),('job_family_code',JobFamily,False),('job_level_code',JobLevel,False),('parent_position_code',Position,True),('default_role_code',Role,False)],
               'employees':[('department_code',Department,False),('position_code',Position,False),('direct_manager_employee_no',Employee,True)]}[entity]
        for key,model,allow_file in specs:
            value=data.get(key)
            if not value: continue
            optional=not next(f for f in SCHEMAS[entity]['fields'] if f['name']==key)['required']
            if optional and value=='待维护':
                data[key]=None
                notes.append({'fieldLabel':REFERENCE_LABELS[key],'rawValue':value,'resolvedValue':'未填写','message':'本字段可选；“待维护”不是正式对象，按未填写处理，已有关系不会被清除。'})
                continue
            if model==Employee:
                qs=Employee.objects.filter(department_ref__company_id=company_id,status='active'); code_key='employee_no'; name_key='full_name'
            else:
                qs=model.objects.all(); code_key='code'; name_key='name'
                if hasattr(model,'company'): qs=qs.filter(company_id=company_id)
                if hasattr(model,'is_active'): qs=qs.filter(is_active=True)
            candidates=list(qs.filter(Q(**{code_key:value})|Q(**{name_key:value}))[:3])
            codes={getattr(o,code_key) for o in candidates}
            if allow_file:
                codes |= ({value} if value in same_file else set()) | file_names.get(value,set())
            if len(codes)>1:
                errors.append(cls._error(row,key,'REFERENCE_AMBIGUOUS',f'{REFERENCE_LABELS[key]}的名称和编码匹配多个对象。','请从引用资料选择唯一业务编码，不使用有歧义的名称。'))
            elif len(codes)==1:
                resolved=next(iter(codes)); data[key]=resolved
                if resolved!=value: notes.append({'fieldLabel':REFERENCE_LABELS[key],'rawValue':value,'resolvedValue':resolved,'message':'按准确名称唯一匹配；保存正式身份。'})

    @classmethod
    def _differences(cls,entity,row,data,company_id):
        payload=cls._payload(entity,data,company_id)
        maps={
            'departments':{'name':('name','name'),'department_type':('departmentType','department_type'),'parent_code':('parentId','parent_id'),'organization_unit_code':('organizationUnitId','organization_unit_id'),'responsible_position_code':('responsiblePositionId','responsible_position_id'),'effective_from':('effectiveFrom','effective_from'),'effective_to':('effectiveTo','effective_to'),'is_active':('active','is_active')},
            'positions':{'name':('name','name'),'department_code':('departmentId','department_id'),'job_family_code':('jobFamilyId','job_family_id'),'job_level_code':('jobLevelId','job_level_id'),'parent_position_code':('parentPositionId','parent_position_id'),'default_role_code':('defaultRoleId','default_role_id'),'description':('description','description'),'responsibility_summary':('responsibilitySummary','responsibility_summary'),'effective_from':('effectiveFrom','effective_from'),'effective_to':('effectiveTo','effective_to'),'is_active':('active','is_active')},
            'employees':{'full_name':('fullName','full_name'),'department_code':('departmentId','department_ref_id'),'position_code':('positionId','position_ref_id'),'status':('status','status'),'phone':('phone','phone')},
        }[entity]
        differences=[]
        for key,(payload_key,attr) in maps.items():
            old=getattr(row,attr); new=payload.get(payload_key)
            comparable=lambda v:v.isoformat() if isinstance(v,(date,datetime)) else (v or '' if not isinstance(v,bool) else v)
            if comparable(old)==comparable(new): continue
            item=next(f for f in SCHEMAS[entity]['fields'] if f['name']==key)
            display=old
            if attr.endswith('_id') and old:
                related=getattr(row,attr[:-3]); display=f"{getattr(related,'name','')}（{getattr(related,'code','')}）"
            differences.append({'field':key,'fieldLabel':item['label'],'existingValue':cls._display(item,display),'inputValue':cls._display(item,data.get(key)),'impact':'不更新、不删除已有记录；需人工核对。'})
        if entity=='employees' and data.get('direct_manager_employee_no'):
            relation=EmployeeReportingRelation.objects.filter(employee=row,relation_type='DIRECT',active=True,is_primary=True).select_related('manager').first()
            existing=relation.manager.employee_no if relation else ''
            if existing!=data['direct_manager_employee_no'] or (relation and (relation.effective_from!=data.get('manager_effective_from') or relation.effective_to!=data.get('manager_effective_to'))):
                differences.append({'field':'direct_manager_employee_no','fieldLabel':'直属主管','existingValue':existing,'inputValue':data['direct_manager_employee_no'],'impact':'请使用原主管关系维护入口明确修改。'})
        return differences

    @classmethod
    def _validate_dates(cls, data, row, errors):
        pairs = [("effective_from", "effective_to"), ("manager_effective_from", "manager_effective_to")]
        for start, end in pairs:
            if data.get(start) and data.get(end) and data[end] < data[start]:
                errors.append(cls._error(row, end, "INVALID_EFFECTIVE_PERIOD", "结束日期不能早于开始日期。"))

    @classmethod
    def _lookup(cls, model, code, company_id, *, active=True):
        if not code:
            return None
        qs = model.objects.filter(code=code)
        if hasattr(model, "company"):
            qs = qs.filter(company_id=company_id)
        if active and hasattr(model, "is_active"):
            qs = qs.filter(is_active=True)
        if active and hasattr(model,'effective_from'):
            qs=qs.filter(Q(effective_from__isnull=True)|Q(effective_from__lte=date.today()))
        if active and hasattr(model,'effective_to'):
            qs=qs.filter(Q(effective_to__isnull=True)|Q(effective_to__gte=date.today()))
        return qs.first()

    @classmethod
    def _validate_references(cls, entity, data, row, errors, company_id, same_file):
        checks = []
        if entity == "departments":
            checks = [("parent_code", Department, True), ("organization_unit_code", OrganizationUnit, False), ("responsible_position_code", Position, False)]
        elif entity == "positions":
            checks = [("department_code", Department, False), ("job_family_code", JobFamily, False), ("job_level_code", JobLevel, False), ("parent_position_code", Position, True)]
            role = data.get("default_role_code")
            if role and not Role.objects.filter(code=role).exists():
                errors.append(cls._error(row, "默认角色编码", "REFERENCE_NOT_FOUND", f"默认角色不存在：{role}"))
        else:
            checks = [("department_code", Department, False), ("position_code", Position, False)]
            manager = data.get("direct_manager_employee_no")
            if manager and manager not in same_file and not Employee.objects.filter(employee_no=manager, department_ref__company_id=company_id, status="active").exists():
                errors.append(cls._error(row, "直属主管工号", "REFERENCE_NOT_FOUND", f"当前公司有效主管不存在：{manager}"))
        for key, model, allow_same in checks:
            code = data.get(key)
            if code and not (allow_same and code in same_file) and not cls._lookup(model, code, company_id):
                optional=not next(item for item in SCHEMAS[entity]['fields'] if item['name']==key)['required']
                errors.append(cls._error(row, key, "REFERENCE_NOT_FOUND", f"目标公司中没有启用且在有效期内的{REFERENCE_LABELS[key]}：{code}。", '请从本模板引用资料选择已有名称或编码。'+('本项可选，如不建立此关联可留空；不会自动清除已有关系。' if optional else '本项必填，不能用新建其他对象绕过引用。')))
        if entity == "employees":
            dept = cls._lookup(Department, data.get("department_code"), company_id)
            position = cls._lookup(Position, data.get("position_code"), company_id)
            if dept and position and position.department_id != dept.pk:
                errors.append(cls._error(row, "所属岗位编码", "INVALID_RELATION", "岗位不属于所选部门。"))

    @classmethod
    def _validate_cycles(cls, entity, rows):
        parent_key = {"departments": "parent_code", "positions": "parent_position_code", "employees": "direct_manager_employee_no"}.get(entity)
        if not parent_key:
            return
        graph = {row["identity"]: row["data"].get(parent_key) for row in rows if row["identity"]}
        for row in rows:
            start, seen, current = row["identity"], set(), row["identity"]
            while current in graph and graph[current]:
                if current in seen or graph[current] == start:
                    error = cls._error(row["rowNumber"], parent_key, "HIERARCHY_CYCLE", "文件内上下级关系形成循环。")
                    row["errors"].append(error); row["state"] = "BLOCKED"; row["stateLabel"] = "已阻断"
                    break
                seen.add(current); current = graph[current]

    @staticmethod
    def _existing(entity, identity, company_id):
        if entity == "departments": return Department.objects.filter(code=identity, company_id=company_id).first()
        if entity == "positions": return Position.objects.filter(code=identity, company_id=company_id).first()
        return Employee.objects.filter(employee_no=identity, department_ref__company_id=company_id).first()

    @classmethod
    def _matches(cls, entity, row, data, company_id):
        def code(model, value):
            found = cls._lookup(model, value, company_id, active=False)
            return found.pk if found else None
        if entity == "departments":
            expected = (data.get("name"), data.get("department_type"), code(Department, data.get("parent_code")), code(OrganizationUnit, data.get("organization_unit_code")), code(Position, data.get("responsible_position_code")), data.get("effective_from"), data.get("effective_to"), data.get("is_active"))
            actual = (row.name, row.department_type, row.parent_id, row.organization_unit_id, row.responsible_position_id, row.effective_from, row.effective_to, row.is_active)
        elif entity == "positions":
            role = Role.objects.filter(code=data.get("default_role_code")).first()
            expected = (data.get("name"), code(Department, data.get("department_code")), code(JobFamily, data.get("job_family_code")), code(JobLevel, data.get("job_level_code")), code(Position, data.get("parent_position_code")), role.pk if role else None, data.get("description") or "", data.get("responsibility_summary") or "", data.get("effective_from"), data.get("effective_to"), data.get("is_active"))
            actual = (row.name, row.department_id, row.job_family_id, row.job_level_id, row.parent_position_id, row.default_role_id, row.description, row.responsibility_summary, row.effective_from, row.effective_to, row.is_active)
        else:
            expected = (data.get("full_name"), code(Department, data.get("department_code")), code(Position, data.get("position_code")), data.get("status"), data.get("phone") or "")
            actual = (row.full_name, row.department_ref_id, row.position_ref_id, row.status, row.phone or "")
        return actual == expected

    @staticmethod
    def _json_data(data):
        return {key: value.isoformat() if isinstance(value, (date, datetime)) else value for key, value in data.items()}

    @staticmethod
    def _display(item, value):
        if value is None: return ""
        reverse = {stored: label for label, stored in item["choices"].items()}
        return reverse.get(value, value.isoformat() if isinstance(value, (date, datetime)) else value)

    @classmethod
    def error_report_bytes(cls, preview):
        workbook=Workbook(); sheet=workbook.active; sheet.title='导入校验报告'
        headers=['源行号','对象编码','对象名称','中文字段','用户填写值','解析或已有值','具体原因','修正办法']
        sheet.append(headers)
        for error in preview['errors']:
            sheet.append([error.get(k,'') for k in ('rowNumber','objectCode','objectName','fieldLabel','rawValue','resolvedValue','message','suggestedAction')])
        for row in preview['rows']:
            for note in row.get('normalizations',[]):
                sheet.append([row['rowNumber'],row['identity'],row['objectName'],note['fieldLabel'],note.get('rawValue',''),note.get('resolvedValue',''),note['message'],'核对解析结果；原填写值已保留。'])
        widths=[10,16,20,18,30,34,52,64]
        for index,width in enumerate(widths,1): sheet.column_dimensions[sheet.cell(1,index).column_letter].width=width
        for cells in sheet:
            lines=1
            for index,cell in enumerate(cells):
                cell.alignment=Alignment(wrap_text=True,vertical='top')
                if isinstance(cell.value,str): cell.data_type='s'
                lines=max(lines,1+len(str(cell.value or ''))//max(8,int(widths[index]/2)))
            sheet.row_dimensions[cells[0].row].height=max(30,lines*18)
        for cell in sheet[1]: cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='1F4E78')
        sheet.freeze_panes='D2';sheet.auto_filter.ref=sheet.dimensions
        technical=workbook.create_sheet('技术明细')
        technical.append(['源行号','内部字段','错误码'])
        for error in preview['errors']: technical.append([error['rowNumber'],error['field'],error['errorType']])
        technical.sheet_state='hidden'
        stream=io.BytesIO();workbook.save(stream);return stream.getvalue()

    @classmethod
    def commit(cls, entity, *, uploaded_file, user, preview_fingerprint, preview_actor_binding, idempotency_key):
        if not idempotency_key:
            raise OrganizationImportError("IDEMPOTENCY_KEY_REQUIRED", "确认导入需要幂等键。")
        expected_binding = cls.actor_binding(user)
        if preview_actor_binding != expected_binding:
            raise OrganizationImportError("PREVIEW_ACTOR_CHANGED", "预览人与确认导入人或公司范围不一致。", http_status=403)
        preview, _ = cls.preview(entity, uploaded_file=uploaded_file, user=user)
        if preview["previewFingerprint"] != preview_fingerprint:
            raise OrganizationImportError("PREVIEW_STALE", "文件或登录范围已变化，请重新预览。")
        if not preview["canCommit"]:
            raise OrganizationImportError("IMPORT_NOT_READY", "仍有冲突或错误，不能确认导入。")
        creates = [row for row in preview["rows"] if row["decision"] == "CREATE"]
        ordered = cls._dependency_order(entity, creates)
        created, audit_ids, targets = 0, [], []
        with transaction.atomic():
            for row in ordered:
                payload = cls._payload(entity, row["data"], user.company_id)
                payload["reason"] = f"{cls.VERSION} 批量导入；幂等键 {idempotency_key}；源行 {row['rowNumber']}"
                try:
                    result = OrganizationOperatingService.execute(user=user, action=SCHEMAS[entity]["action"], payload=payload)
                except OrganizationOperatingError as exc:
                    raise OrganizationImportError(exc.code, f"第{row['rowNumber']}行写入失败：{exc.message}", http_status=exc.http_status) from exc
                created += 1; audit_ids.append(result["auditId"]); targets.append(result["target"])
        return {"created": created, "matched": preview["counts"]["match"], "auditIds": audit_ids, "targets": targets, "formalReadbackCount": len(targets), "idempotencyKey": idempotency_key}

    @classmethod
    def _dependency_order(cls, entity, rows):
        parent_key = {"departments": "parent_code", "positions": "parent_position_code", "employees": "direct_manager_employee_no"}[entity]
        by_id = {row["identity"]: row for row in rows}; ordered, visiting, done = [], set(), set()
        def visit(identity):
            if identity in done: return
            if identity in visiting: raise OrganizationImportError("HIERARCHY_CYCLE", "文件内上下级关系形成循环。")
            visiting.add(identity)
            parent = by_id[identity]["data"].get(parent_key)
            if parent in by_id: visit(parent)
            visiting.remove(identity); done.add(identity); ordered.append(by_id[identity])
        for identity in by_id: visit(identity)
        return ordered

    @classmethod
    def _payload(cls, entity, data, company_id):
        def object_id(model, key):
            value = data.get(key); found = cls._lookup(model, value, company_id, active=False)
            return found.pk if found else None
        if entity == "departments":
            return {"code": data["code"], "name": data["name"], "departmentType": data["department_type"], "parentId": object_id(Department, "parent_code"), "organizationUnitId": object_id(OrganizationUnit, "organization_unit_code"), "responsiblePositionId": object_id(Position, "responsible_position_code"), "effectiveFrom": data.get("effective_from"), "effectiveTo": data.get("effective_to"), "active": data["is_active"]}
        if entity == "positions":
            role = Role.objects.filter(code=data.get("default_role_code")).first()
            return {"code": data["code"], "name": data["name"], "departmentId": object_id(Department, "department_code"), "jobFamilyId": object_id(JobFamily, "job_family_code"), "jobLevelId": object_id(JobLevel, "job_level_code"), "parentPositionId": object_id(Position, "parent_position_code"), "defaultRoleId": role.pk if role else None, "description": data.get("description") or "", "responsibilitySummary": data.get("responsibility_summary") or "", "effectiveFrom": data.get("effective_from"), "effectiveTo": data.get("effective_to"), "active": data["is_active"]}
        manager = Employee.objects.filter(employee_no=data.get("direct_manager_employee_no"), department_ref__company_id=company_id).first()
        return {"employeeNo": data["employee_no"], "fullName": data["full_name"], "departmentId": object_id(Department, "department_code"), "positionId": object_id(Position, "position_code"), "status": data["status"], "phone": data.get("phone") or "", "directManagerId": manager.pk if manager else None, "directManagerEffectiveFrom": data.get("manager_effective_from"), "directManagerEffectiveTo": data.get("manager_effective_to")}
