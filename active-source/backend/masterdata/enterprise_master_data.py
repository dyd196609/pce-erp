"""Enterprise master-data page metadata and isolated non-canonical fixtures.

Canonical domains keep their rows empty here and read formal runtime models.
"""

MASTER_DATA_VERSION = "V1.14.2.8.4.8.5"
MASTER_DATA_TENANT = "PCE-MD-ACCEPTANCE"
MASTER_DATA_BATCH = "V85-MASTER-DATA"

ENTITY_DEFINITIONS = {
    "organizations": {
        "masterDataCode": "MD-ORG",
        "pageCode": "master-data-organizations",
        "nodeCode": "organization-data",
        "title": "组织主数据",
        "primaryField": "organizationCode",
        "rows": [
            {
                "id": "MD-ORG-001",
                "organizationCode": "ORG-CN-001",
                "organizationName": "华东制造有限公司",
                "organizationType": "公司",
                "parentOrganization": "-",
                "businessStatus": "启用",
            },
            {
                "id": "MD-ORG-002",
                "organizationCode": "PLANT-SZ-001",
                "organizationName": "苏州工厂",
                "organizationType": "工厂",
                "parentOrganization": "华东制造有限公司",
                "businessStatus": "启用",
            },
            {
                "id": "MD-ORG-003",
                "organizationCode": "DEPT-PUR-001",
                "organizationName": "采购部",
                "organizationType": "部门",
                "parentOrganization": "华东制造有限公司",
                "businessStatus": "启用",
            },
            {
                "id": "MD-ORG-004",
                "organizationCode": "WC-ASM-001",
                "organizationName": "总装工作中心",
                "organizationType": "工作中心",
                "parentOrganization": "苏州工厂",
                "businessStatus": "启用",
            },
        ],
    },
    "customers": {
        "masterDataCode": "MD-CUSTOMER",
        "pageCode": "master-data-customers",
        "nodeCode": "customer-data",
        "title": "客户主数据",
        "primaryField": "customerCode",
        # 正式页面只读 sales.Customer；禁止静态验收客户。
        "rows": [],
    },
    "suppliers": {
        "masterDataCode": "MD-SUPPLIER",
        "pageCode": "master-data-suppliers",
        "nodeCode": "supplier-data",
        "title": "供应商主数据",
        "primaryField": "supplierCode",
        # 正式页面由SupplierMasterRuntimeAdapter读取supplier表；禁止静态验收供应商。
        "rows": [],
    },
    "materials": {
        "masterDataCode": "MD-MATERIAL",
        "pageCode": "master-data-materials",
        "nodeCode": "material-data",
        "title": "物料主数据",
        "primaryField": "materialCode",
        "rows": [],
    },
    "boms": {
        "masterDataCode": "MD-BOM",
        "pageCode": "master-data-boms",
        "nodeCode": "bom-data",
        "title": "BOM基础数据",
        "primaryField": "bomNo",
        "demoRows": [
            {
                "id": "MD-BOM-001",
                "bomNo": "BOM-CAB-001",
                "productName": "智能控制柜",
                "bomVersion": "V1.0",
                "componentName": "焊接箱体",
                "quantity": 1,
                "unit": "件",
                "businessStatus": "已发布",
            },
            {
                "id": "MD-BOM-002",
                "bomNo": "BOM-CAB-001-L2",
                "productName": "智能控制柜",
                "bomVersion": "V1.0",
                "componentName": "控制模块",
                "quantity": 2,
                "unit": "件",
                "businessStatus": "已发布",
            },
        ],
        "rows": [],
    },
    "routings": {
        "masterDataCode": "MD-ROUTING",
        "pageCode": "master-data-routings",
        "nodeCode": "routing-data",
        "title": "工艺路线基础数据",
        "primaryField": "routingNo",
        "demoRows": [
            {
                "id": "MD-ROUTING-001",
                "routingNo": "RT-CAB-001",
                "operationName": "箱体装配",
                "sequence": 10,
                "workCenter": "总装工作中心",
                "standardHours": 2.5,
                "businessStatus": "启用",
            },
            {
                "id": "MD-ROUTING-002",
                "routingNo": "RT-CAB-002",
                "operationName": "电气调试",
                "sequence": 20,
                "workCenter": "调试工作中心",
                "standardHours": 1.5,
                "businessStatus": "启用",
            },
        ],
        "rows": [],
    },
    "warehouses": {
        "masterDataCode": "MD-WAREHOUSE",
        "pageCode": "master-data-warehouses",
        "nodeCode": "warehouse-data",
        "title": "仓库基础数据",
        "primaryField": "warehouseCode",
        "demoRows": [
            {
                "id": "MD-WAREHOUSE-001",
                "warehouseCode": "WH-RM-001",
                "warehouseName": "原材料仓",
                "zoneName": "金属材料区",
                "locationCode": "RM-A-01",
                "businessStatus": "启用",
            },
            {
                "id": "MD-WAREHOUSE-002",
                "warehouseCode": "WH-FG-001",
                "warehouseName": "成品仓",
                "zoneName": "待发货区",
                "locationCode": "FG-B-01",
                "businessStatus": "启用",
            },
        ],
        "rows": [],
    },
}


def get_master_data_definition(entity_code):
    return ENTITY_DEFINITIONS.get(str(entity_code or "").strip().lower())
