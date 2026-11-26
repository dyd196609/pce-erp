from .canary_demo_settings import *  # noqa: F401,F403


PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED = True
PCE_ACTION_PERMISSION_ENFORCED = True
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [  # noqa: F405
    "workflow_runtime.authentication.CanaryActorAuthentication",
    "system.authentication.JWTAuthentication",
]
