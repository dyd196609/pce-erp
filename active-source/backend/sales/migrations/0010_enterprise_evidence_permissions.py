from django.db import migrations


CODES = (
    ("sales.production_followup.read", "查看本人负责的生产订单", "MES"),
    ("sales.production_followup.assign", "分派或移交生产跟单", "MES"),
    ("sales.customer_account.bind", "核实并绑定客户账号", "SALES"),
    ("sales.customer_progress.publish", "发布客户订单里程碑", "SALES"),
    ("reconciliation.evidence_risk.check", "读取采购一致性核对", "FIN"),
    ("reconciliation.evidence_risk.receive", "受理采购风险并指定处理人", "FIN"),
    ("reconciliation.evidence_risk.close", "独立复核并关闭采购风险", "FIN"),
    ("reconciliation.evidence_risk.quality", "处理质检风险", "QMS"),
    ("reconciliation.evidence_risk.inventory", "处理仓管风险", "WMS"),
    ("reconciliation.evidence_risk.procurement", "处理采购风险", "SCM"),
    ("reconciliation.evidence_risk.payable", "处理财务风险", "FIN"),
)


def register_permissions(apps, schema_editor):
    permission = apps.get_model("system", "Permission")
    for code, name, module in CODES:
        permission.objects.using(schema_editor.connection.alias).get_or_create(
            code=code, defaults={"name": name, "module": module},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0009_enterprise_evidence"),
        ("reconciliation", "0004_enterprise_evidence"),
    ]
    operations = [migrations.RunPython(register_permissions, migrations.RunPython.noop)]
