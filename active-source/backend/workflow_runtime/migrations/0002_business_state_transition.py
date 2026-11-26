# Generated for V1.14.2.8.4.7.54.1.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflow_runtime", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessStateTransition",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("business_type", models.CharField(max_length=80)),
                ("business_object_id", models.BigIntegerField()),
                ("from_status", models.CharField(max_length=80)),
                ("to_status", models.CharField(max_length=80)),
                ("action_code", models.CharField(max_length=80)),
                ("transition_version", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "operator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="business_state_transitions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workflow_instance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="business_state_transitions",
                        to="workflow_runtime.workflowinstance",
                    ),
                ),
            ],
            options={
                "db_table": "business_state_transitions",
                "indexes": [
                    models.Index(
                        fields=[
                            "business_type",
                            "business_object_id",
                            "created_at",
                        ],
                        name="idx_business_state_history",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "business_type",
                            "business_object_id",
                            "transition_version",
                        ),
                        name="uniq_business_state_transition_version",
                    ),
                ],
            },
        ),
    ]
