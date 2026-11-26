"""Configuration evidence tests; production SQLite is opened read-only, never migrated."""
import copy
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from engineering_material_configuration_audit import OUT, DB, sha, save, snapshot
OUT = ROOT / "docs/evidence/semi_finished_model_closure_20260909"
from pde.semi_finished_configuration_preview import build_projection, load_source, resolve_code


class ConfigurationProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_source()
        cls.formal = snapshot()["formal"]
        cls.result = build_projection(cls.source, cls.formal, 1)

    def config(self, code):
        return next(r for r in self.result["configurations"] if r["sourceCode"] == code)

    def test_source_bundle_and_all_original_shas(self):
        self.assertEqual(len(self.source["sourceFiles"]), 6)
        self.assertNotIn("08订单排产信息（样版）.xlsx", [r["file"] for r in self.source["sourceFiles"]])

    def test_all_frozen_rows_lookup_exactly(self):
        self.assertEqual(len(self.result["identityMap"]), 71)
        self.assertTrue(all(r["lookupConsistency"] == "EXACT" and r["source05Method"] == "EXACT" for r in self.result["identityMap"]))

    def test_single_configuration_for_63_not_geometry_buckets(self):
        self.assertEqual(self.config("BTKF2601001")["realRowCount"], 63)
        self.assertEqual(self.result["summary"]["threeInOneConfigurationCount"], 1)
        self.assertEqual(self.result["summary"]["activeConfigurationCount"], 2)

    def test_external_identity_not_name(self):
        match = self.config("BTKF2601001")["identity"]
        self.assertEqual(match["method"], "EXTERNAL_IDENTITY")
        self.assertEqual(match["formal"]["id"], 140)
        self.assertEqual(match["formal"]["code"], "MAT202608000058")
        formal = copy.deepcopy(self.formal)
        formal["identities"] = []
        self.assertEqual(build_projection(self.source, formal, 1)["summary"]["formal05Matched"], 0)

    def test_existing_user_exclusions_not_new_missing_masters(self):
        self.assertEqual(self.result["summary"]["formal05Matched"], 58)
        self.assertEqual(self.result["summary"]["userExcludedSourceCount"], 3)
        self.assertEqual(self.config("DD4708001")["identity"]["method"], "USER_EXCLUDED")
        self.assertNotIn("DD4708001", [g["sourceCode"] for g in self.result["gaps"]])

    def test_foreign_organization_rejected(self):
        with self.assertRaisesRegex(ValueError, "ORGANIZATION"):
            build_projection(self.source, self.formal, 999)

    def test_foreign_material_cannot_resolve(self):
        formal = copy.deepcopy(self.formal)
        for m in formal["materials"]:
            m["company_id"] = 999
        result = build_projection(self.source, formal, 1)
        self.assertEqual(result["summary"]["formal05Matched"], 0)

    def test_drifted_identity_sha_is_not_match(self):
        formal = copy.deepcopy(self.formal)
        for i in formal["identities"]:
            if i["target_entity_id"] == "140" and i["target_entity_type"] == "materials":
                i["audit_metadata"] = json.dumps({"sourceCode": "BTKF2601001", "sourceSha256": "wrong"})
        p = build_projection(self.source, formal, 1)
        self.assertEqual(next(r for r in p["configurations"] if r["sourceCode"] == "BTKF2601001")["identity"]["status"], "UNRESOLVED")

    def test_conflicting_formal_targets_fail_closed(self):
        formal = copy.deepcopy(self.formal)
        material = copy.deepcopy(next(m for m in formal["materials"] if m["id"] == 140))
        material.update(id=99999, code="BTKF2601001")
        formal["materials"].append(material)
        p = build_projection(self.source, formal, 1)
        c = next(r for r in p["configurations"] if r["sourceCode"] == "BTKF2601001")
        self.assertEqual(c["identity"]["status"], "UNRESOLVED")

    def test_inactive_material_not_match(self):
        formal = copy.deepcopy(self.formal)
        next(m for m in formal["materials"] if m["id"] == 140)["is_active"] = False
        p = build_projection(self.source, formal, 1)
        self.assertEqual(next(r for r in p["configurations"] if r["sourceCode"] == "BTKF2601001")["identity"]["status"], "UNRESOLVED")

    def test_catalog_duplicate_not_silently_first_match(self):
        source = copy.deepcopy(self.source)
        source["dependencies"]["物料目录(设计)"].append(copy.deepcopy(next(d for d in source["dependencies"]["物料目录(设计)"] if d["row"] == 62)))
        p = build_projection(source, self.formal, 1)
        self.assertEqual(p["summary"]["threeInOneMapped"], 0)

    def test_splice_and_skin_are_not_inferred_from_name(self):
        attrs = {r["key"]: r for r in self.config("BTKF2601001")["attributes"]}
        self.assertIn("实木拼", attrs["veneer"]["sourceValue"])
        self.assertIsNone(attrs["splice"]["sourceValue"])
        self.assertIsNone(attrs["skinFeel"]["sourceValue"])

    def test_formal_uom_is_preserved_despite_blank_source(self):
        attrs = {r["key"]: r for r in self.config("BTKF2601001")["attributes"]}
        self.assertIsNone(attrs["uom"]["sourceValue"])
        self.assertEqual(attrs["uom"]["formalTargets"][0]["id"], 18)
        self.assertEqual(attrs["uom"]["relationshipStatus"], "EXISTING_FORMAL_LINK")

    def test_paint_type_code_retains_name_difference(self):
        a = next(r for r in self.config("BTKF2601001")["attributes"] if r["key"] == "paintProcess")
        self.assertEqual(a["sourceValue"], "半透工艺")
        self.assertEqual(a["formalTargets"][0]["name"], "半透开放")
        self.assertEqual(a["formalTargets"][0]["model"], "pde.ManufacturingProcessType")
        self.assertEqual(a["relationshipStatus"], "NOT_FORMALIZED")

    def test_no_false_color_or_veneer_or_substrate_identity(self):
        attrs = {r["key"]: r for r in self.config("BTKF2601001")["attributes"]}
        for k in ("color", "veneer", "substrate"):
            self.assertEqual(attrs[k]["formalStatus"], "UNRESOLVED")
        self.assertEqual(attrs["veneer"]["sourceTrace"][0]["row"], 27)
        self.assertEqual(attrs["substrate"]["sourceTrace"][0]["row"], 2)

    def test_no_veneer_explicit_none_is_not_virtual_material(self):
        a = next(r for r in self.config("HYFB0101001")["attributes"] if r["key"] == "veneer")
        self.assertEqual(a["formalStatus"], "NOT_APPLICABLE")
        self.assertEqual(a["formalTargets"], [])

    def test_no_fake_paint_quantity_or_loss_policy(self):
        self.assertTrue(all(r["quantity"] is None and not r["formalRelationship"] for r in self.result["compositionTrace"]))
        self.assertTrue(all(not c["businessCalculable"] and not c["userValidated"] for c in self.result["configurations"]))

    def test_thickness_does_not_imply_stock(self):
        self.assertEqual(len(self.result["thicknessAnalysis"]), 63)
        self.assertTrue(all(r["semantic"] == "UNKNOWN" and not r["rawBoardExactMatchAllowed"] for r in self.result["thicknessAnalysis"]))
        self.assertEqual(self.result["summary"]["thicknessCounts"], {"18": 31, "28": 14, "24": 6, "22": 11, "25": 1})

    def test_frozen_scope_not_extended(self):
        self.assertEqual([r["row"] for r in self.source["outsideFrozenScope"]], [25, 26, 72])
        self.assertEqual(self.result["summary"]["realRowCount"], 71)

    def test_door_context_keeps_opening_and_wall_dimensions_separate(self):
        row = self.config("QSFB4601001")["engineeringRows"][0]
        self.assertEqual(row["role"], "单开门")
        self.assertIsNone(row["model"])
        self.assertIsNone(row["thickness"])
        self.assertEqual(row["dimensionText"], "洞高 2045 / 洞宽 938 / 墙厚 265")
        self.assertEqual(row["quantityLabel"], "门洞数量")

    def test_user_requests_are_per_configuration(self):
        self.assertEqual(len(self.result["gaps"]), 2)
        self.assertEqual(sorted(g["affectedRows"] for g in self.result["gaps"]), [8, 63])

    def test_pure_projection_does_not_mutate_input(self):
        before = json.dumps([self.source, self.formal], sort_keys=True)
        build_projection(self.source, self.formal, 1)
        self.assertEqual(before, json.dumps([self.source, self.formal], sort_keys=True))


