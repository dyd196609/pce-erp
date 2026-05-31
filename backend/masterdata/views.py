import uuid
import pandas as pd
from django.http import HttpResponse
from io import BytesIO
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import MaterialCategory, Material, CodeRule
from .serializers import MaterialCategorySerializer, MaterialSerializer, CodeRuleSerializer


class MaterialPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class MaterialCategoryViewSet(viewsets.ModelViewSet):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MaterialPagination

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def export_template(self, request):
        """下载导入模板（Excel）"""
        df = pd.DataFrame({
            '序号': [1],
            '物料编码': ['MT001'],
            '物料名称': ['示例物料'],
            '规格型号': ['规格ABC-123'],
            '单位': ['个'],
            '单价': [100.00],
            '物料类型': ['成品'],
            '物料分类': ['电子设备'],
            '安全库存': [10],
            '最高库存': [100],
            '补货点': [20],
            '采购件': ['是'],
            '生产件': ['是'],
            '标准成本': [80.00],
            '状态': ['启用'],
        })

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='物料模板', index=False)

        response = HttpResponse(output.getvalue(
        ), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="material_template.xlsx"'
        return response

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """导入 Excel 或 CSV 文件"""
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        file_name = file.name.lower()
        try:
            if file_name.endswith('.csv'):
                df = pd.read_csv(file, encoding='utf-8')
            else:
                df = pd.read_excel(file, engine='openpyxl')
                # ========== 调试打印 ==========
                print("=== 导入调试 ===")
                print("总行数:", len(df))
                print("列名:", list(df.columns))
                if len(df) > 0:
                    print("第一行数据:", df.iloc[0].to_dict())
                else:
                    print("第一行数据: 无数据")
                # ========== 调试结束 ==========
        except Exception as e:
            return Response({'error': f'文件解析失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        success_count = 0
        errors = []

        for index, row in df.iterrows():
            try:
                # 基本字段校验
                code = str(row.get('物料编码', '')).strip()
                name = str(row.get('物料名称', '')).strip()
                unit = str(row.get('单位', '')).strip()
                if not code or not name or not unit:
                    errors.append(f'第{index+2}行：物料编码、物料名称、单位不能为空')
                    continue

                if Material.objects.filter(code=code).exists():
                    errors.append(f'第{index+2}行：物料编码 {code} 已存在')
                    continue

                # ========== 处理物料分类 ==========
                # ... 在 for 循环内部，处理物料分类
                category_name = str(row.get('物料分类', '')).strip()
                category = None
                if category_name:
                    try:
                        # 准备创建分类时所需的默认值（根据你的模型字段）
                        defaults = {
                            'code': f"IMP_{uuid.uuid4().hex[:8]}",  # 生成唯一 code
                            'company_id': 1,                       # 根据你的业务设定
                            'sort_order': 0,
                            'is_active': True,
                            # 注意：没有 description 字段，不要加
                        }
                        category, created = MaterialCategory.objects.get_or_create(
                            name=category_name,
                            defaults=defaults
                        )
                        if created:
                            print(
                                f"新建分类: {category_name} (code={defaults['code']})")
                    except Exception as e:
                        errors.append(f'第{index+2}行：处理物料分类失败 - {str(e)}')
                        continue
                # ==================================

                # 物料类型映射
                material_type_raw = str(row.get('物料类型', '原材料')).strip()
                if material_type_raw == '成品':
                    material_type_code = 'finished'
                elif material_type_raw == '耗材':
                    material_type_code = 'auxiliary'
                elif material_type_raw == '固定资产':
                    material_type_code = 'fixed'
                else:
                    material_type_code = 'raw'

                # 采购件/生产件
                is_purchased = str(row.get('采购件', '否')).strip() in [
                    '是', 'true', '1', 'True']
                is_produced = str(row.get('生产件', '否')).strip() in [
                    '是', 'true', '1', 'True']

                # 创建物料对象
                material = Material(
                    code=code,
                    name=name,
                    specification=str(row.get('规格型号', '')) if pd.notna(
                        row.get('规格型号')) else '',
                    unit=unit,
                    price=float(row.get('单价', 0)) if pd.notna(
                        row.get('单价')) else 0,
                    material_type=material_type_code,
                    safety_stock=float(row.get('安全库存', 0)) if pd.notna(
                        row.get('安全库存')) else 0,
                    max_stock=float(row.get('最高库存', 0)) if pd.notna(
                        row.get('最高库存')) else 0,
                    reorder_point=float(row.get('补货点', 0)) if pd.notna(
                        row.get('补货点')) else 0,
                    is_purchased=is_purchased,
                    is_produced=is_produced,
                    standard_cost=float(row.get('标准成本', 0)) if pd.notna(
                        row.get('标准成本')) else 0,
                    company_id=1,
                    is_active=True,
                    # ========== 重要：根据实际模型字段名填写 ==========
                    # 如果 Material 模型中的外键字段名是 'category'，则保留下面一行
                    # 如果是 'material_category'，请将 'category' 改为 'material_category'
                    category=category,
                    # =================================================
                )
                material.save()
                success_count += 1
            except Exception as e:
                errors.append(f'第{index+2}行：{str(e)}')
                import traceback
                traceback.print_exc()

        return Response({
            'success': success_count,
            'errors': errors,
            'total': len(df)
        })


class CodeRuleViewSet(viewsets.ModelViewSet):
    queryset = CodeRule.objects.all()
    serializer_class = CodeRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
