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
    supply_type = serializers.CharField(read_only=True)
    supply_type_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Material
        fields = ['id', 'code', 'name', 'purpose', 'specification', 'application_notes',
                  'unit', 'unit_status',
                  'base_uom', 'purchase_uom', 'price',
                  'purchase_unit', 'conversion_rate', 'material_type', 'material_type_display',
                  'category', 'category_name', 'safety_stock', 'max_stock', 'reorder_point',
                  'economic_order_qty', 'lead_time', 'is_purchased', 'is_produced',
                  'supply_type', 'supply_type_display',
                  'cost_method', 'standard_cost', 'last_cost', 'company_id', 'is_active',
                  'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        purchased = attrs.get('is_purchased', getattr(self.instance, 'is_purchased', False))
        produced = attrs.get('is_produced', getattr(self.instance, 'is_produced', False))
        if purchased and produced:
            raise serializers.ValidationError({
                'is_purchased': '采购件与自制件不能同时为真。',
                'is_produced': '采购件与自制件不能同时为真。',
            })
        unit_status = attrs.get('unit_status', getattr(self.instance, 'unit_status', 'confirmed'))
        unit = str(attrs.get('unit', getattr(self.instance, 'unit', '')) or '').strip()
        base_uom = attrs.get('base_uom', getattr(self.instance, 'base_uom', None))
        if unit_status == 'confirmed' and not unit and not base_uom:
            raise serializers.ValidationError({
                'unit_status': '单位已确认时必须维护兼容单位或正式基本单位。',
            })
        if unit_status == 'not_confirmed' and (unit or base_uom):
            raise serializers.ValidationError({
                'unit_status': '单位待维护时不得猜填兼容单位或正式基本单位。',
            })
        return attrs

class CodeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeRule
        fields = '__all__'
        read_only_fields = ('id', 'created_at')
