"""
掌云智造 PCE 后端配置文件
系统简称：PCE
项目路径：E:\Dev-PCE\Source\backend
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 安全密钥（生产环境请修改为随机字符串）
SECRET_KEY = "django-insecure-pce-change-this-to-random-string"

# 调试模式（开发环境为True）
DEBUG = True

# 允许访问的主机（* 表示所有，仅开发用）
ALLOWED_HOSTS = ["*"]

# 注册的应用
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "system",
    "pfm",
    "masterdata",
    "procurement",
    "purchase",
]

# 中间件
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 根URL配置
ROOT_URLCONF = "pce_backend.urls"

# 模板配置
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI入口
WSGI_APPLICATION = "pce_backend.wsgi.application"

# ========================
# 数据库配置（请修改密码）
# ========================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# 密码验证（Django内置）
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# 语言和时区
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = False

# 静态文件
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",  # 如果项目级 static 目录存在
]
# 或者使用应用内的 static 目录，Django 会自动发现

# 默认主键类型
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ========================
# Django REST Framework 配置
# ========================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "system.authentication.JWTAuthentication",  # 自定义JWT认证
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",  # 恢复需要登录
    ],
    "DEFAULT_PAGINATION_CLASS": "purchase.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 10,
}

# 跨域配置（开发环境允许所有来源）
CORS_ALLOW_ALL_ORIGINS = True

# JWT配置
JWT_SECRET_KEY = SECRET_KEY
JWT_EXPIRATION_HOURS = 24

# 系统名称
PCE_SYSTEM_NAME = "掌云智造"
PCE_SYSTEM_SHORT = "PCE"

# 自定义用户模型
AUTH_USER_MODEL = "system.User"
