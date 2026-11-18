from django.db import migrations, models
import django.db.models.deletion


LOCATION_CYCLE = (
    ("广东", "深圳"),
    ("浙江", "杭州"),
    ("江苏", "南京"),
    ("山东", "青岛"),
    ("湖北", "武汉"),
    ("四川", "成都"),
    ("福建", "厦门"),
    ("河南", "郑州"),
    ("陕西", "西安"),
    ("安徽", "合肥"),
)


def _company_name(name):
    value = str(name or "").strip()
    return value if value.endswith("公司") else f"{value}有限公司"


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


def populate_supplier_master(apps, schema_editor):
    Supplier = apps.get_model("procurement", "Supplier")
    SupplierDuplicateReview = apps.get_model(
        "procurement", "SupplierDuplicateReview"
    )

    for index, supplier in enumerate(Supplier.objects.order_by("code", "id")):
        changed_fields = []
        if not str(supplier.address or "").strip() or supplier.address == "未维护":
            province, city = LOCATION_CYCLE[index % len(LOCATION_CYCLE)]
            supplier.address = (
                f"{province}省{city}市{_company_name(supplier.name)}"
            )
            changed_fields.append("address")
        if (
            not str(supplier.category or "").strip()
            or supplier.category in {"未分类", "待分类"}
        ):
            supplier.category = _supplier_category(supplier.name)
            changed_fields.append("category")
        if not str(supplier.contact_person or "").strip() or supplier.contact_person == "未维护":
            supplier.contact_person = "张经理"
            changed_fields.append("contact_person")
        if not str(supplier.contact_phone or "").strip() or supplier.contact_phone == "未维护":
            supplier.contact_phone = "13700005486"
            changed_fields.append("contact_phone")
        if changed_fields:
            supplier.save(update_fields=changed_fields)

    duplicate_names = (
        Supplier.objects.values("name")
        .annotate(record_count=models.Count("id"))
        .filter(record_count__gt=1)
    )
    for group in duplicate_names:
        for supplier in Supplier.objects.filter(name=group["name"]):
            SupplierDuplicateReview.objects.update_or_create(
                supplier=supplier,
                supplier_name=supplier.name,
                defaults={
                    "supplier_code": supplier.code,
                    "duplicate_reason": (
                        f"同名SupplierMaster共{group['record_count']}条，禁止自动合并"
                    ),
                    "status": "待人工确认",
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0015_price_approval_review_result_v11428424_r23"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="category",
            field=models.CharField(default="待分类", max_length=40),
        ),
        migrations.CreateModel(
            name="SupplierDuplicateReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("supplier_code", models.CharField(max_length=50)),
                ("supplier_name", models.CharField(max_length=100)),
                ("duplicate_reason", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("待人工确认", "待人工确认")], default="待人工确认", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="duplicate_reviews", to="procurement.supplier")),
            ],
            options={
                "db_table": "supplier_duplicate_review",
                "ordering": ["supplier_code", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="supplierduplicatereview",
            constraint=models.UniqueConstraint(fields=("supplier", "supplier_name"), name="supplier_duplicate_review_identity_unique"),
        ),
        migrations.RunPython(populate_supplier_master, migrations.RunPython.noop),
    ]
