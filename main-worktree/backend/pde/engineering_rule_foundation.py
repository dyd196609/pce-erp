"""A1.8 DO-2 engineering-rule validation and isolated execution foundation.

This module deliberately stops at deterministic rule evaluation.  It does not
create calculation records, derived facts, material requirements, operation
requirements, BOMs, plans, or inventory transactions.
"""

from __future__ import annotations

import ast
import hashlib
import heapq
import json
import re
from dataclasses import dataclass
from decimal import (
    Decimal,
    DivisionByZero,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    localcontext,
)


SOURCE_TYPES = {
    "CUSTOMER",
    "SITE_MEASUREMENT",
    "SALES",
    "DESIGN",
    "ENGINEERING_INPUT",
    "ENGINEERING_DERIVED",
    "MASTER_DATA",
    "RULE_PARAMETER",
    "AGGREGATED",
}
OUTPUT_DOMAINS = {
    "DERIVED_FACT",
    "MATERIAL_REQUIREMENT",
    "OPERATION_REQUIREMENT",
}
VALUE_TYPES = {"decimal", "integer"}
ROUNDING_MODES = {
    "ROUND_CEILING": ROUND_CEILING,
    "ROUND_DOWN": ROUND_DOWN,
    "ROUND_FLOOR": ROUND_FLOOR,
    "ROUND_HALF_DOWN": ROUND_HALF_DOWN,
    "ROUND_HALF_EVEN": ROUND_HALF_EVEN,
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_UP": ROUND_UP,
}
NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
SUPPORTED_BINARY_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
SUPPORTED_UNARY_OPERATORS = (ast.UAdd, ast.USub)


class EngineeringRuleError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _fail(code: str, message: str, **details):
    raise EngineeringRuleError(code, message, details)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def specification_hash(specification: dict) -> str:
    return hashlib.sha256(canonical_json(specification).encode("utf-8")).hexdigest()


def expression_hash(specification: dict) -> str:
    expression = str((specification or {}).get("expression") or "")
    return hashlib.sha256(expression.encode("utf-8")).hexdigest()


def _required_mapping(value, field: str) -> dict:
    if not isinstance(value, dict):
        _fail("INVALID_SPECIFICATION", f"{field}必须是对象。", field=field)
    return value


def _required_list(value, field: str) -> list:
    if not isinstance(value, list) or not value:
        _fail("INVALID_SPECIFICATION", f"{field}必须是非空数组。", field=field)
    return value


def _dimension(value) -> dict[str, int]:
    """Normalize a small industry-neutral dimensional contract.

    String aliases are governance vocabulary rather than industry branches.
    A mapping can represent any future composite dimension without a schema
    change, for example ``{"mass": 1, "time": -1}``.
    """

    if value in (None, "", "dimensionless"):
        return {}
    if isinstance(value, dict):
        result = {}
        for key, exponent in value.items():
            if not NAME_PATTERN.match(str(key)) or not isinstance(exponent, int):
                _fail("INVALID_SPECIFICATION", "unitDimension映射无效。", unitDimension=value)
            if exponent:
                result[str(key)] = exponent
        return result
    if not isinstance(value, str):
        _fail("INVALID_SPECIFICATION", "unitDimension必须是字符串或维度映射。")
    aliases = {
        "length": {"length": 1},
        "area": {"length": 2},
        "volume": {"length": 3},
        "mass": {"mass": 1},
        "time": {"time": 1},
        "count": {"count": 1},
        "mass_per_length": {"mass": 1, "length": -1},
        "quantity_per_time": {"quantity": 1, "time": -1},
    }
    if value in aliases:
        return aliases[value]
    if NAME_PATTERN.match(value):
        return {value: 1}
    _fail("INVALID_SPECIFICATION", "unitDimension格式无效。", unitDimension=value)


