"""Isolated standard-library tests: no Django setup, database or authentication."""
import ast
import copy
import hashlib
import json
import unittest
from pathlib import Path

from pde.formal_calculation_readback import summarize_formal_calculations


class FormalCalculationReadbackTests(unittest.TestCase):
    def setUp(self):
        self.lines = [dict(salesOrderItemId=n + 3, orderEngineeringInstanceId=n + 2, sourceRecordId=11) for n in range(4)]

    def record(self, n=0, **changes):
        return dict(dict(id=n + 20, companyId=1, scope="order_engineering", salesOrderItemId=n + 3,
                         orderEngineeringInstanceId=n + 2, sourceRecordId=11, status="completed",
                         statusLabel="已完成", calculationNo=f"EC-{n}"), **changes)

    def read(self, records):
        return summarize_formal_calculations(company_id=1, lines=self.lines, records=records)

    def test_zero_partial_complete_and_each_line_mapping(self):
        self.assertEqual(self.read([])[1]["code"], "NOT_SAVED")
        for count in range(1, 5):
            states, summary = self.read([self.record(n) for n in range(count)])
            self.assertEqual(summary["savedLineCount"], count)
            self.assertEqual(summary["completedRecordCount"], count)
            self.assertEqual(summary["code"], "SAVED" if count == 4 else "PARTIALLY_SAVED")
            for n in range(4):
                self.assertEqual(states[n + 3]["code"], "SAVED" if n < count else "NOT_SAVED")

    def test_exact_company_scope_order_line_instance_and_source(self):
        for changes in (dict(companyId=2), dict(scope="preview"), dict(salesOrderItemId=99),
                        dict(orderEngineeringInstanceId=99), dict(sourceRecordId=99)):
            with self.subTest(changes=changes):
                self.assertEqual(self.read([self.record(**changes)])[1]["recordCount"], 0)
        self.lines[0]["orderEngineeringInstanceId"] = None
        self.assertEqual(self.read([self.record()])[1]["recordCount"], 0)

    def test_failed_running_and_superseded_are_records_but_not_completed(self):
        for status in ("failed", "running", "superseded"):
            states, summary = self.read([self.record(status=status)])
            self.assertEqual(states[3]["code"], "RECORDS_PRESENT")
            self.assertEqual(summary["savedLineCount"], 0)
            self.assertEqual(summary["recordCount"], 1)

    def test_history_count_is_not_saved_line_count_and_no_mutation(self):
        records = [self.record(), self.record(id=21, status="superseded")]
        before = copy.deepcopy((self.lines, records))
        states, summary = self.read(records)
        self.assertEqual(summary["recordCount"], 2)
        self.assertEqual(summary["completedRecordCount"], 1)
        self.assertEqual(summary["savedLineCount"], 1)
        self.assertEqual(states[3]["records"], records)
        self.assertEqual(before, (self.lines, records))

    def test_failed_read_is_never_an_empty_success(self):
        with self.assertRaises(ValueError):
            self.read(None)

    def test_formal_write_and_validation_current_protection_baseline(self):
        tree = ast.parse(Path(__file__).with_name('formal_engineering_continuation_service.py').read_text(encoding='utf-8-sig'))
        service = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'FormalEngineeringContinuationService')
        expected = {
            'create_instance': '07f9d304cfbf1f11ccc58ccff6e46402cee6704b6c83cfee758ee69b14e65bc5',
            'confirm_instance_source': '7456c0e2ffb1746aa0fc885b1eefd7c87f169292443406613caa5a3f5e4b80e9',
            'validate': 'ee92d6d6580ae43cf827918ae184f609cd0e5aa44bd9753ffaca548e023d8b75',
            'execute': '2afafc3779388e1d80adce93a3c96398e1eda1bd6aa3ee89ec0dee5b6c0b2f69',
            '_execute_atomic': '26ac07d593d10e5ec2522d9795ae5372e2e3e9b117302dc9a22e0d3a5e2c30a1',
        }
        actual = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                  for node in service.body if isinstance(node, ast.FunctionDef) and node.name in expected}
        # Preserve the original expectation as historical evidence. Its three
        # differences were not retroactively authorized. The user explicitly
        # allowed a prospective baseline after the current boundary review,
        # maintain-permission fix, and independent behavior/readonly checks.
        baseline = json.loads(Path(__file__).with_name(
            'formal_continuation_protection_baseline.v4.json').read_text(encoding='utf-8'))
        previous_path = Path(__file__).with_name(baseline['previousBaseline']['path'])
        previous = json.loads(previous_path.read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(previous_path.read_bytes()).hexdigest(), baseline['previousBaseline']['sha256'])
        self.assertEqual(previous['currentMethods'], baseline['previousBaseline']['currentMethods'])
        self.assertEqual(baseline['legacyExpected'], expected)
        self.assertEqual(baseline['historicalAuthorization'], 'UNKNOWN_RETAINED')
        self.assertEqual(actual, baseline['currentMethods'])
        for filename, classes in baseline['classMethods'].items():
            dependency = ast.parse(Path(__file__).with_name(filename).read_text(encoding='utf-8-sig'))
            for class_name, methods in classes.items():
                class_node = next(n for n in dependency.body if isinstance(n, ast.ClassDef) and n.name == class_name)
                found = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                         for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name in methods}
                self.assertEqual(found, methods)
        root = Path(__file__).resolve().parents[2]
        for filename, expected_hash in baseline['files'].items():
            self.assertEqual(hashlib.sha256((root / filename).read_bytes()).hexdigest(), expected_hash)
        for filename, functions in baseline['helpers'].items():
            dependency = ast.parse(Path(__file__).with_name(filename).read_text(encoding='utf-8-sig'))
            found = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                     for node in dependency.body if isinstance(node, ast.FunctionDef) and node.name in functions}
            self.assertEqual(found, functions)
        for filename, constants in baseline['constants'].items():
            dependency = ast.parse(Path(__file__).with_name(filename).read_text(encoding='utf-8-sig'))
            found = {node.targets[0].id: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                     for node in dependency.body if isinstance(node, ast.Assign) and len(node.targets) == 1
                     and isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants}
            self.assertEqual(found, constants)
        review = Path(__file__).resolve().parents[2] / baseline['reviewEvidence']['path']
        self.assertEqual(hashlib.sha256(review.read_bytes()).hexdigest(), baseline['reviewEvidence']['sha256'])
        preflight = next(node for node in service.body if isinstance(node, ast.FunctionDef) and node.name == 'condition_preflight')
        self.assertIn("facts['formalCalculationState']", ast.unparse(preflight))


if __name__ == '__main__':
    unittest.main()
