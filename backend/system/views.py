import datetime
import json
import jwt

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import (
    User,
    Department,
    Position,
    Role,
    Permission,
    Menu,
    RoleMenu,
    Company,
    Workshop,
    Team,
    Process,
)
from .serializers import MenuSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "用户名和密码不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "用户名或密码错误"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"error": "用户名或密码错误"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "用户已被禁用"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        payload = {
            "user_id": user.id,
            "username": user.username,
            "exp": datetime.datetime.utcnow()
            + datetime.timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

        user_data = {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "email": user.email,
            "mobile": user.mobile,
            "company_id": user.company_id,
        }

        return Response({"token": token, "user": user_data})


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    try:
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JsonResponse({"error": "用户名和密码不能为空"}, status=400)

        user = authenticate(request, username=username, password=password)

        if user is None:
            return JsonResponse({"error": "用户名或密码错误"}, status=401)

        login(request, user)

        payload = {
            "user_id": user.id,
            "username": user.username,
            "exp": datetime.datetime.utcnow()
            + datetime.timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

        user_data = {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "email": user.email,
            "mobile": user.mobile,
            "company_id": user.company_id,
        }

        return JsonResponse(
            {
                "success": True,
                "token": token,
                "user": user_data,
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def group_suggestions(request):
    groups = Group.objects.all()
    suggestions = set()

    for group in groups:
        suggestions.add(group.name)

    return JsonResponse({"suggestions": sorted(suggestions)})


@csrf_exempt
@require_http_methods(["GET"])
def department_list(request):
    departments = Department.objects.filter(is_active=True).order_by("id")

    data = []
    for dept in departments:
        data.append(
            {
                "id": dept.id,
                "name": dept.name,
                "code": dept.code,
                "parent_id": dept.parent_id,
                "manager": dept.manager,
                "is_active": dept.is_active,
            }
        )

    return JsonResponse(data, safe=False)


@csrf_exempt
@require_http_methods(["GET"])
def position_list(request):
    positions = Position.objects.filter(is_active=True).order_by("id")

    data = []
    for position in positions:
        data.append(
            {
                "id": position.id,
                "name": position.name,
                "code": position.code,
                "department_name": (
                    position.department.name if position.department else ""
                ),
                "is_active": position.is_active,
            }
        )

    return JsonResponse({"success": True, "data": data})


@csrf_exempt
@require_http_methods(["GET"])
def role_list(request):
    roles = Role.objects.all().order_by("id")

    data = []
    for role in roles:
        data.append(
            {
                "id": role.id,
                "name": role.name,
                "code": role.code,
                "description": role.description,
            }
        )

    return JsonResponse({"success": True, "data": data})


@csrf_exempt
@require_http_methods(["GET"])
def permission_list(request):
    permissions = Permission.objects.all().order_by("module", "id")

    data = []
    for permission in permissions:
        data.append(
            {
                "id": permission.id,
                "code": permission.code,
                "name": permission.name,
                "module": permission.module,
            }
        )

    return JsonResponse({"success": True, "data": data})


@csrf_exempt
@require_http_methods(["GET"])
def user_list(request):
    users = User.objects.all().order_by("id")

    data = []
    for user in users:
        data.append(
            {
                "id": user.id,
                "username": user.username,
                "real_name": user.real_name,
                "email": user.email or "",
                "mobile": user.mobile or "",
                "company_id": user.company_id,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
            }
        )

    return JsonResponse({"success": True, "data": data})


class MenuTreeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        menus = Menu.objects.filter(parent__isnull=True, is_active=True).order_by(
            "sort_order", "id"
        )

        serializer = MenuSerializer(menus, many=True)
        return Response({"success": True, "data": serializer.data})


@csrf_exempt
@require_http_methods(["GET"])
def org_tree(request):
    companies = Company.objects.filter(is_active=True).order_by("id")
    result = []

    for company in companies:
        company_node = {
            "id": f"company-{company.id}",
            "label": company.name,
            "type": "company",
            "children": [],
        }

        departments = Department.objects.filter(
            company=company,
            parent__isnull=True,
            is_active=True,
        ).order_by("id")

        for department in departments:
            company_node["children"].append(build_department_node(department))

        result.append(company_node)

    return JsonResponse({"success": True, "data": result})


def build_department_node(department):
    node = {
        "id": f"department-{department.id}",
        "label": department.name,
        "type": "department",
        "children": [],
    }

    child_departments = Department.objects.filter(
        parent=department,
        is_active=True,
    ).order_by("id")

    for child in child_departments:
        node["children"].append(build_department_node(child))

    workshops = Workshop.objects.filter(
        department=department,
        is_active=True,
    ).order_by("id")

    for workshop in workshops:
        workshop_node = {
            "id": f"workshop-{workshop.id}",
            "label": workshop.name,
            "type": "workshop",
            "children": [],
        }

        teams = Team.objects.filter(
            workshop=workshop,
            is_active=True,
        ).order_by("id")

        for team in teams:
            team_node = {
                "id": f"team-{team.id}",
                "label": team.name,
                "type": "team",
                "children": [],
            }

            processes = Process.objects.filter(
                team=team,
                is_active=True,
            ).order_by("id")

            for process in processes:
                team_node["children"].append(
                    {
                        "id": f"process-{process.id}",
                        "label": process.name,
                        "type": "process",
                        "children": [],
                    }
                )

            workshop_node["children"].append(team_node)

        node["children"].append(workshop_node)

    return node


@csrf_exempt
@require_http_methods(["GET"])
def role_menu_ids(request, role_id):
    menu_ids = list(
        RoleMenu.objects.filter(role_id=role_id).values_list("menu_id", flat=True)
    )

    return JsonResponse({"success": True, "data": menu_ids})


@csrf_exempt
@require_http_methods(["POST"])
def save_role_menus(request, role_id):
    try:
        data = json.loads(request.body)
        menu_ids = data.get("menu_ids", [])

        RoleMenu.objects.filter(role_id=role_id).delete()

        for menu_id in menu_ids:
            RoleMenu.objects.create(role_id=role_id, menu_id=menu_id)

        return JsonResponse({"success": True, "message": "角色菜单保存成功"})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def my_menus(request):
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return JsonResponse({"success": False, "error": "未提供登录 token"}, status=401)

    token = auth_header.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        username = payload.get("username")
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"token 无效：{str(e)}"},
            status=401,
        )

    if username == "admin":
        role_code = "superadmin"
    else:
        role_code = "employee"

    try:
        role = Role.objects.get(code=role_code)
    except Role.DoesNotExist:
        return JsonResponse({"success": False, "error": "未找到用户角色"}, status=404)

    menu_ids = list(
        RoleMenu.objects.filter(role=role).values_list("menu_id", flat=True)
    )

    menus = Menu.objects.filter(
        id__in=menu_ids,
        is_active=True,
    )

    parent_ids = set()
    for menu in menus:
        current = menu.parent
        while current:
            parent_ids.add(current.id)
            current = current.parent

    final_ids = set(menu_ids) | parent_ids

    root_menus = Menu.objects.filter(
        parent__isnull=True,
        id__in=final_ids,
        is_active=True,
    ).order_by("sort_order", "id")

    def build_menu_node(menu):
        children = Menu.objects.filter(
            parent=menu,
            id__in=final_ids,
            is_active=True,
        ).order_by("sort_order", "id")

        return {
            "id": menu.id,
            "name": menu.name,
            "code": menu.code,
            "path": menu.path,
            "component": menu.component,
            "icon": menu.icon,
            "parent": menu.parent_id,
            "sort_order": menu.sort_order,
            "permission_code": menu.permission_code,
            "is_active": menu.is_active,
            "children": [build_menu_node(child) for child in children],
        }

    data = [build_menu_node(menu) for menu in root_menus]

    return JsonResponse({"success": True, "data": data})
