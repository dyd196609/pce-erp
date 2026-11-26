"""
PCE 自定义JWT认证模块
"""
import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import Company, User
from pce_backend.identity_context import credential_context_matches, database_identity

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Authorization格式错误，应为 Bearer <token>')

        token = parts[1]

        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token已过期，请重新登录')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('无效的Token')

        user_id = payload.get('user_id')
        if not user_id:
            raise exceptions.AuthenticationFailed('Token中缺少用户标识')

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('用户不存在或已被禁用')
        if not Company.objects.filter(pk=user.company_id, is_active=True).exists():
            raise exceptions.AuthenticationFailed('所属公司已退出有效经营范围，请联系管理员纠正登录范围。')

        database = database_identity()
        if (
            payload.get('username') != user.username
            or payload.get('database_context') != database['databaseContext']
            or payload.get('database_alias', 'default') != database['databaseAlias']
        ):
            raise exceptions.AuthenticationFailed('数据库运行上下文已变化，请重新登录。')
        if not credential_context_matches(user, payload.get('credential_context')):
            raise exceptions.AuthenticationFailed('账号安全凭据已变化，请重新登录。')

        from sales.followup_models import CustomerAccountBinding

        if CustomerAccountBinding.objects.filter(account=user).exists():
            match = request.resolver_match
            if not match or match.url_name not in {"customer-progress-list", "customer-progress-order", "api_logout"}:
                raise exceptions.PermissionDenied("客户账号仅可访问本客户订单进度。")

        request.pce_auth_context = {
            'backend': f'{self.__class__.__module__}.{self.__class__.__name__}',
            'jwtSubject': payload.get('sub'),
            'jwtUserId': payload.get('user_id'),
            'jwtUsername': payload.get('username'),
            'jwtStableIdentity': payload.get('stable_identity'),
            'jwtDatabaseContext': payload.get('database_context'),
            **database,
        }

        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer'
