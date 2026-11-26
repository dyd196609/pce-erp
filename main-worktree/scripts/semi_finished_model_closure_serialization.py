"""Retain full audit timestamp precision in isolated round-trip evidence."""
import datetime
import json


def encoder():
    from django.core.serializers.json import DjangoJSONEncoder

    class FullPrecisionEncoder(DjangoJSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime.datetime, datetime.time)):
                return obj.isoformat()
            return super().default(obj)
    return FullPrecisionEncoder


if __name__ == "__main__":
    from semi_finished_model_closure_runtime import bootstrap, OUT
    bootstrap()
    from django.apps import apps
    from django.core import serializers
    identities = json.loads((OUT / "ISOLATED_CREATED_OBJECTS.json").read_text(encoding="utf-8"))
    objects = [apps.get_model(item["model"]).objects.get(pk=item["pk"]) for item in identities]
    (OUT / "REAL_CASE_ROUNDTRIP_FIXTURE.json").write_text(serializers.serialize("json", objects, indent=2, cls=encoder()) + "\n", encoding="utf-8")
    print(f"Exported {len(objects)} real replay objects with full timestamp precision; database read-only")
