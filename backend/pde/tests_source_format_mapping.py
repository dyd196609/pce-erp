"""SIMULATED_FOR_TEST: governed source formats, no production fixtures."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from masterdata.models import UnitOfMeasure
from system.models import Company, OrganizationOperatingAuditRecord, User
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object

from .engineering_rule_foundation import EngineeringRuleError, specification_hash, validate_specification
from .models import EngineeringRuleDefinition, EngineeringSourceRecord
from .production_foundation_service import EngineeringLifecycleService, ProductionFoundationError, ProductionFoundationService
from .source_format_mapping_service import (
    CONTRACT, SourceFormatMappingError, mapped_order_inputs, normalize_content,
    normalize_source_payload, validate_mapping,
)


def mapping(**overrides):
    config = {"contractVersion": CONTRACT, "format": "CSV", "delimiter": ",",
        "decimalSeparator": ".", "thousandsSeparator": "",
        "fields": [{"rawField": "原始数量", "canonicalName": "source_quantity", "sourceType": "ENGINEERING_INPUT",
            "valueType": "decimal", "unit": None, "unitDimension": None,
            "zeroTokens": ["ZERO"], "blankTokens": ["NULL"], "blankPolicy": "NULL"}]}
    config.update(overrides)
    return config


def specification(config):
    return {"rulePackage": {"code": "SIM.SOURCE.FORMAT", "version": "V1"}, "expression": "raw_quantity",
        "inputs": [{"canonicalName": "raw_quantity", "valueType": "decimal", "sourceType": "ENGINEERING_INPUT",
            "unitDimension": "dimensionless"}],
        "outputs": [{"canonicalName": "normalized_quantity", "valueType": "decimal", "unitDimension": "dimensionless",
            "resultDomain": "DERIVED_FACT"}],
        "dependencies": [], "applicability": {}, "decimalPrecision": 28, "outputScale": 6,
        "roundingMode": "ROUND_HALF_UP", "sourceEvidence": {"reference": "SIMULATED_FOR_TEST"},
        "sourceFormatMapping": config}


class SourceFormatNormalizerTests(SimpleTestCase):
    def test_explicit_zero_and_blank_are_different(self):
        result = normalize_content(mapping(), "原始数量\n0\nZERO\nNULL\n2.500\n")
        self.assertEqual([row["canonicalInputs"]["source_quantity"]["value"] for row in result["rows"]],
            ["0", "0", None, "2.500"])
        self.assertEqual(result["rows"][2]["raw"], {"原始数量": "NULL"})

    def test_configured_columns_and_localized_number_format(self):
        config = mapping(delimiter=";", decimalSeparator=",", thousandsSeparator=".")
        config["fields"][0]["rawField"] = "customer volume"
        result = normalize_content(config, "customer volume;description\n1.234,500;untouched\n")
        self.assertEqual(result["rows"][0]["canonicalInputs"]["source_quantity"]["value"], "1234.500")
        self.assertEqual(result["rows"][0]["raw"]["description"], "untouched")

    def test_empty_json_value_remains_null(self):
        result = normalize_content(mapping(format="JSON_ROWS"), [{"原始数量": None}, {"原始数量": ""}, {"原始数量": 0}])
        self.assertEqual([row["canonicalInputs"]["source_quantity"]["value"] for row in result["rows"]], [None, None, "0"])

    def test_json_text_preserves_decimal_precision(self):
        result = normalize_content(mapping(format="JSON_ROWS"), '[{"原始数量":0.123456789123456789}]')
        self.assertEqual(result["rows"][0]["canonicalInputs"]["source_quantity"]["value"], "0.123456789123456789")

    def test_json_float_objects_require_lossless_source(self):
        with self.assertRaisesMessage(SourceFormatMappingError, "浮点精度"):
            normalize_content(mapping(format="JSON_ROWS"), [{"原始数量": 0.1}])

    def test_missing_field_does_not_become_blank(self):
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_content(mapping(format="JSON_ROWS"), [{"different": "3"}])
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_FIELD_MISSING")

    def test_invalid_grouping_is_not_silently_stripped(self):
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_content(mapping(delimiter=";", thousandsSeparator=","), "原始数量\n12,34\n")
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_NUMBER_INVALID")

    def test_configured_blank_error(self):
        config = mapping()
        config["fields"][0]["blankPolicy"] = "ERROR"
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_content(config, "原始数量\nNULL\n")
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_BLANK_NOT_ALLOWED")

    def test_integer_and_text_fields_have_separate_contracts(self):
        config = mapping(format="JSON_ROWS")
        config["fields"][0]["valueType"] = "integer"
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_content(config, [{"原始数量": "1.5"}])
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_INTEGER_REQUIRED")
        config["fields"][0].update(valueType="text", zeroTokens=[])
        self.assertEqual(normalize_content(config, [{"原始数量": "001-A"}])["rows"][0]["canonicalInputs"]["source_quantity"]["value"], "001-A")

    def test_duplicate_mapping_and_zero_to_null_are_rejected(self):
        config = mapping()
        config["fields"].append(deepcopy(config["fields"][0]))
        with self.assertRaises(SourceFormatMappingError):
            validate_mapping(config)
        for token in ("0", "0.00", "-0"):
            config = mapping()
            config["fields"][0]["blankTokens"] = [token]
            with self.assertRaises(SourceFormatMappingError):
                validate_mapping(config)

    def test_optional_contract_does_not_change_legacy_formula(self):
        spec = specification(mapping())
        self.assertIs(validate_specification(spec), spec)
        spec.pop("sourceFormatMapping")
        self.assertIs(validate_specification(spec), spec)
        spec["sourceFormatMapping"] = {"contractVersion": CONTRACT, "format": "ARBITRARY"}
        with self.assertRaises(EngineeringRuleError):
            validate_specification(spec)

    def test_malformed_csv_and_duplicate_headers_fail(self):
        for content in ("原始数量,原始数量\n1,2\n", "原始数量,x\n1\n", '原始数量\n"broken\n'):
            with self.subTest(content=content), self.assertRaises(SourceFormatMappingError):
                normalize_content(mapping(), content)


class SourceFormatPersistenceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="SIM-SOURCE-FORMAT", name="SIMULATED_FOR_TEST")
        self.user = User.objects.create_user(username="sim_source_format", company_id=self.company.pk)
        self.unit = UnitOfMeasure.objects.create(company_id=self.company.pk, code="SIM-m", name="测试长度", dimension="length")
        self.config = mapping()
        self.config["fields"][0].update(unit=self.unit.code, unitDimension="length")
        self.rule = self.make_rule("V1", self.config)

    def advance(self, obj, target):
        current = obj.status
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code="SIMULATED_FOR_TEST.source_format.transition", actor=self.user, organization=self.company,
            target_type=type(obj).__name__, target_id=obj.pk, target_label=str(obj.pk), reason="SIMULATED_FOR_TEST",
            before_snapshot={"status": current}, after_snapshot={"status": target})
        transition_business_object(business_object=obj, object_type=type(obj).__name__,
            source_state=current, target_state=target, action_code=audit.action_code, operator=self.user,
            reason=audit.reason, audit_reference=f"system.OrganizationOperatingAuditRecord:{audit.pk}",
            allowed_transitions={(current, target)}, version_field=None)

    def make_rule(self, version, config, *, effective_from=None, effective_to=None):
        row = create_business_object_with_initial_state(model=EngineeringRuleDefinition, initial_state="draft",
            company=self.company, rule_code="SIM-SOURCE-FORMAT", rule_name="SIMULATED_FOR_TEST source mapping",
            version=version, rule_kind="formula", specification=specification(config),
            effective_from=effective_from, effective_to=effective_to)
        self.advance(row, "reviewed")
        self.advance(row, "released")
        return row

    def payload(self, rule=None, content="原始数量\n2.50\n"):
        rule = rule or self.rule
        return {"sourceFormatReference": {"ruleId": rule.pk, "ruleVersion": rule.version,
            "specificationHash": specification_hash(rule.specification)}, "rawContent": content,
            "sourceKind": "SIMULATED_FOR_TEST"}

    @contextmanager
    def authorized(self):
        with patch("pde.production_foundation_service.AuthorizationService.decide", return_value={"allowed": True}), patch(
                "pde.production_foundation_service._actor_chain", return_value={"account": self.user.username}):
            yield

    def save_source(self, payload=None):
        with self.authorized():
            result = ProductionFoundationService.save("engineering-source-records", user=self.user, payload={
                "source_no": "SIM-SOURCE-FORMAT-INPUT", "source_name": "SIMULATED_FOR_TEST",
                "source_type": "controlled_import", "source_version": "V1", "source_payload": payload or self.payload(),
                "content_hash": "client-untrusted", "reason": "SIMULATED_FOR_TEST"})
        return EngineeringSourceRecord.objects.get(pk=result["row"]["id"])

    def test_server_replaces_untrusted_projection_and_records_audit(self):
        data = self.payload()
        data.update(canonicalInputs={"source_quantity": {"value": "999"}}, normalization={"fake": True})
        source = self.save_source(data)
        self.assertEqual(source.source_payload["canonicalInputs"]["source_quantity"]["value"], "2.50")
        self.assertEqual(source.content_hash, source.source_payload["normalization"]["rawContentHash"])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(target_type="EngineeringSourceRecord", target_id=source.pk).count(), 1)

    def test_wrong_company_hash_version_and_expiry_fail(self):
        data = self.payload()
        with self.assertRaises(SourceFormatMappingError):
            normalize_source_payload(data, company_id=self.company.pk + 100)
        for key, value in (("ruleVersion", "V999"), ("specificationHash", "f" * 64)):
            changed = deepcopy(data)
            changed["sourceFormatReference"][key] = value
            with self.assertRaises(SourceFormatMappingError):
                normalize_source_payload(changed, company_id=self.company.pk)
        yesterday = timezone.now().date() - timedelta(days=1)
        expired = self.make_rule("EXPIRED", self.config, effective_to=yesterday)
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_source_payload(self.payload(expired), company_id=self.company.pk)
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_RULE_NOT_EFFECTIVE")

    def test_scope_and_multiline_selection_require_explicit_facts(self):
        config = deepcopy(self.config)
        config["scopeEquals"] = {"factory": "A"}
        scoped = self.make_rule("SCOPED", config)
        data = self.payload(scoped, content="原始数量\n1\n2\n")
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_source_payload(data, company_id=self.company.pk)
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_SCOPE_MISMATCH")
        data["sourceContext"] = {"factory": "A"}
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_source_payload(data, company_id=self.company.pk)
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_ROW_SELECTION_REQUIRED")
        data["sourceFormatRow"] = 1
        self.assertEqual(normalize_source_payload(data, company_id=self.company.pk)["canonicalInputs"]["source_quantity"]["value"], "2")

    def test_confirmed_source_mapping_cannot_change_or_be_removed(self):
        source = self.save_source()
        with self.authorized():
            EngineeringLifecycleService.transition("engineering-source-records", object_id=source.pk,
                target_status="confirmed", user=self.user, reason="SIMULATED_FOR_TEST")
            for payload in ({"source_payload": {}}, {"source_name": "changed"}):
                with self.subTest(payload=payload), self.assertRaises(ProductionFoundationError) as raised:
                    ProductionFoundationService.save("engineering-source-records", user=self.user, object_id=source.pk, payload=payload)
                self.assertEqual(raised.exception.code, "CONFIRMED_SOURCE_FORMAT_IMMUTABLE")
        source.refresh_from_db()
        self.assertEqual(source.source_payload["rawContent"], "原始数量\n2.50\n")

    def test_formal_consumer_checks_raw_snapshot_and_existing_attributes(self):
        source = self.save_source()
        mapped = mapped_order_inputs(source, {})
        existing = {"source_quantity": {"value": Decimal("2.500"), "unit": self.unit.code, "sourceType": "ENGINEERING_INPUT"}}
        self.assertEqual(mapped_order_inputs(source, existing), mapped)
        existing["source_quantity"]["value"] = "8"
        with self.assertRaises(SourceFormatMappingError) as raised:
            mapped_order_inputs(source, existing)
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_ENGINEERING_INPUT_CONFLICT")
        source.source_payload["canonicalInputs"]["source_quantity"]["value"] = "4"
        with self.assertRaises(SourceFormatMappingError) as raised:
            mapped_order_inputs(source, {})
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_SNAPSHOT_MISMATCH")

    def test_new_rule_version_leaves_formal_source_snapshot_unchanged(self):
        source = self.save_source()
        snapshot = deepcopy(source.source_payload)
        updated = deepcopy(self.config)
        updated["fields"][0]["rawField"] = "new column"
        self.make_rule("V2", updated)
        self.assertEqual(mapped_order_inputs(source, {})["source_quantity"]["value"], "2.50")
        source.refresh_from_db()
        self.assertEqual(source.source_payload, snapshot)
        changed = deepcopy(self.rule.specification)
        changed["sourceFormatMapping"] = updated
        self.rule.specification = changed
        with self.assertRaises(ValidationError):
            self.rule.save()

    def test_unmapped_legacy_inputs_keep_original_path(self):
        legacy = {"source_quantity": {"value": "7", "unit": None}}
        source = SimpleNamespace(source_payload={"canonicalInputs": {"unrelated": "999"}})
        self.assertIs(mapped_order_inputs(source, legacy), legacy)
        self.assertEqual(normalize_source_payload({"canonicalInputs": legacy}, company_id=self.company.pk), {"canonicalInputs": legacy})

    def test_inactive_or_wrong_dimension_units_fail(self):
        wrong = deepcopy(self.config)
        wrong["fields"][0]["unitDimension"] = "area"
        rule = self.make_rule("BAD-UNIT", wrong)
        with self.assertRaises(SourceFormatMappingError) as raised:
            normalize_source_payload(self.payload(rule), company_id=self.company.pk)
        self.assertEqual(raised.exception.code, "SOURCE_FORMAT_UNIT_REFERENCE_INVALID")

    @override_settings(USE_TZ=True)
    def test_aware_time_configuration_uses_the_same_mapping_contract(self):
        result = normalize_source_payload(self.payload(), company_id=self.company.pk)
        self.assertEqual(result["canonicalInputs"]["source_quantity"]["value"], "2.50")
