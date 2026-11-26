"""Canonical material configuration candidate. Isolated migration authorization only.

No product aliases, formula engine or duplicate material-requirement tables.
"""
from django.core.exceptions import ValidationError
from django.db import models


class MaterialConfiguration(models.Model):
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    material = models.ForeignKey("masterdata.Material", on_delete=models.PROTECT, related_name="manufacturing_configurations")
    source_identity = models.OneToOneField("masterdata.ExternalIdentity", on_delete=models.PROTECT, related_name="material_configuration")
    configuration_code = models.CharField(max_length=120)
    source_validated = models.BooleanField(default=False)
    validation_reference = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_material_configuration"
        constraints = [models.UniqueConstraint(fields=("company", "configuration_code"), name="pde_mat_config_company_code_unique")]

    def clean(self):
        if self.material.company_id != self.company_id or self.source_identity.organization_id != self.company_id:
            raise ValidationError("配置、正式物料、来源身份必须属于同一公司")
        if self.material.material_type != "semi":
            raise ValidationError("当前配置只适用于正式半成品Material")
        if self.source_identity.mapping_status != "MATCH" or self.source_identity.target_entity_type != "materials" or str(self.material_id) != self.source_identity.target_entity_id:
            raise ValidationError("配置来源身份必须精确指向同一Material")
        if self.source_validated and not self.validation_reference:
            raise ValidationError("人工确认必须保留真实裁决来源")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialConfigurationAttribute(models.Model):
    class Kind(models.TextChoices):
        PROCESS = "paintProcess", "油漆工艺"
        COLOR = "color", "颜色 / 色板"
        VENEER = "veneer", "木皮"
        SUBSTRATE = "substrate", "坯板材料族"
        SPLICE = "splice", "是否拼皮"
        SKIN = "skinFeel", "是否肤感"
        PAINT = "paintKind", "油漆材料"
        UOM = "uom", "基本单位"

    class Knowledge(models.TextChoices):
        TRUE = "KNOWN_TRUE", "是（已知）"
        FALSE = "KNOWN_FALSE", "否（已知）"
        UNKNOWN = "UNKNOWN", "未知"
        NA = "NOT_APPLICABLE", "不适用"

    class Resolution(models.TextChoices):
        RESOLVED = "RESOLVED", "正式身份已解析"
        UNRESOLVED = "UNRESOLVED", "正式身份待解析"
        NA = "NOT_APPLICABLE", "不需要正式对象身份"

    configuration = models.ForeignKey(MaterialConfiguration, on_delete=models.PROTECT, related_name="attributes")
    attribute_kind = models.CharField(max_length=24, choices=Kind.choices)
    source_value = models.TextField(null=True, blank=True)
    canonical_value = models.TextField(null=True, blank=True)
    knowledge_state = models.CharField(max_length=24, choices=Knowledge.choices, default=Knowledge.UNKNOWN)
    resolution_status = models.CharField(max_length=24, choices=Resolution.choices, default=Resolution.UNRESOLVED)
    formal_material = models.ForeignKey("masterdata.Material", on_delete=models.PROTECT, null=True, blank=True, related_name="configuration_attribute_links")
    process_type = models.ForeignKey("pde.ManufacturingProcessType", on_delete=models.PROTECT, null=True, blank=True)
    material_family = models.ForeignKey("masterdata.MaterialCategory", on_delete=models.PROTECT, null=True, blank=True)
    uom = models.ForeignKey("masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True)
    source_file = models.CharField(max_length=240)
    source_sha256 = models.CharField(max_length=64)
    source_sheet = models.CharField(max_length=120)
    source_cell = models.CharField(max_length=24)
    source_validated = models.BooleanField(default=False)
    validation_reference = models.TextField(blank=True)
    provenance = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "pde_material_configuration_attribute"
        constraints = [
            models.UniqueConstraint(fields=("configuration", "attribute_kind"), name="pde_mat_config_attr_unique"),
            models.CheckConstraint(condition=models.Q(attribute_kind__in=("paintProcess", "color", "veneer", "substrate", "splice", "skinFeel", "paintKind", "uom")), name="pde_mat_attr_kind_valid"),
            models.CheckConstraint(condition=models.Q(knowledge_state__in=("KNOWN_TRUE", "KNOWN_FALSE", "UNKNOWN", "NOT_APPLICABLE")), name="pde_mat_attr_knowledge_valid"),
            models.CheckConstraint(condition=models.Q(resolution_status__in=("RESOLVED", "UNRESOLVED", "NOT_APPLICABLE")), name="pde_mat_attr_resolution_valid"),
            models.CheckConstraint(condition=(models.Q(resolution_status="RESOLVED") | models.Q(formal_material__isnull=True, process_type__isnull=True, material_family__isnull=True, uom__isnull=True)), name="pde_mat_attr_unresolved_no_fk"),
            models.CheckConstraint(condition=(
                models.Q(attribute_kind="paintProcess", formal_material__isnull=True, material_family__isnull=True, uom__isnull=True)
                | models.Q(attribute_kind="substrate", formal_material__isnull=True, process_type__isnull=True, uom__isnull=True)
                | models.Q(attribute_kind="uom", formal_material__isnull=True, process_type__isnull=True, material_family__isnull=True)
                | models.Q(attribute_kind__in=("veneer", "paintKind"), process_type__isnull=True, material_family__isnull=True, uom__isnull=True)
                | models.Q(attribute_kind__in=("color", "splice", "skinFeel"), formal_material__isnull=True, process_type__isnull=True, material_family__isnull=True, uom__isnull=True)
            ), name="pde_mat_attr_typed_target_valid"),
        ]

    def clean(self):
        company = self.configuration.company_id
        for target in (self.formal_material, self.process_type, self.material_family, self.uom):
            if target and target.company_id != company:
                raise ValidationError("属性正式目标必须属于配置所在公司")
        if self.attribute_kind in ("splice", "skinFeel"):
            if self.knowledge_state == "UNKNOWN" and self.canonical_value is not None:
                raise ValidationError("未知布尔属性不得补默认值")
            if self.resolution_status != "NOT_APPLICABLE":
                raise ValidationError("布尔属性是受控状态，不伪造Material身份")
        elif self.knowledge_state in ("KNOWN_TRUE", "KNOWN_FALSE"):
            raise ValidationError("是/否状态只用于拼皮与肤感")
        if self.resolution_status == "RESOLVED" and sum(x is not None for x in (self.formal_material_id, self.process_type_id, self.material_family_id, self.uom_id)) != 1:
            raise ValidationError("已解析属性必须引用唯一且类型正确的正式目标")
        if self.source_validated and not self.validation_reference:
            raise ValidationError("来源业务确认必须保留裁决出处")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialFamilyAllowedMaterial(models.Model):
    """Explicit admissible material/specification, never all-Material geometry search."""
    family = models.ForeignKey("masterdata.MaterialCategory", on_delete=models.PROTECT, related_name="allowed_materials")
    material = models.ForeignKey("masterdata.Material", on_delete=models.PROTECT, related_name="family_allowances")
    length_mm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    width_mm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    thickness_mm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    source_identity = models.ForeignKey("masterdata.ExternalIdentity", on_delete=models.PROTECT)
    source_validated = models.BooleanField(default=False)
    specification_validated = models.BooleanField(default=False)
    evidence = models.JSONField(default=dict)

    class Meta:
        db_table = "pde_material_family_allowed_material"
        constraints = [
            models.UniqueConstraint(fields=("family", "material"), name="pde_mat_family_member_unique"),
            models.CheckConstraint(condition=(models.Q(specification_validated=False) | models.Q(length_mm__isnull=False, width_mm__isnull=False, thickness_mm__isnull=False, length_mm__gt=0, width_mm__gt=0, thickness_mm__gt=0)), name="pde_mat_family_spec_positive"),
        ]

    def clean(self):
        if self.family.company_id != self.material.company_id or self.source_identity.organization_id != self.family.company_id:
            raise ValidationError("材料族、候选物料与来源必须同公司")
        if self.source_identity.mapping_status != "MATCH" or self.source_identity.target_entity_type != "materials" or self.source_identity.target_entity_id != str(self.material_id):
            raise ValidationError("成员必须有唯一正式来源身份")
        if self.material.supply_type != "purchase" or not self.material.is_active or self.material.material_type not in {"raw", "auxiliary"}:
            raise ValidationError("允许成员必须是启用的真实采购组成物料")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialConfigurationSourceBinding(models.Model):
    """Row inheritance, not a second engineering instance or calculated result."""
    source_record = models.ForeignKey("pde.EngineeringSourceRecord", on_delete=models.PROTECT, related_name="material_configuration_bindings")
    source_sheet = models.CharField(max_length=120)
    source_row = models.PositiveIntegerField()
    configuration = models.ForeignKey(MaterialConfiguration, on_delete=models.PROTECT, related_name="source_bindings")
    thickness_value = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    thickness_semantic = models.CharField(max_length=40, default="UNKNOWN", choices=(("UNKNOWN", "未知"), ("RAW_BOARD_THICKNESS", "原板厚"), ("FINISHED_COMPONENT_THICKNESS", "完成部件厚"), ("COMPOSITE_THICKNESS", "组合厚度")))
    source_lineage = models.JSONField(default=dict)

    class Meta:
        db_table = "pde_material_configuration_source_binding"
        constraints = [
            models.UniqueConstraint(fields=("source_record", "source_sheet", "source_row"), name="pde_mat_cfg_source_row_unique"),
            models.CheckConstraint(condition=models.Q(thickness_semantic__in=("UNKNOWN", "RAW_BOARD_THICKNESS", "FINISHED_COMPONENT_THICKNESS", "COMPOSITE_THICKNESS")), name="pde_mat_cfg_thickness_semantic_valid"),
        ]

    def clean(self):
        if self.source_record.company_id != self.configuration.company_id:
            raise ValidationError("工程来源与配置必须属于同一公司")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
