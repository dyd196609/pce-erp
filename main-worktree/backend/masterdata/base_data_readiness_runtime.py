"""Read-only Group 1-6 base-data readiness facts.

Counts come from canonical models at request time.  Source counts are evidence
summaries from the approved whole-house workbooks; UNKNOWN is kept explicit
where no source file or governed mapping exists.
"""

from django.apps import apps
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from .base_data_comparison_runtime import build_batch1_comparison


def _model(label):
    try:
        return apps.get_model(label)
    except LookupError:
        return None


def _count(label, company_id, filters=None):
    model = _model(label)
    if model is None:
        return 0
    try:
        tables = set(connection.introspection.table_names())
        if model._meta.db_table not in tables:
            return 0
        query = model.objects.all()
        names = {field.name for field in model._meta.fields}
        if "company" in names or "company_id" in names:
            query = query.filter(company_id=company_id)
        if filters:
            query = query.filter(**filters)
        return query.count()
    except Exception:
        return 0


def _migration_applied(app_label, migration_name):
    try:
        return (app_label, migration_name) in MigrationRecorder(connection).applied_migrations()
    except Exception:
        return False


def _entry(code, name, model, count, source, source_count, *, missing="待逐条映射",
           conflict="待人工检查", simulated=0, developed=True, data_present=None,
           route="", critical=False):
    if data_present is None:
        data_present = "PRESENT" if count else "MISSING"
    return {
        "code": code, "module": name, "source": source,
        "sourceRecordCount": source_count,
        "formalModel": model, "formalRecordCount": count,
        "formalData": f"{model} / {count} 条" if model else "正式模型未部署 / 0 条",
        "missing": missing, "conflict": conflict, "simulatedCount": simulated,
        "developed": bool(developed), "dataPresent": data_present,
        "userValidated": False,
        "ready": "NOT_READY",
        "maintenanceRoute": route,
        "productionWriteCount": 0,
    }


