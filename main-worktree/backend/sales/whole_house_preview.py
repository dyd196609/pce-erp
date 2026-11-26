"""Governed, read-only projection of the approved whole-house source sample.

This module is deliberately not an import model.  It contains the normalized
preview and source-to-canonical mapping proven from the governed Excel files;
no function in this module writes a database row.
"""

SOURCE_FILE = "08订单排产信息（样版）.xlsx"
SOURCE_SHEET = "生产计划"
SOURCE_SHA256 = "CC94662B760102316838208F9478C3618269B7F48EDAED6A99D7A13B81580A59"

from .source_semantics import source_evidence


def _mapping(source_field, entity, field, transformation, readiness, missing_dependency=""):
    return {
        "sourceField": source_field,
        "canonicalEntity": entity,
        "canonicalField": field,
        "transformation": transformation,
        "readiness": readiness,
        "missingDependency": missing_dependency,
    }


WHOLE_HOUSE_ORDER_SOURCE_MAPPING = (
    _mapping("序号", "SalesOrderItemEngineeringAttribute", "sequence", "保留源行顺序", "READY"),
    _mapping("主订单号", "SalesOrder", "external_source_no", "原值保留；正式 order_no 由 ERP 生成", "PARTIAL", "用户确认后才允许正式创建"),
    _mapping("子订单号", "SalesOrderItem", "external_line_no", "原值保留；不得直接当 ERP 主键", "PARTIAL", "逐行补足商业身份与数量证据；来源数与销售行数独立"),
    _mapping("半成品板材编码", "SalesOrderItemEngineeringAttribute / BOMItem", "raw_value / material", "先作为工程来源属性；BOM 发布时再解析物料", "PARTIAL", "正式物料与 BOM 关系未建立"),
    _mapping("半成品编码", "SalesOrderItemEngineeringAttribute / ProductManufacturingOutput", "normalized_value / routing_version", "作为工程结构和工艺路线来源键，不冒充销售成品编码", "PARTIAL", "正式 ProductDefinition、BOM、Routing、ManufacturingOutput 未建立"),
    _mapping("订单类型", "SalesOrder", "order_type", "正单 → standard 候选；需业务确认", "PARTIAL", "源枚举到 ERP 枚举尚待用户确认"),
    _mapping("产品类型", "SalesOrderItem", "customer_product_name", "房门/饰面/柜体仅为类别；不得据此决定销售行数", "PARTIAL", "正式销售产品身份和 ProductDefinition 未建立"),
    _mapping("紧急程度", "SalesOrderItemEngineeringAttribute", "order_priority", "原值保留", "READY"),
    _mapping("客户", "Customer", "name", "按名称查找正式客户；不自动新增", "PARTIAL", "需确认正式客户匹配"),
    _mapping("等级", "SalesOrderItemEngineeringAttribute", "customer_grade", "原值保留", "READY"),
    _mapping("项目名称", "SalesOrder", "project_reference", "原值保留", "READY"),
    _mapping("客户缴纳订金日期", "SalesOrderItemEngineeringAttribute", "deposit_date", "Excel 日期标准化为 YYYY-MM-DD", "PARTIAL", "订金/应收正式对象本轮未接入"),
    _mapping("订单金额", "SalesOrder", "total amount (derived)", "源值仅作核对；不得覆盖订单行金额", "BLOCKED", "源值为 0，缺正式价格与金额口径"),
    _mapping("客户下单日期", "SalesOrder", "order_date", "Excel 日期标准化为 YYYY-MM-DD", "READY"),
    _mapping("客户订单交期", "SalesOrder / SalesOrderItem", "required_delivery_date / required_date", "Excel 日期标准化为 YYYY-MM-DD", "READY"),
    _mapping("客户来图日期", "SalesOrderItemEngineeringAttribute", "drawing_received_date", "Excel 日期标准化为 YYYY-MM-DD", "READY"),
    _mapping("接单人", "SalesOrder", "sales_owner", "按员工姓名匹配；不自动新增", "PARTIAL", "需匹配在职员工与营销岗位"),
    _mapping("拆单员", "SalesOrderItemEngineeringAttribute / OrderEngineeringInstance", "splitter", "先保留来源人员；工程实例建立后绑定责任人", "PARTIAL", "正式工程责任绑定未建立"),
    _mapping("设计师", "SalesOrderItemEngineeringAttribute / OrderEngineeringInstance", "designer", "先保留来源人员；工程实例建立后绑定责任人", "PARTIAL", "正式工程责任绑定未建立"),
    _mapping("下单员", "SalesOrderItemEngineeringAttribute", "order_placer", "原值 0 视为未提供，不映射 created_by", "MISSING", "真实下单员缺失"),
    *(
        _mapping(field, "SalesOrderItemEngineeringAttribute / OperationRequirement", canonical, "保留数值和源字段；仅在工程核算后形成工序需求", "PARTIAL", "UOM 与正式工序需求口径未确认")
        for field, canonical in (
            ("油漆数量", "paint_quantity"), ("木工数量", "woodwork_quantity"),
            ("贴皮数量", "veneer_quantity"), ("拼皮数量", "veneer_splicing_quantity"),
            ("UV数量", "uv_quantity"), ("防潮数量", "moisture_proof_quantity"),
            ("饰面数量", "finish_surface_quantity"), ("柜门数量", "cabinet_door_quantity"),
            ("柜体数量", "cabinet_body_quantity"), ("房门数量", "room_door_quantity"),
            ("免漆数量", "paint_free_quantity"), ("开放数量", "open_finish_quantity"),
            ("混油数量", "mixed_paint_quantity"), ("封闭数量", "closed_finish_quantity"),
            ("肤感数量", "skin_feel_quantity"),
        )
    ),
    _mapping("备注", "SalesOrderItem", "remark", "原值保留；0 视为空备注", "READY"),
)


