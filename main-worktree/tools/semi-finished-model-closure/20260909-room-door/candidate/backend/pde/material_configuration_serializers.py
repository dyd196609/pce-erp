"""Canonical read/round-trip contract; no production write endpoint is registered."""
from rest_framework import serializers
from .models import MaterialConfiguration, MaterialConfigurationAttribute, TemplateMaterialRequirementSlot


class MaterialConfigurationAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialConfigurationAttribute
        fields = "__all__"


class MaterialConfigurationSerializer(serializers.ModelSerializer):
    attributes = MaterialConfigurationAttributeSerializer(many=True, read_only=True)

    class Meta:
        model = MaterialConfiguration
        fields = ("id", "company", "material", "source_identity", "configuration_code", "source_validated", "validation_reference", "attributes")


class MaterialCompositionSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateMaterialRequirementSlot
        fields = "__all__"