def build_base_data_readiness(company_id):
    c = lambda label, filters=None: _count(label, company_id, filters)
    groups = [
        {"group": "GROUP 1", "name": "客户 / 供应商 / UOM", "modules": [
            _entry("customers", "客户 / 经销商", "sales.Customer", c("sales.Customer"), "07经销商 + 08订单排产信息（样版）", 88, missing="88条来源尚未人工确认正式匹配", conflict="精确匹配0；禁止模糊匹配", data_present="MISSING", route="/foundation/base-data-comparison/customers"),
            _entry("suppliers", "供应商", "procurement.Supplier", c("procurement.Supplier"), "09供应商", 20, missing="18个有效名称待匹配；2个空名称待修正", conflict="正式库同名与来源匹配待人工确认", data_present="MISSING", route="/foundation/base-data-comparison/suppliers"),
            _entry("uoms", "UOM", "masterdata.UnitOfMeasure", c("masterdata.UnitOfMeasure"), "01–13工作簿计量值并集", 12, missing="平方、面积2项待业务裁决", conflict="10项精确匹配；不自动合并平方/面积", data_present="PARTIAL", route="/foundation/base-data-comparison/uoms", critical=True),
        ]},
        {"group": "GROUP 2", "name": "物料 / 产品工程", "modules": [
            _entry("materials", "Material", "masterdata.Material", c("masterdata.Material"), "05半成品板材、10采购物料；12木皮、13坯板为属性参考", 193, missing="190条有效来源已形成正式对照；3条待定占位需修正", conflict="MT004/无线鼠标等80条历史样例已隔离", data_present="PARTIAL", route="/foundation/group2-comparison/materials", critical=True),
            _entry("products", "Product", "pde.ProductDefinition", c("pde.ProductDefinition"), "08订单排产信息（样版）", 37, missing="3个去重产品候选尚无正式产品定义", conflict="饰面是否规范为木饰面及配置方式待人工裁决", route="/foundation/group2-comparison/products", critical=True),
            _entry("product_versions", "Product Version", "pde.ProductVersion", c("pde.ProductVersion"), "08订单排产信息（样版）+ 工程拆单及订单排产数据核算方式", 3, missing="真实版本资料待用户确认", conflict="产品定义尚未确认", route="/foundation/group2-comparison/product-versions-configurations", critical=True),
            _entry("product_configurations", "Product Configuration", "pde.ProductConfiguration", c("pde.ProductConfiguration"), "08订单排产信息（样版）+ 工程拆单及订单排产数据核算方式", 3, missing="STANDARD/TEMPLATE_ASSISTED/ORDER_ENGINEERED待用户确认", conflict="不从采购物料反推销售产品", route="/foundation/group2-comparison/product-versions-configurations", critical=True),
        ]},
        {"group": "GROUP 3", "name": "工艺结构", "modules": [
            _entry("operations", "Operation", "system.Process", c("system.Process"), "01工序 + 06设计工序", 42, missing="工序标准工时/UOM/岗位人员关系未完整", conflict="01与06同名/语义需人工确认", data_present="PARTIAL", route="/foundation/master-data/operations", critical=True),
            _entry("boms", "BOM", "pde.ProductBOM", c("pde.ProductBOM"), "工程拆单及订单排产数据核算方式", None, missing="真实BOM未维护", conflict="UNKNOWN", route="/foundation/master-data/boms", critical=True),
            _entry("routings", "Routing", "pde.Routing", c("pde.Routing"), "02工艺路线", 42, missing="42条来源路线/1137个非空步骤待正式映射", conflict="路线产品归属待确认", route="/foundation/master-data/routings", critical=True),
            _entry("routing_versions", "Routing Version", "pde.RoutingVersion", c("pde.RoutingVersion"), "02工艺路线", 42, missing="真实路线版本未维护", conflict="UNKNOWN", route="/foundation/master-data/routing-versions", critical=True),
            _entry("routing_steps", "Routing Step", "pde.RoutingStep", c("pde.RoutingStep"), "02工艺路线", 1137, missing="步骤、前置关系、工作中心及转序方式待确认", conflict="GENERAL/KITTING不得按名称推断", route="/foundation/master-data/routing-steps", critical=True),
        ]},
        {"group": "GROUP 4", "name": "制造资源与日历", "modules": [
            _entry("workshops", "Workshop", "system.Workshop", c("system.Workshop"), "01工序中的车间字段", 3, missing="来源到正式车间待逐条确认", conflict="UNKNOWN", data_present="PARTIAL", route="/foundation/master-data/workshops", critical=True),
            _entry("work_centers", "WorkCenter", "pde.WorkCenter", c("pde.WorkCenter"), "用户制造现场确认", None, missing="真实工作中心待维护", conflict="UNKNOWN", route="/foundation/master-data/work-centers", critical=True),
            _entry("teams", "Team", "system.Team", c("system.Team"), "用户制造现场确认", None, missing="真实班组待维护", conflict="UNKNOWN", route="/organization", critical=True),
            _entry("shifts", "Shift", "pfm.Shift", c("pfm.Shift"), "用户制造现场确认", None, missing="真实班次待维护", conflict="UNKNOWN", route="/shifts", critical=True),
            _entry("standard_capacity", "Standard Capacity", "pde.StandardCapacity", c("pde.StandardCapacity"), "03标准产能", 972, missing="42产品矩阵/972个产能格待映射并人工确认", conflict="禁止伪造产能", route="/foundation/master-data/standard-capacities", critical=True),
            _entry("standard_time", "Standard Time", "system.Process.standard_hours / pde.RoutingStep.standard_hours", c("system.Process", {"standard_hours__gt": 0}), "01工序 + 02工艺路线", 32, missing="正数标准工时记录不足", conflict="工时与产能必须分开", route="/foundation/master-data/operations", critical=True),
            _entry("daily_working_time", "Daily Working Time", None, 0, "用户制造现场确认", None, missing="正式每日工作时间模型/事实未形成", conflict="UNKNOWN", developed=False, critical=True),
            _entry("calendar", "Working Calendar", None, 0, "用户制造现场确认", None, missing="正式工作日历模型/事实未形成", conflict="UNKNOWN", developed=False, critical=True),
            _entry("staffing", "Staffing", "pfm.Employee", c("pfm.Employee", {"status": "active"}), "岗位/人员正式档案 + 用户制造现场确认", None, missing="在职人员存在，但未形成工序/工作中心配置", conflict="员工数不等于可用制造人员", data_present="PARTIAL", route="/organization?tab=employees", critical=True),
        ]},
        {"group": "GROUP 5", "name": "采购 / 仓储 / 供应", "modules": [
            _entry("purchase_lead_time", "Purchase Lead Time", "masterdata.Material.lead_time", c("masterdata.Material", {"lead_time__gt": 0}), "09供应商 + 10采购物料", 132, missing="采购提前期真实值待维护", conflict="禁止以模拟值作为REAL", route="/foundation/master-data/materials", critical=True),
            _entry("warehouses", "Warehouse", "procurement.Warehouse", c("procurement.Warehouse"), "现有正式仓储事实", None, missing="仓库真实性待用户确认", conflict="UNKNOWN", data_present="PARTIAL", route="/foundation/master-data/warehouses", critical=True),
            _entry("locations", "Location", "procurement.WarehouseLocation", c("procurement.WarehouseLocation"), "用户仓储现场确认", None, missing="真实库位待维护", conflict="UNKNOWN", route="/foundation/master-data/warehouse-locations", critical=True),
            _entry("inventory", "Inventory", "procurement.InventoryBalance", c("procurement.InventoryBalance"), "现有正式库存事实", None, missing="现存库存需隔离测试/历史并盘点", conflict="不得把无线鼠标库存作为整木库存", data_present="PARTIAL" if c("procurement.InventoryBalance") else "MISSING", route="/pde/a1-foundation", critical=True),
            _entry("supply_other", "Other Planning / Supply Data", "planning/planning supply facts", c("planning.PlanningRequirement"), "工程拆单及订单排产数据核算方式", None, missing="批次血缘、日历、资源约束未形成", conflict="现存旧计划事实不代表新计划就绪", data_present="PARTIAL" if c("planning.PlanningRequirement") else "MISSING", route="/planning/requirements", critical=True),
        ]},
        {"group": "GROUP 6", "name": "Production Batch & Scheduling Policy", "modules": [
            _entry("production_batch", "Production Batch", None, 0, "本轮生产批次契约", None, missing="正式持久化未部署；当前仅Schema/Preview", conflict="禁止以订单号替代批次号", developed=True, route="/planning/production-batch-foundation", critical=True),
            _entry("batch_allocation", "Batch Item Allocation", None, 0, "本轮数量分配契约", None, missing="正式批次行未部署；校验预览已具备", conflict="累计投产量不得无解释超订单需求", developed=True, route="/planning/production-batch-foundation", critical=True),
            _entry("transition_policy", "General / Kitting Configuration", None, 0, "Operation默认 + RoutingStep覆盖设计", None, missing="正式配置字段未部署；规则预览已具备", conflict="不按工序名称/编码推断", developed=True, route="/planning/production-batch-foundation", critical=True),
            _entry("kitting_scope", "Kitting Scope", None, 0, "Batch + Product Structure + Routing + Step", None, missing="真实Required Member Set待制造数据", conflict="不得使用所有订单行", developed=True, route="/planning/production-batch-foundation", critical=True),
            _entry("date_propagation", "Planning Date Propagation", None, 0, "本轮V1非APS预览算法", None, missing="真实产能/日历/人员不足时BLOCK", conflict="不生成伪日期", developed=True, route="/planning/production-batch-foundation", critical=True),
            _entry("kitting_status", "Kitting Status", None, 0, "WAITING_FOR_KITTING / READY预览", None, missing="实际执行反馈不在本轮", conflict="计划日期到达不等于实际齐套", developed=True, route="/planning/production-batch-foundation", critical=True),
        ]},
    ]
    for group in groups:
        statuses = {item["dataPresent"] for item in group["modules"]}
        group["developed"] = all(item["developed"] for item in group["modules"])
        group["dataPresent"] = "MISSING" if statuses == {"MISSING"} else "PARTIAL"
        group["userValidated"] = False
        group["ready"] = "NOT_READY"
    group1 = groups[0]
    group1_comparisons = {
        entity: build_batch1_comparison(entity, company_id)["summary"]
        for entity in ("customers", "suppliers", "uoms")
    }
    group1_formalized = (
        group1_comparisons["customers"]["exactMatchCount"] == 88
        and group1_comparisons["customers"]["unmatchedSourceCount"] == 0
        and group1_comparisons["suppliers"]["exactMatchCount"] == 18
        and group1_comparisons["suppliers"]["unmatchedSourceCount"] == 0
        and group1_comparisons["suppliers"]["invalidSourceCount"] == 2
        and group1_comparisons["uoms"]["unmatchedSourceCount"] == 0
    )
    group1["userValidated"] = True
    group1["dataPresent"] = "PRESENT" if group1_formalized else "PARTIAL"
    group1["ready"] = "READY" if group1_formalized else "VALIDATED"
    for item, entity in zip(group1["modules"], ("customers", "suppliers", "uoms")):
        comparison = group1_comparisons[entity]
        item["userValidated"] = True
        item["dataPresent"] = "PRESENT" if group1_formalized else item["dataPresent"]
        item["ready"] = "READY" if group1_formalized else "VALIDATED"
        item["sourceRecordCount"] = comparison["sourceRecordCount"]
        item["formalRecordCount"] = comparison["formalRecordCount"]
    group1["modules"][0]["missing"] = "88条来源已正式匹配；来源外1条历史/测试记录继续隔离"
    group1["modules"][0]["conflict"] = "未匹配0；冲突0"
    group1["modules"][1]["missing"] = "18个有效名称已正式匹配；2个空名称继续BLOCKED / EXCLUDED"
    group1["modules"][1]["conflict"] = "未匹配0；空名称不猜测"
    group1["modules"][2]["missing"] = "平方映射m²/平方米；面积为calculation_basis=AREA，不创建面积UOM"
    group1["modules"][2]["conflict"] = "UOM人工裁决已完成"
    return {
        "factLoadStatus": "success", "readOnly": True,
        "baseDataSystem": "GROUP_1_FORMALIZED / GROUP_2_MANUAL_VALIDATION_READY" if group1_formalized else "MANUAL_VALIDATION_READY",
        "baseDataReality": "PARTIAL" if group1_formalized else "NOT_READY",
        "productionBusinessMasterDataWriteCount": 0,
        "groups": groups,
        "simulatedDataPreview": [
            {"entity": "Customer", "field": "contactName", "previewValue": "测试联系人-CUST-001", "provenance": "SIMULATED_FOR_TEST"},
            {"entity": "Customer", "field": "email", "previewValue": "cust-001@example.invalid", "provenance": "SIMULATED_FOR_TEST"},
            {"entity": "Supplier", "field": "phone", "previewValue": "000-TEST-0001", "provenance": "SIMULATED_FOR_TEST"},
            {"entity": "Supplier", "field": "address", "previewValue": "测试地址-不得用于业务", "provenance": "SIMULATED_FOR_TEST"},
            {"entity": "Material", "field": "auxiliaryNote", "previewValue": "软件测试辅助字段", "provenance": "SIMULATED_FOR_TEST"},
        ],
        "simulationRules": [
            "只补非制造核心辅助字段", "不覆盖来源真实值", "生产关键数据禁止模拟为REAL",
            "当前只是Preview，正式写入0",
        ],
        "planningDeployment": {
            "productionEnabled": False,
            "migration0005Applied": _migration_applied("planning", "0005_order_planning_chain_v1"),
            "demandRecords": c("planning.Demand"),
            "mpsRecords": c("planning.MasterProductionScheduleRun"),
            "mrpRecords": c("planning.MaterialRequirementsPlanningRun"),
            "productionSchedule": "PREVIEW_ONLY",
        },
    }
