"""
PCE 自定义JWT认证模块
"""
import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import User

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

        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer'