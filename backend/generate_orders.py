import random
import pandas as pd
from datetime import datetime, timedelta
from django.apps import apps

Supplier = apps.get_model('procurement', 'Supplier')
Material = apps.get_model('masterdata', 'Material')
Employee = apps.get_model(
    'pfm', 'Employee') if apps.is_installed('pfm') else None

suppliers = Supplier.objects.filter(
    is_active=True).values_list('code', flat=True)
supplier_list = list(suppliers)
if not supplier_list:
    raise Exception("No supplier found. Please import supplier data first.")

materials = Material.objects.filter(
    is_active=True).values('code', 'name', 'specification')
material_list = list(materials)
if not material_list:
    raise Exception("No material found. Please import material data first.")

if Employee:
    buyers = Employee.objects.filter(
        is_active=True).values_list('full_name', flat=True)
    buyer_list = list(buyers)
else:
    buyer_list = ['Zhang San', 'Li Si', 'Wang Wu']
if not buyer_list:
    buyer_list = ['Buyer1', 'Buyer2', 'Buyer3']

STATUS_CHINESE = ['draft', 'submitted', 'approved', 'reviewed',
                  'final_approved', 'received', 'completed', 'closed']
STATUS_WEIGHTS = [0.7, 0.1, 0.05, 0.05, 0.03, 0.03, 0.02, 0.02]

START_DATE = datetime(2026, 4, 1)
END_DATE = datetime(2026, 8, 31)
TODAY = datetime(2026, 5, 19)

ORDER_COUNT = 200
OVERDUE_COUNT = 20

random.seed(42)

orders = []
order_items = []

for i in range(1, ORDER_COUNT + 1):
    po_no = f'PO20260519{i:04d}'
    supplier = random.choice(supplier_list)
    buyer = random.choice(buyer_list)
    order_date = TODAY - timedelta(days=random.randint(0, 90))
    expected_date = START_DATE + \
        timedelta(days=random.randint(0, (END_DATE - START_DATE).days))

    is_overdue = (i <= OVERDUE_COUNT)
    if is_overdue:
        max_extra_days = max(1, (TODAY - expected_date).days)
        if max_extra_days <= 0:
            actual_receive_date = expected_date + timedelta(days=1)
        else:
            extra_days = random.randint(1, min(30, max_extra_days))
            actual_receive_date = expected_date + timedelta(days=extra_days)
        if actual_receive_date > TODAY:
            actual_receive_date = TODAY
        actual_receive_date_str = actual_receive_date.strftime('%Y-%m-%d')
        status = random.choice(['received', 'completed', 'closed'])
    else:
        actual_receive_date_str = ''
        status = random.choices(STATUS_CHINESE, weights=STATUS_WEIGHTS)[0]

    item_count = random.randint(1, 3)
    total_amount = 0
    for j in range(item_count):
        material = random.choice(material_list)
        quantity = random.randint(1, 50)
        unit_price = round(random.uniform(10, 10000), 2)
        amount = round(quantity * unit_price, 2)
        total_amount += amount

        if is_overdue:
            actual_qty = quantity
            actual_price = unit_price
            actual_amount_val = amount
            actual_arrival = actual_receive_date_str
        else:
            actual_qty = ''
            actual_price = ''
            actual_amount_val = ''
            actual_arrival = ''

        order_items.append({
            '订单号': po_no,
            '物料编码': material['code'],
            '物料名称': material['name'],
            '规格型号': material.get('specification', ''),
            '计划数量': quantity,
            '计划单价': unit_price,
            '计划金额': amount,
            '实际交货数量': actual_qty,
            '实际交货单价': actual_price,
            '实际交货金额': actual_amount_val,
            '实际到货日期': actual_arrival,
            '期望到货日期': expected_date.strftime('%Y-%m-%d')
        })

    orders.append({
        '订单号': po_no,
        '供应商编码': supplier,
        '供应商名称': '',
        '采购员': buyer,
        '下单日期': order_date.strftime('%Y-%m-%d'),
        '预计到货日期': expected_date.strftime('%Y-%m-%d'),
        '实际到货日期': actual_receive_date_str,
        '总金额': total_amount,
        '状态': status,
        '备注': f'Test order {i}'
    })

df_orders = pd.DataFrame(orders)
df_items = pd.DataFrame(order_items)

output_file = 'purchase_orders_test_200.xlsx'
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    df_orders.to_excel(writer, sheet_name='订单列表', index=False)
    df_items.to_excel(writer, sheet_name='商品明细', index=False)

print(
    f'Successfully generated {ORDER_COUNT} purchase orders, total {len(order_items)} items.')
print(f'File saved as: {output_file}')
