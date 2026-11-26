from .settings import *  # noqa: F401,F403


PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED = True
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
    "workflow_runtime.authentication.CanaryActorAuthentication",
    "system.authentication.JWTAuthentication",
]