def _validate_contract(contract: dict, *, field: str, output: bool = False):
    if not isinstance(contract, dict):
        _fail("INVALID_SPECIFICATION", f"{field}成员必须是对象。", field=field)
    name = str(contract.get("canonicalName") or "").strip()
    if not NAME_PATTERN.match(name):
        _fail("INVALID_SPECIFICATION", "canonicalName必须是稳定ASCII标识符。", field=field)
    value_type = str(contract.get("valueType") or "").strip()
    if value_type not in VALUE_TYPES:
        _fail("INVALID_SPECIFICATION", "DO-2安全算术只支持decimal/integer。", canonicalName=name)
    _dimension(contract.get("unitDimension"))
    if output:
        domain = str(contract.get("resultDomain") or "").strip()
        if domain not in OUTPUT_DOMAINS:
            _fail("INVALID_SPECIFICATION", "输出resultDomain不在冻结的三类范围内。", canonicalName=name)
    else:
        source_type = str(contract.get("sourceType") or "").strip()
        if source_type not in SOURCE_TYPES:
            _fail("INVALID_SPECIFICATION", "输入sourceType不在冻结的九类范围内。", canonicalName=name)
        if not isinstance(contract.get("required", True), bool):
            _fail("INVALID_SPECIFICATION", "required必须为布尔值。", canonicalName=name)
        if not isinstance(contract.get("unitRequired", False), bool):
            _fail("INVALID_SPECIFICATION", "unitRequired必须为布尔值。", canonicalName=name)


def _parse_expression(expression: str, declared_names: set[str]) -> ast.Expression:
    if not isinstance(expression, str) or not expression.strip():
        _fail("INVALID_EXPRESSION", "规则表达式不能为空。")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        _fail("INVALID_EXPRESSION", "规则表达式语法无效。", offset=exc.offset)
    for node in ast.walk(tree):
        if isinstance(node, ast.operator):
            if not isinstance(node, SUPPORTED_BINARY_OPERATORS):
                _fail("UNSUPPORTED_OPERATOR", "表达式包含不支持的二元运算符。", operator=type(node).__name__)
            continue
        if isinstance(node, ast.unaryop):
            if not isinstance(node, SUPPORTED_UNARY_OPERATORS):
                _fail("UNSUPPORTED_OPERATOR", "表达式包含不支持的一元运算符。", operator=type(node).__name__)
            continue
        if isinstance(node, ast.Name):
            if node.id not in declared_names:
                _fail("UNKNOWN_VARIABLE", "表达式引用了未声明变量。", variable=node.id)
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                _fail("INVALID_DECIMAL", "表达式常量必须是十进制数值。")
            continue
        if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Load)):
            _fail("INVALID_EXPRESSION", "表达式包含禁止的语法节点。", node=type(node).__name__)
    return tree