def whole_house_order_preview():
    evidence = source_evidence()
    return {
        "previewCode": "WHOLE_HOUSE_ORDER_20231112_6_READ_ONLY",
        "previewStatus": "AWAITING_USER_VALIDATION",
        "readOnly": True,
        "businessWriteCount": 0,
        "source": {
            "fileName": SOURCE_FILE,
            "sheet": SOURCE_SHEET,
            "range": "A1:AJ38",
            "dataRows": "2-38",
            "rowCount": 37,
            "sha256": SOURCE_SHA256,
            "sourceRole": "业务素材/事实来源；不是 ERP Schema 或编码标准",
            "evidenceType": evidence["evidenceType"],
            "archiveSha256": evidence["archiveSha256"],
            "archivePath": evidence["archivePath"],
        },
        "order": {
            "customerOrDealer": "温岭江公馆",
            "externalOrderNo": "2023/11/12-6-正单",
            "project": "世贸大厦",
            "spaceOrRoom": "源文件未提供",
            "productSummary": "房门 / 饰面 / 柜体",
            "quantitySummary": "房门 4.65；饰面 3.951972；柜体 19",
            "uom": "源文件未提供；禁止推断",
            "specification": "源文件未提供；禁止推断",
            "deliveryDate": "2023-11-30",
            "engineeringMode": "MAKE 候选；需建立正式产品/工程事实后确认",
            "structureSummary": "3 个分类汇总，不等于销售明细；37 条工程/排产来源行；销售行数尚无依据",
            "sourceReference": f"{SOURCE_FILE} / {SOURCE_SHEET} / rows 2-38",
            "orderType": "正单",
            "urgency": "一般",
            "orderDate": "2023-11-12",
            "depositDate": "2023-10-20",
            "drawingDate": "2023-11-01",
            "receiver": "戴桂舟",
            "splitter": "王静",
            "designer": "霍新猛",
            "amountRaw": "0（仅保留源值；不是可写正式金额）",
        },
        "productGroups": evidence["groups"],
        "quantityPrecision": evidence["precision"],
        "operationEvidence": evidence["operationEvidence"],
        "sourceLineIdentities": evidence["rows"],
        "mapping": [dict(value) for value in WHOLE_HOUSE_ORDER_SOURCE_MAPPING],
        "relatedSources": [
            {"file": "07经销商.xlsx", "sheet": "客户管理", "range": "B7", "relationship": "客户名称命中：温岭江公馆"},
            {"file": "02工艺路线.xlsx", "sheet": "工艺路线", "range": "B9:AF10,B17:AD17", "relationship": "三个半成品编码命中工艺来源；尚未成为 ERP 正式 Routing"},
            {"file": "03标准产能.xlsx", "sheet": "标准产能", "range": "B13,B21,B34", "relationship": "三个半成品编码命中来源产能行；尚未成为正式 StandardCapacity"},
            {"file": "11半成品工价.xlsx", "sheet": "标准工价", "range": "B13,B21,B34", "relationship": "三个半成品编码命中来源工价行；不进入本轮订单金额"},
            {"file": "工程拆单及订单排产数据核算方式.xlsx", "sheet": "客户", "range": "A7", "relationship": "客户名称命中；未发现该主订单号或三个半成品编码"},
        ],
        "readiness": {
            "salesOrderPreview": "READY",
            "canonicalCustomer": "PARTIAL",
            "canonicalSalesProducts": "MISSING",
            "uom": "MISSING",
            "spaceAndSpecification": "MISSING",
            "productDefinition": "MISSING",
            "productConfiguration": "NOT_YET_APPLICABLE",
            "bom": "MISSING",
            "routing": "SOURCE_REFERENCE_ONLY",
            "manufacturingOutput": "MISSING",
            "manufacturingReady": False,
            "planningEligible": False,
            "userValidated": False,
        },
    }