def api_checks():
    # Dedicated process; same real facts, but SQLite's own URI mode prevents any write.
    os.environ["DJANGO_SETTINGS_MODULE"] = "pce_backend.settings"
    from django.conf import settings
    settings.DATABASES["default"]["NAME"] = DB.as_uri() + "?mode=ro"
    settings.DATABASES["default"]["OPTIONS"] = {"uri": True}
    import django
    django.setup()
    from django.db import connection
    from system.models import User
    from rest_framework.test import APIRequestFactory, force_authenticate
    from pde.views import EngineeringCalculationReadinessView
    from pde.engineering_calculation_service import EngineeringCalculationError
    connection.ensure_connection()
    connection.connection.execute("PRAGMA query_only=ON")
    user = User.objects.filter(is_superuser=True, company_id=1, is_active=True).defer("password").first()
    assert user is not None, "No existing authorized read-only test actor"
    factory = APIRequestFactory()
    view = EngineeringCalculationReadinessView.as_view()
    writes = []
    sql_count = 0
    def guard(execute, sql, params, many, context):
        nonlocal sql_count
        sql_count += 1
        if sql.lstrip().split()[0].upper() not in ("SELECT", "PRAGMA", "EXPLAIN"):
            writes.append(sql[:40])
            raise AssertionError("Forbidden database statement during read-only acceptance")
        return execute(sql, params, many, context)
    def request(subview="semi-finished-structure", actor=user, method="get"):
        req = getattr(factory, method)("/api/pde/a1-engineering/calculations/readiness/", {"subview": subview})
        if actor is not None:
            force_authenticate(req, actor)
        return view(req)
    cases = []
    with connection.execute_wrapper(guard):
        response = request()
        assert response.status_code == 200, str(response.data)
        assert response.data["summary"] if "summary" in response.data else response.data["realRowCount"] == 71
        for k in ("apiFacts", "pageFacts", "diagnosticFacts"):
            assert response.data[k] == response.data["strictFacts"]
        from pde.semi_finished_configuration_validation import apply_validation
        assert response.data["semiFinishedConfiguration"] == apply_validation(ConfigurationProjectionTests.result)
        save(OUT / "API_READONLY_EVIDENCE.json", response.data)
        cases.append("authorized GET / same source-formal projection / four surface facts PASS")
        anonymous = request(actor=None)
        assert anonymous.status_code in (401, 403)
        cases.append("anonymous denied PASS")
        with patch("pde.engineering_calculation_service.EngineeringCalculationService._authorize", side_effect=EngineeringCalculationError("PERMISSION_DENIED", "denied")):
            denied = request()
            assert denied.status_code == 403 and denied.data["resultCount"] is None
            cases.append("unauthorized fail closed / no empty-success PASS")
        with patch("pde.semi_finished_configuration_preview.load_source", side_effect=ValueError("changed source")):
            failed = request()
            assert failed.status_code == 503 and failed.data["factLoadStatus"] == "read_failed"
            assert failed.data["resultCount"] is None and not failed.data["passed"]
            assert all(k in failed.data for k in ("apiUrl", "httpStatus", "errorCode", "errorMessage", "loadedAt", "tenantId", "batchId"))
            cases.append("source/hash failure complete error contract PASS")
        bad = request(subview="wrong")
        assert bad.status_code == 400
        cases.append("unknown subview denied PASS")
        posted = request(method="post")
        assert posted.status_code == 405
        cases.append("POST unsupported PASS")
        prior = request(subview="")
        assert prior.status_code == 200 and len(prior.data["formalRules"]) == 4
        assert prior.data["materialRuleDefinition"]["sourceRowCount"] == 71
        cases.append("original readiness / 4 rules / 31 cards / 71 rows preserved PASS")
    connection.close()
    return {"cases": cases, "caseCount": len(cases), "sqlCount": sql_count, "writeStatements": writes, "databaseMode": "mode=ro + PRAGMA query_only + SQL read-only guard"}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    before = sha(DB)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ConfigurationProjectionTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    api = api_checks()
    after = sha(DB)
    assert before == after
    report = {"unitTests": result.testsRun, "unitResult": "PASS", "api": api, "databaseBefore": before, "databaseAfter": after, "productionBusinessWrite": 0}
    save(OUT / "TEST_RESULTS.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