def validate_specification(specification: dict) -> dict:
    spec = _required_mapping(specification, "specification")
    if spec.get("ruleRole") == "OPERATION_ALLOCATION_COMPOSITION":
        from .operation_contribution_composition import (
            OperationContributionCompositionError, validate_composition_specification,
        )
        try:
            return validate_composition_specification(spec)
        except OperationContributionCompositionError as exc:
            _fail(exc.code, exc.message, **exc.details)
    package = _required_mapping(spec.get("rulePackage"), "rulePackage")
    package_code = str(package.get("code") or "").strip()
    package_version = str(package.get("version") or "").strip()
    if not CODE_PATTERN.match(package_code) or not VERSION_PATTERN.match(package_version):
        _fail("INVALID_SPECIFICATION", "rulePackage.code/version必须是稳定标识。")

    inputs = _required_list(spec.get("inputs"), "inputs")
    outputs = _required_list(spec.get("outputs"), "outputs")
    if len(outputs) != 1:
        _fail("INVALID_SPECIFICATION", "DO-2每条安全表达式规则必须声明一个确定输出。")
    for row in inputs:
        _validate_contract(row, field="inputs", output=False)
    for row in outputs:
        _validate_contract(row, field="outputs", output=True)
    input_names = [row["canonicalName"] for row in inputs]
    output_names = [row["canonicalName"] for row in outputs]
    if len(input_names) != len(set(input_names)) or len(output_names) != len(set(output_names)):
        _fail("INVALID_SPECIFICATION", "规则输入或输出canonicalName重复。")
    if set(input_names) & set(output_names):
        _fail("INVALID_SPECIFICATION", "单条规则输入与输出不得同名。")

    dependencies = spec.get("dependencies", [])
    if not isinstance(dependencies, list) or any(
        not isinstance(code, str) or not CODE_PATTERN.match(code) for code in dependencies
    ):
        _fail("INVALID_SPECIFICATION", "dependencies必须是稳定规则编码数组。")
    if len(dependencies) != len(set(dependencies)):
        _fail("INVALID_SPECIFICATION", "dependencies包含重复规则编码。")

    precision = spec.get("decimalPrecision")
    scale = spec.get("outputScale")
    if not isinstance(precision, int) or not 1 <= precision <= 50:
        _fail("INVALID_SPECIFICATION", "decimalPrecision必须在1至50之间。")
    if not isinstance(scale, int) or not 0 <= scale <= precision:
        _fail("INVALID_SPECIFICATION", "outputScale必须在0至decimalPrecision之间。")
    rounding = str(spec.get("roundingMode") or "")
    if rounding not in ROUNDING_MODES:
        _fail("INVALID_SPECIFICATION", "roundingMode不受支持。", roundingMode=rounding)
    priority = spec.get("priority", 100)
    if not isinstance(priority, int) or priority < 0:
        _fail("INVALID_SPECIFICATION", "priority必须是非负整数。")
    evidence = spec.get("sourceEvidence")
    if not isinstance(evidence, dict) or not str(evidence.get("reference") or "").strip():
        _fail("INVALID_SPECIFICATION", "sourceEvidence.reference是正式来源追溯必填项。")
    if not isinstance(spec.get("applicability"), dict):
        _fail("INVALID_SPECIFICATION", "applicability必须是行业中立的适用范围对象。")

    _parse_expression(str(spec.get("expression") or ""), set(input_names))
    if "sourceFormatMapping" in spec:
        from .source_format_mapping_service import SourceFormatMappingError, validate_mapping
        try:
            validate_mapping(spec["sourceFormatMapping"])
        except SourceFormatMappingError as exc:
            _fail(exc.code, exc.message, **exc.details)
    return spec


@dataclass(frozen=True)
class _Value:
    decimal: Decimal
    dimension: dict[str, int]
    literal: bool = False


def _combine_dimensions(left: dict[str, int], right: dict[str, int], sign: int) -> dict[str, int]:
    result = dict(left)
    for key, exponent in right.items():
        result[key] = result.get(key, 0) + sign * exponent
        if result[key] == 0:
            del result[key]
    return result


def _decimal(value, variable: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        _fail("INVALID_DECIMAL", "运行输入必须使用无二进制浮点损失的十进制文本。", variable=variable)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        _fail("INVALID_DECIMAL", "运行输入无法转换为Decimal。", variable=variable)


def _eval_node(node, expression: str, values: dict[str, _Value]) -> _Value:
    if isinstance(node, ast.Constant):
        segment = ast.get_source_segment(expression, node) or str(node.value)
        try:
            return _Value(Decimal(segment), {}, True)
        except InvalidOperation:
            _fail("INVALID_DECIMAL", "表达式常量不是有效Decimal。", value=segment)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, expression, values)
        return _Value(value.decimal if isinstance(node.op, ast.UAdd) else -value.decimal, value.dimension, value.literal)
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, expression, values)
        right = _eval_node(node.right, expression, values)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if left.dimension != right.dimension:
                if left.literal and not left.dimension:
                    dimension = right.dimension
                elif right.literal and not right.dimension:
                    dimension = left.dimension
                else:
                    _fail("UNIT_MISMATCH", "加减运算两侧维度不一致。")
            else:
                dimension = left.dimension
            result = left.decimal + right.decimal if isinstance(node.op, ast.Add) else left.decimal - right.decimal
            return _Value(result, dimension, left.literal and right.literal)
        if isinstance(node.op, ast.Mult):
            return _Value(
                left.decimal * right.decimal,
                _combine_dimensions(left.dimension, right.dimension, 1),
                left.literal and right.literal,
            )
        try:
            return _Value(
                left.decimal / right.decimal,
                _combine_dimensions(left.dimension, right.dimension, -1),
                left.literal and right.literal,
            )
        except (DivisionByZero, ZeroDivisionError, InvalidOperation):
            _fail("DIVISION_BY_ZERO", "规则执行发生除零。")
    _fail("INVALID_EXPRESSION", "表达式节点未通过安全执行器。")


