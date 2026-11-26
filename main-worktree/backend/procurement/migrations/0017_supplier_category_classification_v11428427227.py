from django.db import migrations


def _supplier_category(name):
    value = str(name or "")
    if any(word in value for word in ("京东", "阿里", "拼多多")):
        return "办公用品供应商"
    if any(word in value for word in (
        "海尔", "格力", "美的", "比亚迪", "宁德", "中车", "电网", "电建",
        "能建", "航空", "船舶", "兵工", "核建", "建筑", "中铁", "铁建", "交建",
    )):
        return "设备供应商"
    if any(word in value for word in (
        "技术", "科技", "通讯", "电子", "电科", "信息", "软件", "网络", "讯飞",
        "信服", "网科", "认证", "在线", "曙光", "海康", "大华", "联想", "小米",
        "浪潮", "中芯", "紫光", "计算",
    )):
        return "电子元器件供应商"
    if any(word in value for word in (
        "集团", "通用", "宝武", "中粮", "中化", "五矿", "石油", "石化", "黄金",
        "有色", "移动", "联通", "电信", "顺丰", "出行", "建材",
    )):
        return "综合供应商"
    return "待分类"


def classify_defaulted_suppliers(apps, schema_editor):
    Supplier = apps.get_model("procurement", "Supplier")
    for supplier in Supplier.objects.filter(category="待分类"):
        category = _supplier_category(supplier.name)
        if category != supplier.category:
            supplier.category = category
            supplier.save(update_fields=["category"])


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0016_supplier_master_completeness_v11428427227"),
    ]

    operations = [
        migrations.RunPython(classify_defaulted_suppliers, migrations.RunPython.noop),
    ]
