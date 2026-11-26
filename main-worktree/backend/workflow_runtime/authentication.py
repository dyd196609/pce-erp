from django.conf import settings
from rest_framework import authentication

from system.models import User


class CanaryActorAuthentication(authentication.BaseAuthentication):
    """Isolated-browser role authentication; disabled outside V55.2 test settings."""

    cookie_name = "pce_v552_actor"

    def authenticate(self, request):
        if not getattr(
            settings, "PCE_ACTION_PERMISSION_CANARY_AUTH_ENABLED", False
        ):
            return None
        actor = request.COOKIES.get(self.cookie_name, "").strip()
        if not actor:
            return None
        user = User.objects.filter(username=actor, is_active=True).first()
        if not user:
            return None
        return user, {"testActor": actor, "serverResolved": True}