def evaluate_specification(specification: dict, input_values: dict) -> dict:
    spec = validate_specification(specification)
    if spec.get("ruleRole") == "OPERATION_ALLOCATION_COMPOSITION":
        _fail("NON_EXECUTABLE_RULE", "投产量组合声明只用于正式贡献兼容性校验，不能作为工程数量公式执行。")
    declared = {row["canonicalName"]: row for row in spec["inputs"]}
    unknown = sorted(set(input_values) - set(declared))
    if unknown:
        _fail("UNKNOWN_VARIABLE", "运行输入包含未声明变量。", variables=unknown)
    expression_tree = _parse_expression(spec["expression"], set(declared))
    referenced_names = {node.id for node in ast.walk(expression_tree) if isinstance(node, ast.Name)}
    missing = sorted(name for name in referenced_names if name not in input_values)
    if missing:
        _fail("UNKNOWN_VARIABLE", "缺少规则必填输入。", variables=missing)

    values = {}
    for name, contract in declared.items():
        if name not in input_values:
            continue
        supplied = input_values[name]
        metadata = supplied if isinstance(supplied, dict) else {}
        raw_value = metadata.get("value") if isinstance(supplied, dict) else supplied
        expected_dimension = _dimension(contract.get("unitDimension"))
        if isinstance(supplied, dict) and "unitDimension" in supplied:
            actual_dimension = _dimension(supplied.get("unitDimension"))
            if actual_dimension != expected_dimension:
                _fail("UNIT_MISMATCH", "运行输入单位维度与契约不一致。", variable=name)
        if contract.get("unitRequired") and (
            not isinstance(supplied, dict) or not supplied.get("unit")
        ):
            _fail("UNIT_MISMATCH", "规则输入缺少契约要求的计量单位。", variable=name)
        values[name] = _Value(_decimal(raw_value, name), expected_dimension)

    expression = spec["expression"]
    with localcontext() as context:
        context.prec = spec["decimalPrecision"]
        result = _eval_node(expression_tree.body, expression, values)
        expected_output_dimension = _dimension(spec["outputs"][0].get("unitDimension"))
        if result.dimension != expected_output_dimension:
            _fail(
                "UNIT_MISMATCH",
                "表达式结果维度与输出契约不一致。",
                actual=result.dimension,
                expected=expected_output_dimension,
            )
        quantum = Decimal(1).scaleb(-spec["outputScale"])
        try:
            normalized = result.decimal.quantize(quantum, rounding=ROUNDING_MODES[spec["roundingMode"]])
        except InvalidOperation:
            _fail("INVALID_DECIMAL", "规则结果无法按声明精度舍入。")
    output = spec["outputs"][0]
    return {
        "canonicalName": output["canonicalName"],
        "value": str(normalized),
        "valueType": output["valueType"],
        "unit": output.get("unit"),
        "unitDimension": output.get("unitDimension"),
        "resultDomain": output["resultDomain"],
        "rulePackage": spec["rulePackage"],
        "specificationHash": specification_hash(spec),
    }


