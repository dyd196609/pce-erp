"""Preview, apply, or read back the Material 130 canonical convergence."""

import json

from django.core.management.base import BaseCommand, CommandError

from masterdata.canonical_material_convergence_service import (
    CanonicalMaterialConvergenceError,
    apply_canonical_material_convergence,
    preview_canonical_material_convergence,
    readback_canonical_material_convergence,
)
from system.models import User


class Command(BaseCommand):
    help = "Use the formal Material Master service; default mode is zero-write preview."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true")
        mode.add_argument("--readback", action="store_true")

    def handle(self, *args, **options):
        actor = User.objects.filter(
            username=options["actor"], is_active=True,
        ).first()
        if not actor:
            raise CommandError("FORMAL_ACTOR_NOT_FOUND")
        try:
            if options["apply"]:
                result = apply_canonical_material_convergence(user=actor)
            elif options["readback"]:
                result = readback_canonical_material_convergence(user=actor)
            else:
                result = preview_canonical_material_convergence(user=actor)
        except CanonicalMaterialConvergenceError as exc:
            raise CommandError(json.dumps({
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }, ensure_ascii=False, default=str)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
