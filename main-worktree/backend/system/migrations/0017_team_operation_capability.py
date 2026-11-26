import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pfm", "0003_enterprise_organization_model_v1"),
        ("system", "0016_process_display_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="effective_from",
            field=models.DateField(blank=True, null=True, verbose_name="生效日期"),
        ),
        migrations.AddField(
            model_name="team",
            name="effective_to",
            field=models.DateField(blank=True, null=True, verbose_name="失效日期"),
        ),
        migrations.AlterField(
            model_name="process",
            name="team",
            field=models.ForeignKey(
                blank=True,
                help_text="仅保留旧数据兼容；正式可承担班组由工序班组能力关系维护。",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="processes",
                to="system.team",
                verbose_name="旧版默认班组（兼容）",
            ),
        ),
        migrations.CreateModel(
            name="ProcessTeamCapability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("note", models.CharField(blank=True, max_length=240, verbose_name="能力与安排说明")),
                ("operation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="team_capabilities", to="system.process", verbose_name="工序")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operation_capabilities", to="system.team", verbose_name="班组")),
            ],
            options={
                "verbose_name": "工序班组能力关系",
                "verbose_name_plural": "工序班组能力关系",
            },
        ),
        migrations.CreateModel(
            name="TeamMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role_label", models.CharField(blank=True, max_length=80, verbose_name="班组内角色")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="team_memberships", to="pfm.employee", verbose_name="员工")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="system.team", verbose_name="班组")),
            ],
            options={
                "verbose_name": "班组成员关系",
                "verbose_name_plural": "班组成员关系",
            },
        ),
        migrations.AddConstraint(
            model_name="processteamcapability",
            constraint=models.UniqueConstraint(fields=("operation", "team", "effective_from"), name="uniq_system_process_team_capability_period"),
        ),
        migrations.AddConstraint(
            model_name="teammembership",
            constraint=models.UniqueConstraint(fields=("team", "employee", "effective_from"), name="uniq_system_team_membership_period"),
        ),
    ]