def stable_topological_order(rules, *, target_outputs: list[str] | None = None):
    """Validate a rule package and return deterministic rule objects."""

    by_code = {}
    specs = {}
    output_producers = {}
    package_identities = set()
    for rule in rules:
        code = str(rule.rule_code)
        if not CODE_PATTERN.match(code):
            _fail("INVALID_SPECIFICATION", "rule_code必须是稳定规则标识。", ruleCode=code)
        if code in by_code:
            _fail("DUPLICATE_RULE", "规则包包含重复rule_code。", ruleCode=code)
        spec = validate_specification(rule.specification)
        if spec.get("ruleRole") == "OPERATION_ALLOCATION_COMPOSITION":
            _fail("NON_EXECUTABLE_RULE", "投产量组合声明不能进入工程公式计算图。")
        by_code[code] = rule
        specs[code] = spec
        package_identities.add((spec["rulePackage"]["code"], spec["rulePackage"]["version"]))
        for output in spec["outputs"]:
            name = output["canonicalName"]
            if name in output_producers:
                _fail(
                    "DUPLICATE_OUTPUT", "多个规则声明了同一输出。",
                    output=name, producers=[output_producers[name], code],
                )
            output_producers[name] = code

    if len(package_identities) > 1:
        _fail("RULE_PACKAGE_MISMATCH", "同一次DAG校验只能包含同一规则包版本。")

    outgoing = {code: set() for code in by_code}
    indegree = {code: 0 for code in by_code}
    for code, spec in specs.items():
        dependencies = spec.get("dependencies", [])
        for dependency in dependencies:
            if dependency not in by_code:
                _fail("UNKNOWN_DEPENDENCY", "规则依赖不存在。", ruleCode=code, dependency=dependency)
            outgoing[dependency].add(code)
            indegree[code] += 1
        for contract in spec["inputs"]:
            if contract["sourceType"] != "ENGINEERING_DERIVED":
                continue
            producer = output_producers.get(contract["canonicalName"])
            if not producer:
                _fail("MISSING_PRODUCER", "工程派生输入没有生产规则。", input=contract["canonicalName"])
            if producer not in dependencies:
                _fail(
                    "MISSING_PRODUCER", "工程派生输入的生产规则未声明为依赖。",
                    input=contract["canonicalName"], producer=producer, ruleCode=code,
                )

    ready = []
    for code, degree in indegree.items():
        if degree == 0:
            heapq.heappush(ready, (specs[code].get("priority", 100), code))
    ordered_codes = []
    while ready:
        _, code = heapq.heappop(ready)
        ordered_codes.append(code)
        for child in sorted(outgoing[code]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, (specs[child].get("priority", 100), child))
    if len(ordered_codes) != len(by_code):
        cyclic = sorted(code for code, degree in indegree.items() if degree)
        _fail("DEPENDENCY_CYCLE", "规则依赖图存在循环。", rules=cyclic)

    if target_outputs:
        missing_targets = sorted(set(target_outputs) - set(output_producers))
        if missing_targets:
            _fail("MISSING_PRODUCER", "规则包目标输出没有生产规则。", outputs=missing_targets)
        required = set()
        stack = [output_producers[name] for name in target_outputs]
        while stack:
            code = stack.pop()
            if code in required:
                continue
            required.add(code)
            stack.extend(specs[code].get("dependencies", []))
        unreachable = sorted(set(by_code) - required)
        if unreachable:
            _fail("UNREACHABLE_RULE", "规则包包含不贡献目标输出的规则。", rules=unreachable)
    return [by_code[code] for code in ordered_codes]


def execute_released_package(rules, input_values: dict, *, target_outputs: list[str] | None = None):
    """Execute released rules in-memory only; no formal result is persisted."""

    ordered = stable_topological_order(rules, target_outputs=target_outputs)
    pool = dict(input_values)
    outputs = {}
    trace = []
    for rule in ordered:
        if rule.status != "released":
            _fail("RULE_NOT_RELEASED", "只有已发布规则可以执行。", ruleCode=rule.rule_code)
        names = [row["canonicalName"] for row in rule.specification["inputs"]]
        result = evaluate_specification(rule.specification, {name: pool[name] for name in names if name in pool})
        value = {
            "value": result["value"],
            "unit": result.get("unit"),
            "unitDimension": result.get("unitDimension"),
        }
        pool[result["canonicalName"]] = value
        outputs[result["canonicalName"]] = result
        trace.append({
            "ruleCode": rule.rule_code,
            "version": rule.version,
            "specificationHash": result["specificationHash"],
        })
    return {"outputs": outputs, "trace": trace, "persisted": False}
