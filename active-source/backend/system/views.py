import datetime
import json
import hashlib
import jwt
import logging
import secrets
import uuid
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import authenticate, login, logout
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
from .authorization import user_access_profile
from pce_backend.identity_context import jwt_identity_claims


logger = logging.getLogger(__name__)

AUTH_HANDOFF_TTL_SECONDS = 60
AUTH_HANDOFF_CACHE_PREFIX = "pce:tab-auth-handoff:v1:"


def _authentication_runtime_fingerprint():
    """Return a non-secret correlation fingerprint for server-side diagnosis."""
    configured = Path(settings.DATABASES["default"]["NAME"]).resolve()
    return hashlib.sha256(str(configured).encode("utf-8")).hexdigest()[:16]


def _jwt_for_user(user):
    payload = {
        "user_id": user.id,
        **jwt_identity_claims(user),
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def _user_payload(user):
    from sales.followup_models import CustomerAccountBinding

    if CustomerAccountBinding.objects.filter(account=user).exists():
        return {"id": user.pk, "username": user.username, "real_name": user.real_name,
                "company_id": user.company_id, "customer_portal": True}
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "email": user.email,
        "mobile": user.mobile,
        "company_id": user.company_id,
        "access": user_access_profile(user),
    }


def _handoff_cache_key(code):
    digest = hashlib.sha256(str(code).encode("utf-8")).hexdigest()
    return f"{AUTH_HANDOFF_CACHE_PREFIX}{digest}"


def _legal_handoff_target(value):
    target = str(value or "").strip()
    return target.startswith("/") and not target.startswith("//") and "://" not in target


class TabAuthenticationHandoffIssueView(APIView):
    """Issue a short-lived opaque code to an already authenticated tab."""

    def post(self, request):
        target_path = str(request.data.get("targetPath") or "").strip()
        if not _legal_handoff_target(target_path):
            return Response(
                {"error": "新标签目标必须是当前系统内的合法路径。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code = secrets.token_urlsafe(32)
        cache.set(
            _handoff_cache_key(code),
            {
                "userId": request.user.pk,
                "companyId": request.user.company_id,
                "credentialContext": jwt_identity_claims(request.user),
                "targetPath": target_path,
            },
            timeout=AUTH_HANDOFF_TTL_SECONDS,
        )
        return Response({
            "handoffCode": code,
            "targetPath": target_path,
            "expiresInSeconds": AUTH_HANDOFF_TTL_SECONDS,
        })


class TabAuthenticationHandoffExchangeView(APIView):
    """Consume a single-use code and establish only the receiving tab's JWT."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        code = str(request.data.get("handoffCode") or "").strip()
        target_path = str(request.data.get("targetPath") or "").strip()
        if not code or not _legal_handoff_target(target_path):
            return Response(
                {"error": "新标签身份衔接信息无效。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = _handoff_cache_key(code)
        handoff = cache.get(key)
        # Delete before further validation so every presented code is one-shot.
        cache.delete(key)
        if not isinstance(handoff, dict) or handoff.get("targetPath") != target_path:
            return Response(
                {"error": "新标签身份衔接已失效或已经使用，请从业务流程中心重新打开。"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = User.objects.filter(
            pk=handoff.get("userId"), company_id=handoff.get("companyId"), is_active=True,
        ).first()
        if not user or not Company.objects.filter(pk=user.company_id, is_active=True).exists():
            return Response(
                {"error": "原登录身份已失效，请重新登录。"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if jwt_identity_claims(user) != handoff.get("credentialContext"):
            return Response(
                {"error": "原登录权限上下文已变化，请重新登录。"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({
            "token": _jwt_for_user(user),
            "user": _user_payload(user),
            "targetPath": target_path,
        })


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

        if not Company.objects.filter(pk=user.company_id, is_active=True).exists():
            return Response(
                {"error": "所属公司已退出有效经营范围，请联系管理员纠正登录范围"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = _jwt_for_user(user)
        user_data = _user_payload(user)

        return Response({"token": token, "user": user_data})


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    request_id = uuid.uuid4().hex
    try:
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JsonResponse({"error": "用户名和密码不能为空"}, status=400)

        user = authenticate(request, username=username, password=password)

        if user is None:
            candidate = User.objects.filter(username=username).only(
                "id", "is_active", "company_id", "password",
            ).first()
            logger.warning(
                "authentication_rejected request_id=%s account_id=%s active=%s "
                "company_id=%s password_algorithm=%s database_fingerprint=%s",
                request_id,
                candidate.pk if candidate else None,
                candidate.is_active if candidate else None,
                candidate.company_id if candidate else None,
                (
                    candidate.password.split("$", 1)[0]
                    if candidate and "$" in candidate.password else "unavailable"
                ),
                _authentication_runtime_fingerprint(),
            )
            return JsonResponse({"error": "用户名或密码错误"}, status=401)

        if not Company.objects.filter(pk=user.company_id, is_active=True).exists():
            return JsonResponse(
                {"error": "所属公司已退出有效经营范围，请联系管理员纠正登录范围"},
                status=401,
            )

        from sales.followup_models import CustomerAccountBinding

        customer_portal = CustomerAccountBinding.objects.filter(account=user).exists()
        if not customer_portal:
            login(request, user)
        else:
            logout(request)
        logger.info(
            "authentication_succeeded request_id=%s account_id=%s company_id=%s "
            "database_fingerprint=%s",
            request_id, user.pk, user.company_id, _authentication_runtime_fingerprint(),
        )

        token = _jwt_for_user(user)
        user_data = _user_payload(user)

        return JsonResponse(
            {
                "success": True,
                "token": token,
                "user": user_data,
            }
        )

    except Exception:
        logger.exception("authentication_error request_id=%s", request_id)
        return JsonResponse({"error": "登录服务暂时不可用，请联系管理员。"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_logout(request):
    """Terminate the legacy Django session paired with a browser-held JWT.

    JWT removal remains a client responsibility. Formal APIs authenticate only
    the active tab's bearer token; clearing this cookie is retained as defense
    in depth for non-DRF and older endpoints.
    """
    logout(request)
    return JsonResponse({"success": True})


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
        user_id = payload.get("user_id")
    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"token 无效：{str(e)}"},
            status=401,
        )

    try:
        user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "未找到有效登录账户"}, status=404)

    if user.is_superuser:
        menu_ids = list(Menu.objects.filter(is_active=True).values_list("id", flat=True))
    else:
        role_codes = user_access_profile(user)["roles"]
        menu_ids = list(RoleMenu.objects.filter(
            role__code__in=role_codes,
        ).values_list("menu_id", flat=True).distinct())

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
