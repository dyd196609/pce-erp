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
    "reconciliation",
    "supplier_performance",
    "purchase_invoice_prepare",
    "purchase_accounts_payable_draft",
    "payable_confirmation_prepare",
    "payment_request_prepare",
    "workflow_runtime",
    "payment_request",
    "payment_instruction_prepare",
    "payment_order_prepare",
    "payment_order_draft",
    "payment_risk_review",
    "formal_payment_order",
    "bank_send_preparation",
    "bank_send_task",
    "bank_send_execution_gate",
    "bank_send_request",
    "bank_send_execution_simulation",
    "purchase_canary",
    "pde",
    "planning",
    "sales",
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
        # Validation runners set this to an isolated temporary database. The
        # default remains the existing developer database and is never used by
        # the production-persistence gate.
        "NAME": os.environ.get("PCE_DATABASE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"timeout": 30},
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

PCE_PAYMENT_INSTRUCTION_PREPARE_FEATURE_ENABLED = True
PCE_PAYMENT_INSTRUCTION_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False
PCE_PAYMENT_INSTRUCTION_PREPARE_TEST_TENANTS = {"tenant-canary-demo"}
PCE_PAYMENT_INSTRUCTION_PREPARE_FAILURE_INJECTION_ENABLED = DEBUG
PCE_PAYMENT_ORDER_PREPARE_FEATURE_ENABLED = os.environ.get(
    "PCE_PAYMENT_ORDER_PREPARE_FEATURE_ENABLED", "0"
) == "1"
PCE_PAYMENT_ORDER_PREPARE_PRODUCTION_ROLLOUT_ENABLED = False
PCE_PAYMENT_ORDER_PREPARE_TEST_TENANTS = {
    value.strip()
    for value in os.environ.get("PCE_PAYMENT_ORDER_PREPARE_TEST_TENANTS", "").split(",")
    if value.strip()
}

# A process that declares the unified non-production acceptance profile must
# never fall back to backend/db.sqlite3 or a mismatched database identity.
from pde.acceptance_isolation import verify_declared_acceptance_runtime
verify_declared_acceptance_runtime(DATABASES)
PCE_PAYMENT_ORDER_PREPARE_FAILURE_INJECTION_ENABLED = DEBUG
PCE_PAYMENT_ORDER_DRAFT_FEATURE_ENABLED = os.environ.get(
    "PCE_PAYMENT_ORDER_DRAFT_FEATURE_ENABLED", "0"
) == "1"
PCE_PAYMENT_ORDER_DRAFT_PRODUCTION_ROLLOUT_ENABLED = False
PCE_PAYMENT_ORDER_DRAFT_TEST_TENANTS = {
    value.strip()
    for value in os.environ.get("PCE_PAYMENT_ORDER_DRAFT_TEST_TENANTS", "").split(",")
    if value.strip()
}
PCE_PAYMENT_ORDER_DRAFT_FAILURE_INJECTION_ENABLED = DEBUG
PCE_PAYMENT_RISK_REVIEW_FEATURE_ENABLED = os.environ.get(
    "PCE_PAYMENT_RISK_REVIEW_FEATURE_ENABLED", "0"
) == "1"
PCE_PAYMENT_RISK_REVIEW_PRODUCTION_ROLLOUT_ENABLED = False
PCE_PAYMENT_RISK_REVIEW_TEST_TENANTS = {
    value.strip()
    for value in os.environ.get("PCE_PAYMENT_RISK_REVIEW_TEST_TENANTS", "").split(",")
    if value.strip()
}
PCE_PAYMENT_RISK_REVIEW_FAILURE_INJECTION_ENABLED = DEBUG
PCE_FORMAL_PAYMENT_ORDER_FEATURE_ENABLED = os.environ.get(
    "PCE_FORMAL_PAYMENT_ORDER_FEATURE_ENABLED", "0"
) == "1"
PCE_FORMAL_PAYMENT_ORDER_PRODUCTION_ROLLOUT_ENABLED = False
PCE_FORMAL_PAYMENT_ORDER_TEST_TENANTS = {
    value.strip()
    for value in os.environ.get("PCE_FORMAL_PAYMENT_ORDER_TEST_TENANTS", "").split(",")
    if value.strip()
}
PCE_FORMAL_PAYMENT_ORDER_FAILURE_INJECTION_ENABLED = DEBUG
PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED = False
PCE_ACTION_PERMISSION_ENFORCED = True
PCE_BANK_SEND_REQUEST_FEATURE_ENABLED = os.environ.get(
    "PCE_BANK_SEND_REQUEST_FEATURE_ENABLED", "0"
) == "1"
PCE_BANK_SEND_REQUEST_PRODUCTION_ROLLOUT_ENABLED = False
PCE_BANK_SEND_REQUEST_TEST_TENANTS = {
    value.strip()
    for value in os.environ.get("PCE_BANK_SEND_REQUEST_TEST_TENANTS", "").split(",")
    if value.strip()
}

# ========================
# Django REST Framework 配置
# ========================
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "workflow_runtime.exception_handler.pce_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "system.authentication.JWTAuthentication",  # 自定义JWT认证
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",  # 恢复需要登录
    ],
    "DEFAULT_PAGINATION_CLASS": "purchase.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 10,
}

# 跨域配置：客户端统一使用 credentials 模式，响应不得使用通配来源。
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "PCE_CORS_ALLOWED_ORIGINS",
        ",".join(
            (
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8069",
                "http://127.0.0.1:8070",
            )
        ),
    ).split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "PCE_CSRF_TRUSTED_ORIGINS",
        ",".join(
            (
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8069",
                "http://127.0.0.1:8070",
            )
        ),
    ).split(",")
    if origin.strip()
]

