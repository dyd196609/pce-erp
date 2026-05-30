import random
import pandas as pd
from datetime import datetime, timedelta

# ============================================================
# 请根据您系统中实际存在的供应商编码和物料信息修改以下列表
# ============================================================
SUPPLIER_CODES = ['SUP001', 'SUP002', 'SUP003',
                  'SUP004', 'SUP005', 'SUP006', 'SUP007', 'SUP008', 'SUP009']   # 替换成真实的供应商编码

MATERIAL_LIST = [
    {'code': 'MT001', 'name': '笔记本电脑', 'spec': 'ThinkPad X1 Carbon'},
    {'code': 'MT002', 'name': '台式电脑', 'spec': '戴尔OptiPlex'},
    {'code': 'MT003', 'name': '显示器', 'spec': '27寸4K显示器'},
    {'code': 'MT004', 'name': '无线鼠标', 'spec': '罗技M330'},
    {'code': 'MT005', 'name': '有线键盘', 'spec': '戴尔KB216'},
    {'code': 'MT006', 'name': '机械键盘', 'spec': '樱桃MX3.0'},
    {'code': 'MT007', 'name': 'USB扩展坞', 'spec': '绿联4口'},
    {'code': 'MT008', 'name': '网线', 'spec': '六类千兆3米'},
    {'code': 'MT009', 'name': 'HDMI线', 'spec': '2.0版2米'},
]   # 替换成真实的物料信息
# ============================================================

BUYERS = ['张三', '李四', '王五']
STATUS_OPTIONS = ['草稿', '已提交', '已审核', '已复核', '已审批', '已收货', '已完成', '已结案']
STATUS_WEIGHTS = [0.7, 0.1, 0.05, 0.05, 0.03, 0.03, 0.02, 0.02]

START_DATE = datetime(2026, 4, 1)
END_DATE = datetime(2026, 8, 31)
TODAY = datetime(2026, 5, 19)

ORDER_COUNT = 200
OVERDUE_COUNT = 20
random.seed(42)

orders = []
items = []

for i in range(1, ORDER_COUNT + 1):
    po_no = f'PO20260519{i:04d}'
    supplier_code = random.choice(SUPPLIER_CODES)
    buyer = random.choice(BUYERS)
    order_date = TODAY - timedelta(days=random.randint(0, 90))
    expected_date = START_DATE + \
        timedelta(days=random.randint(0, (END_DATE - START_DATE).days))

    is_overdue = i <= OVERDUE_COUNT
    if is_overdue:
        max_extra = max(1, (TODAY - expected_date).days)
        extra = random.randint(1, min(30, max_extra))
        actual_receive_date = expected_date + timedelta(days=extra)
        if actual_receive_date > TODAY:
            actual_receive_date = TODAY
        actual_receive_date_str = actual_receive_date.strftime('%Y-%m-%d')
        status = random.choice(['已收货', '已完成', '已结案'])
    else:
        actual_receive_date_str = ''
        status = random.choices(STATUS_OPTIONS, weights=STATUS_WEIGHTS)[0]

    total_amount = 0
    for _ in range(random.randint(1, 3)):
        material = random.choice(MATERIAL_LIST)
        qty = random.randint(1, 100)
        price = round(random.uniform(10, 1000), 2)
        amount = round(qty * price, 2)
        total_amount += amount

        if is_overdue:
            items.append({
                '订单号': po_no,
                '物料编码': material['code'],
                '物料名称': material['name'],
                '规格型号': material['spec'],
                '计划数量': qty,
                '计划单价': price,
                '计划金额': amount,
                '实际交货数量': qty,
                '实际交货单价': price,
                '实际交货金额': amount,
                '实际到货日期': actual_receive_date_str,
                '期望到货日期': expected_date.strftime('%Y-%m-%d')
            })
        else:
            items.append({
                '订单号': po_no,
                '物料编码': material['code'],
                '物料名称': material['name'],
                '规格型号': material['spec'],
                '计划数量': qty,
                '计划单价': price,
                '计划金额': amount,
                '实际交货数量': '',
                '实际交货单价': '',
                '实际交货金额': '',
                '实际到货日期': '',
                '期望到货日期': expected_date.strftime('%Y-%m-%d')
            })

    orders.append({
        '订单号': po_no,
        '供应商编码': supplier_code,
        '供应商名称': '',
        '采购员': buyer,
        '下单日期': order_date.strftime('%Y-%m-%d'),
        '预计到货日期': expected_date.strftime('%Y-%m-%d'),
        '实际到货日期': actual_receive_date_str,
        '总金额': total_amount,
        '状态': status,
        '备注': f'测试订单{i}'
    })

df_orders = pd.DataFrame(orders)
df_items = pd.DataFrame(items)
output_file = 'purchase_orders_test_200.xlsx'
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    df_orders.to_excel(writer, sheet_name='订单列表', index=False)
    df_items.to_excel(writer, sheet_name='商品明细', index=False)

print(f'成功生成 {ORDER_COUNT} 个订单，共 {len(items)} 条明细。')
print(f'文件已保存为: {output_file}')
