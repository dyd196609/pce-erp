import random
from datetime import datetime, timedelta
from django.db import transaction
from django.apps import apps


def generate_orders(n=200):
    """
    v2.2 ERP真实数据引擎
    - 完全对齐 PurchaseOrder / PurchaseOrderItem
    - 不依赖错误外键字段
    """

    User = apps.get_model("system", "User")
    Employee = apps.get_model("pfm", "Employee")
    Material = apps.get_model("masterdata", "Material")
    Supplier = apps.get_model("procurement", "Supplier")
    Department = apps.get_model("pfm", "Department")

    PurchaseOrder = apps.get_model("purchase", "PurchaseOrder")
    PurchaseOrderItem = apps.get_model("purchase", "PurchaseOrderItem")

    users = list(User.objects.all())
    employees = list(Employee.objects.all())
    materials = list(Material.objects.all())
    suppliers = list(Supplier.objects.all())
    departments = list(Department.objects.all())

    if not users or not materials or not suppliers:
        print("❌ 基础数据不足（User / Material / Supplier）")
        return

    created_orders = 0
    created_items = 0

    today = datetime.now()

    with transaction.atomic():

        for i in range(n):

            user = random.choice(users)
            employee = random.choice(employees) if employees else None
            supplier = random.choice(suppliers)
            dept = random.choice(departments) if departments else None

            po_no = f"PO{today.strftime('%Y%m%d')}{i:05d}"

            order = PurchaseOrder.objects.create(
                po_no=po_no,
                supplier_name=getattr(supplier, "name", "未知供应商"),
                buyer_name=getattr(user, "username", "未知用户"),
                purchase_department=dept.name if dept else "采购部",
                require_department="生产部",
                order_date=today - timedelta(days=random.randint(1, 120)),
                expected_date=today + timedelta(days=random.randint(3, 30)),

                total_plan_amount=0,
                total_actual_amount=0,

                document_status=random.choice([
                    "draft", "submitted", "audited", "approved"
                ]),

                progress_status=random.choice([
                    "not_started", "arriving", "arrived", "warehousing"
                ]),

                urgency_level=random.choice([
                    "normal", "urgent", "very_urgent"
                ]),

                is_on_time_delivery=random.choice([True, False]),
                remark="v2.2 自动生成测试数据"
            )

            # ===== 生成明细 =====
            item_count = random.randint(1, 5)
            total_amount = 0

            for _ in range(item_count):

                material = random.choice(materials)

                qty = round(random.uniform(1, 100), 2)
                price = float(getattr(material, "price", 10) or 10)
                amount = round(qty * price, 2)

                total_amount += amount

                PurchaseOrderItem.objects.create(
                    order=order,
                    material_code=getattr(material, "code", "M-000"),
                    material_name=material.name,
                    specification=getattr(material, "specification", ""),
                    unit=getattr(material, "unit", "pcs"),

                    plan_quantity=qty,
                    actual_quantity=qty,

                    plan_unit_price=price,
                    actual_unit_price=price,

                    plan_amount=amount,
                    actual_amount=amount,

                    plan_delivery_date=today + timedelta(days=random.randint(1, 30)),
                    actual_delivery_date=today + timedelta(days=random.randint(1, 40)),

                    arrival_quantity=qty,
                    qualified_quantity=qty,
                    rejected_quantity=0,
                    inbound_quantity=qty,

                    settled_quantity=qty,
                    settled_amount=amount,

                    is_on_time_delivery=random.choice([True, False]),
                    remark="seed item"
                )

                created_items += 1

            order.total_plan_amount = total_amount
            order.total_actual_amount = total_amount
            order.save()

            created_orders += 1

    print(f"✅ v2.2 ERP真实数据引擎完成")
    print(f"   - 采购订单：{created_orders} 条")
    print(f"   - 采购明细：{created_items} 条")