from rest_framework import serializers
from .models import Department
from .models import Menu
from .models import Position
from .models import Role


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code", "parent_id", "manager", "is_active"]


class MenuSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = [
            "id",
            "name",
            "code",
            "path",
            "component",
            "icon",
            "parent",
            "sort_order",
            "permission_code",
            "is_active",
            "children",
        ]

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by("sort_order", "id")
        return MenuSerializer(children, many=True).data


class PositionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Position
        fields = ["id", "name", "code", "department_name"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "code", "description"]
