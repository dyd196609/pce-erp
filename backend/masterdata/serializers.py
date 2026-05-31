from rest_framework import serializers
from .models import MaterialCategory, Material, CodeRule

class MaterialCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = MaterialCategory
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'parent_name')        


class MaterialSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    material_type_display = serializers.CharField(source='get_material_type_display', read_only=True)
    
    class Meta:
        model = Material
        fields = ['id', 'code', 'name', 'specification', 'unit', 'price',   # 🔴 添加 price
                  'purchase_unit', 'conversion_rate', 'material_type', 'material_type_display',
                  'category', 'category_name', 'safety_stock', 'max_stock', 'reorder_point',
                  'economic_order_qty', 'lead_time', 'is_purchased', 'is_produced',
                  'cost_method', 'standard_cost', 'last_cost', 'company_id', 'is_active',
                  'created_by', 'created_at', 'updated_at']

class CodeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeRule
        fields = '__all__'
        read_only_fields = ('id', 'created_at')