# JWT配置
JWT_SECRET_KEY = SECRET_KEY
JWT_EXPIRATION_HOURS = 24

# 系统名称
PCE_SYSTEM_NAME = "掌云智造"
PCE_SYSTEM_SHORT = "PCE"

# Enterprise Procurement Default Tax Rate is the single governed fallback for
# supplier effective prices when the authoritative quotation line has no tax.
PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE = os.environ.get(
    "PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE", "13"
)

# 自定义用户模型
AUTH_USER_MODEL = "system.User"

# Purchase-reconciliation formal persistence is deny-by-default. A test tenant
# still needs both the server feature flag and explicit allow-list membership.
PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED = os.environ.get(
    "PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED", "0"
) == "1"
PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PURCHASE_RECONCILIATION_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get("PCE_PURCHASE_RECONCILIATION_TEST_TENANTS", "").split(",")
    if item.strip()
}
PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED", "0"
) == "1"

# Purchase-invoice-prepare generation is test-tenant only until a later
# production rollout explicitly enables it.
PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED = os.environ.get(
    "PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED", "0"
) == "1"
PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get("PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS", "").split(",")
    if item.strip()
}
PCE_PURCHASE_INVOICE_PREPARE_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PURCHASE_INVOICE_PREPARE_FAILURE_INJECTION_ENABLED", "0"
) == "1"

# Payment-request approval is test-tenant only until production rollout is
# explicitly enabled. The web client cannot override these server settings.
PCE_PAYMENT_REQUEST_FEATURE_ENABLED = os.environ.get(
    "PCE_PAYMENT_REQUEST_FEATURE_ENABLED", "0"
) == "1"
PCE_PAYMENT_REQUEST_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PAYMENT_REQUEST_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PAYMENT_REQUEST_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get("PCE_PAYMENT_REQUEST_TEST_TENANTS", "").split(",")
    if item.strip()
}
PCE_PAYMENT_REQUEST_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PAYMENT_REQUEST_FAILURE_INJECTION_ENABLED", "0"
) == "1"

# V44 invoice-data collection and validation remains deny-by-default and is
# independently authorized from invoice-prepare generation.
PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED = os.environ.get(
    "PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED", "0"
) == "1"
PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get("PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS", "").split(",")
    if item.strip()
}
PCE_PURCHASE_INVOICE_VALIDATION_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PURCHASE_INVOICE_VALIDATION_FAILURE_INJECTION_ENABLED", "0"
) == "1"

# V45 purchase accounts-payable-draft generation is independently
# deny-by-default and test-tenant scoped until a later production rollout.
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED = os.environ.get(
    "PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED", "0"
) == "1"
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get(
        "PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS", ""
    ).split(",")
    if item.strip()
}
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED", "0"
) == "1"
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_COUNT = int(
    os.environ.get("PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_COUNT", "3")
)
PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_INTERVAL_MS = int(
    os.environ.get(
        "PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_SQLITE_RETRY_INTERVAL_MS", "50"
    )
)

PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED = os.environ.get(
    "PCE_PAYABLE_CONFIRMATION_PREPARE_FEATURE_ENABLED", "0"
) == "1"
PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PAYABLE_CONFIRMATION_PREPARE_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get(
        "PCE_PAYABLE_CONFIRMATION_PREPARE_TEST_TENANTS", ""
    ).split(",")
    if item.strip()
}
PCE_PAYABLE_CONFIRMATION_PREPARE_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PAYABLE_CONFIRMATION_PREPARE_FAILURE_INJECTION_ENABLED", "0"
) == "1"
PCE_PAYABLE_CONFIRMATION_PREPARE_SQLITE_RETRY_COUNT = int(
    os.environ.get("PCE_PAYABLE_CONFIRMATION_PREPARE_SQLITE_RETRY_COUNT", "3")
)
PCE_PAYABLE_CONFIRMATION_PREPARE_SQLITE_RETRY_INTERVAL_MS = int(
    os.environ.get(
        "PCE_PAYABLE_CONFIRMATION_PREPARE_SQLITE_RETRY_INTERVAL_MS", "50"
    )
)

PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED = os.environ.get(
    "PCE_PAYMENT_REQUEST_PREPARE_FEATURE_ENABLED", "0"
) == "1"
PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED = os.environ.get(
    "PCE_PAYMENT_REQUEST_PREPARE_PRODUCTION_ROLLOUT_ENABLED", "0"
) == "1"
PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS = {
    item.strip()
    for item in os.environ.get(
        "PCE_PAYMENT_REQUEST_PREPARE_TEST_TENANTS", ""
    ).split(",")
    if item.strip()
}
PCE_PAYMENT_REQUEST_PREPARE_FAILURE_INJECTION_ENABLED = os.environ.get(
    "PCE_PAYMENT_REQUEST_PREPARE_FAILURE_INJECTION_ENABLED", "0"
) == "1"
PCE_PAYMENT_REQUEST_PREPARE_SQLITE_RETRY_COUNT = int(
    os.environ.get("PCE_PAYMENT_REQUEST_PREPARE_SQLITE_RETRY_COUNT", "3")
)
PCE_PAYMENT_REQUEST_PREPARE_SQLITE_RETRY_INTERVAL_MS = int(
    os.environ.get(
        "PCE_PAYMENT_REQUEST_PREPARE_SQLITE_RETRY_INTERVAL_MS", "50"
    )
)
