from masterdata.models import Material
import pandas as pd
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pce_backend.settings')
django.setup()


# 读取您现有的 Excel 文件（请修改为实际路径）
file_path = r'H:\Dev-PCE\Source\backend\物料导入模板_v2.xlsx'   # 实际路径
df = pd.read_excel(file_path, sheet_name='物料导入模板_v2', engine='openpyxl')

# 定义物料类型映射
type_map = {
    '成品': 'finished',
    '耗材': 'auxiliary',
    '固定资产': 'finished',   # 固定资产暂归为成品
}


def to_bool(val):
    if pd.isna(val):
        return False
    return str(val).strip() in ['是', 'true', 'True', '1']


# 扩充到 200 条（基于原有 50 条循环）
base_rows = df.to_dict('records')
new_rows = []
for i in range(200):
    base = base_rows[i % len(base_rows)]
    seq = i + 1
    new_code = f"MT{seq:03d}"
    new_name = base['物料名称'] if seq <= 50 else f"{base['物料名称']}_{seq}"
    # 其他字段复制原值，但物料编码和名称稍作修改避免重复
    row = base.copy()
    row['物料编码'] = new_code
    row['物料名称'] = new_name
    new_rows.append(row)

# 导入数据库
success = 0
for row in new_rows:
    # 字段映射
    code = str(row['物料编码']).strip()
    name = str(row['物料名称']).strip()
    specification = str(row.get('规格型号', '')).strip(
    ) if pd.notna(row.get('规格型号')) else ''
    unit = str(row.get('单位', '')).strip()
    price = float(row['单价']) if pd.notna(row.get('单价')) else 0
    material_type = type_map.get(str(row.get('物料类型', '')).strip(), 'raw')
    safety_stock = float(row.get('安全库存', 0)) if pd.notna(
        row.get('安全库存')) else 0
    max_stock = float(row.get('最高库存', 0)) if pd.notna(row.get('最高库存')) else 0
    reorder_point = float(row.get('补货点', 0)) if pd.notna(row.get('补货点')) else 0
    is_purchased = to_bool(row.get('采购件'))
    is_produced = to_bool(row.get('生产件'))
    standard_cost = float(row.get('标准成本', 0)) if pd.notna(
        row.get('标准成本')) else 0
    is_active = to_bool(row.get('状态'))

    defaults = {
        'name': name,
        'specification': specification,
        'unit': unit,
        'price': price,
        'material_type': material_type,
        'safety_stock': safety_stock,
        'max_stock': max_stock,
        'reorder_point': reorder_point,
        'is_purchased': is_purchased,
        'is_produced': is_produced,
        'standard_cost': standard_cost,
        'is_active': is_active,
        'company_id': 1,   # 重要：设置公司 ID
    }
    obj, created = Material.objects.update_or_create(
        code=code, defaults=defaults)
    success += 1
    print(f"{'创建' if created else '更新'}: {code} - {name}")

print(f"完成！共处理 {success} 条物料。")
