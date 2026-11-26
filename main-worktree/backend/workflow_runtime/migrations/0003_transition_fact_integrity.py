from django.db import migrations, models


REASONS = {
    "submit-formal-payment-order": "approval_submission",
    "approve-formal-payment-order": "final_approval_completed",
    "freeze-formal-payment-order": "execution_facts_frozen",
}


def backfill_authoritative_transition_evidence(apps, schema_editor):
    transition_model = apps.get_model("workflow_runtime", "BusinessStateTransition")
    audit_model = apps.get_model("reconciliation", "BusinessActionAuditRecord")
    for transition in transition_model.objects.all().order_by(
        "object_type",
        "object_id",
        "version",
    ):
        audits = audit_model.objects.filter(
            target_type="formalPaymentOrder",
            target_id=transition.object_id,
            action_code=transition.action_code,
            result="committed",
        ).order_by("created_at", "pk")
        if transition.action_code == "approve-formal-payment-order":
            audits = [
                audit
                for audit in audits
                if (audit.evidence or {}).get("stepNo") == 2
            ]
        else:
            audits = list(audits)
        if len(audits) != 1:
            raise RuntimeError(
                "Cannot bind authoritative audit to transition "
                f"{transition.object_type}:{transition.object_id}:{transition.version}"
            )
        audit = audits[0]
        transition.reason = REASONS.get(
            transition.action_code,
            "authoritative_legacy_transition",
        )
        transition.audit_reference = f"BusinessActionAuditRecord:{audit.pk}"
        transition.save(update_fields=["reason", "audit_reference"])


class Migration(migrations.Migration):

    dependencies = [
        ("reconciliation", "0003_businessdocumentnumberreservation_reusable"),
        ("workflow_runtime", "0002_business_state_transition"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="businessstatetransition",
            name="uniq_business_state_transition_version",
        ),
        migrations.RemoveIndex(
            model_name="businessstatetransition",
            name="idx_business_state_history",
        ),
        migrations.RenameField(
            model_name="businessstatetransition",
            old_name="business_type",
            new_name="object_type",
        ),
        migrations.RenameField(
            model_name="businessstatetransition",
            old_name="business_object_id",
            new_name="object_id",
        ),
        migrations.RenameField(
            model_name="businessstatetransition",
            old_name="from_status",
            new_name="source_state",
        ),
        migrations.RenameField(
            model_name="businessstatetransition",
            old_name="to_status",
            new_name="target_state",
        ),
        migrations.RenameField(
            model_name="businessstatetransition",
            old_name="transition_version",
            new_name="version",
        ),
        migrations.RenameField(
            model_name="businessstatetransition",
            old_name="created_at",
            new_name="timestamp",
        ),
        migrations.AddField(
            model_name="businessstatetransition",
            name="audit_reference",
            field=models.CharField(default="", max_length=160),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="businessstatetransition",
            name="reason",
            field=models.CharField(default="", max_length=240),
            preserve_default=False,
        ),
        migrations.RunPython(
            backfill_authoritative_transition_evidence,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="businessstatetransition",
            index=models.Index(
                fields=["object_type", "object_id", "timestamp"],
                name="idx_business_state_history",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessstatetransition",
            constraint=models.UniqueConstraint(
                fields=("object_type", "object_id", "version"),
                name="uniq_business_state_transition_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessstatetransition",
            constraint=models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="bst_reason_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessstatetransition",
            constraint=models.CheckConstraint(
                condition=~models.Q(audit_reference=""),
                name="bst_audit_reference_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessstatetransition",
            constraint=models.UniqueConstraint(
                fields=("audit_reference",),
                name="uniq_bst_audit_reference",
            ),
        ),
    ]
