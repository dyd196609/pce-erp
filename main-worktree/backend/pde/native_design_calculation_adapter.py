"""Map pinned native design facts to existing approved rule inputs, no formulas."""
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json

from masterdata.models import UnitOfMeasure
from .engineering_calculation_service import EngineeringCalculationError

CONTRACT = "NATIVE-APPROVED-INPUT-V1"
STRUCTURES = {"SINGLE_LEAF": "单开门", "SINGLE_CASING": "单面套"}
PAINT_BRANCHES = {"PAINTED": "有漆", "PAINT_FREE": "免漆"}
LINE_MODES = {"SINGLE": "单", "DOUBLE": "双"}


def _fail(code, reason, **details):
    raise EngineeringCalculationError(code, reason, details)


def _number(value, field, *, positive=False):
    try:
        if isinstance(value, bool) or value in (None, ""):
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result.adjusted() > 14 or (positive and result == 0):
            raise ValueError()
        return result
    except (ValueError, InvalidOperation):
        _fail("NATIVE_CALCULATION_INPUT_INVALID", "原生核算数值必须明确、有限且符合正负范围。", field=field)


def normalize_contract(value, *, frozen=False):
    if isinstance(value,dict) and value.get('ruleFamily')=='THREE_IN_ONE':
        from .cabinet_calculation_adapter import normalize
        return normalize(value,frozen=frozen)
    fields = {"contractVersion", "ruleFamily", "dimensionBasis", "structure", "paintBranch",
              "paintProcessTypeId", "casingDepth", "horizontalAdd", "verticalAdd", "lineMode",
              "quantityBasis", "provenance"}
    if not isinstance(value, dict) or set(value) - (fields | ({"unitProofs"} if frozen else set())):
        _fail("NATIVE_CALCULATION_CONTRACT_INVALID", "原生核算输入包含未受控字段。")
    if value.get("contractVersion") != CONTRACT or value.get("ruleFamily") != "ROOM_DOOR":
        _fail("NATIVE_CALCULATION_FAMILY_UNSUPPORTED", "尚未适配该原生规则族或输入契约版本。")
    if value.get("structure") not in STRUCTURES:
        _fail("NATIVE_CALCULATION_STRUCTURE_UNSUPPORTED", "结构必须明确选择既有受控单开门或单面套分支。")
    basis = "OPENING" if value["structure"] == "SINGLE_LEAF" else "CASING"
    if value.get("dimensionBasis") != basis:
        _fail("NATIVE_CALCULATION_DIMENSION_BASIS_REQUIRED", "设计高宽必须明确为当前结构要求的门洞或门套基准。")
    if value.get("paintBranch") not in PAINT_BRANCHES or type(value.get("paintProcessTypeId")) is not int:
        _fail("NATIVE_CALCULATION_PAINT_BRANCH_REQUIRED", "必须明确涂装分支及对应的精确涂装工艺引用，不按名称推断。")
    if value.get("lineMode") not in LINE_MODES or value.get("quantityBasis") != "ORDER_OBJECT_TOTAL":
        _fail("NATIVE_CALCULATION_QUANTITY_BASIS_REQUIRED", "必须明确线条单双和工程对象订单总数量口径。")
    for field in ("casingDepth", "horizontalAdd", "verticalAdd"):
        part = value.get(field)
        if not isinstance(part, dict) or set(part) != {"value", "uomId"} or type(part.get("uomId")) is not int:
            _fail("NATIVE_CALCULATION_INPUT_REQUIRED", "缺少带明确单位的原生核算输入。", field=field)
        _number(part.get("value"), field, positive=field == "casingDepth")
    proof = value.get("provenance")
    if (not isinstance(proof, dict) or not proof.get("reason") or not proof.get("classification")
            or not isinstance(proof.get("references"), list) or not proof["references"]
            or not all(isinstance(ref, str) and ref.strip() for ref in proof["references"])):
        _fail("NATIVE_CALCULATION_PROVENANCE_REQUIRED", "原生核算补充输入必须保留来源、分类和说明。")
    return json.loads(json.dumps(value, ensure_ascii=False))


def _unit_proof(unit):
    base = unit.conversion_base if unit.conversion_base_id else unit
    if (not unit.is_active or not base.is_active or unit.company_id != base.company_id
            or base.conversion_base_id or unit.dimension != base.dimension):
        _fail("NATIVE_CALCULATION_UNIT_INVALID", "单位必须具备同公司、同维度的受控直接换算基准。")
    return {"id": unit.pk, "companyId": unit.company_id, "code": unit.code,
            "dimension": unit.dimension, "factor": str(unit.conversion_factor),
            "baseId": base.pk, "baseCode": base.code, "baseFactor": str(base.conversion_factor)}


def freeze_contract_units(value, *, company_id, design_uom_id, physical_uom_id):
    if isinstance(value,dict) and value.get('ruleFamily')=='THREE_IN_ONE':
        from .cabinet_calculation_adapter import freeze
        return freeze(value,company_id)
    result = normalize_contract(value)
    targets = list(UnitOfMeasure.objects.filter(company_id=company_id, code__iexact="mm", is_active=True))
    if len(targets) != 1:
        _fail("NATIVE_CALCULATION_MM_UNIT_REQUIRED", "必须存在唯一有效的毫米单位。")
    target = targets[0]
    ids = {target.pk, design_uom_id, physical_uom_id,
           *[result[f]["uomId"] for f in ("casingDepth", "horizontalAdd", "verticalAdd")]}
    units = {u.pk: u for u in UnitOfMeasure.objects.select_related("conversion_base").filter(
        company_id=company_id, pk__in=ids, is_active=True)}
    if None in ids or set(units) != ids:
        _fail("NATIVE_CALCULATION_UNIT_SCOPE_MISMATCH", "尺寸或数量单位缺失、无效或跨公司。")
    proofs = {str(k): _unit_proof(u) for k, u in units.items()}
    result["unitProofs"] = {"targetMmId": target.pk, "units": proofs}
    return result


def _mm(value, uom_id, proof, field):
    source = proof["units"].get(str(uom_id)); target = proof["units"].get(str(proof["targetMmId"]))
    if (not source or not target or source["dimension"] != "length" or target["dimension"] != "length"
            or source["baseId"] != target["baseId"]):
        _fail("NATIVE_CALCULATION_UNIT_CONVERSION_UNAVAILABLE", "输入没有到毫米的同维度受控换算关系。", field=field)
    with localcontext() as ctx:
        ctx.prec = 28
        converted = _number(value, field, positive=field not in {"horizontalAdd", "verticalAdd"}) * Decimal(source["factor"]) / Decimal(target["factor"])
        rounded = converted.quantize(Decimal("0.000001"))
        if rounded != converted:
            _fail("NATIVE_CALCULATION_UNIT_PRECISION_REQUIRED", "单位换算不能无损保留6位小数。", field=field)
    return str(rounded)


def map_native_input(item):
    contract = item.get("nativeCalculationInputs")
    if not contract:
        _fail("NATIVE_DESIGN_CALCULATION_ADAPTER_REQUIRED", "冻结修订尚未登记原生核算输入契约；需通过设计及基线新版本补齐。")
    contract = normalize_contract(contract, frozen=True)
    proof = contract.get("unitProofs")
    if not isinstance(proof, dict) or not isinstance(proof.get("units"), dict):
        _fail("NATIVE_CALCULATION_UNIT_PROOF_REQUIRED", "冻结修订缺少单位换算证明。")
    identity = item["sourceIdentity"]
    units = {str(u.pk): _unit_proof(u) for u in UnitOfMeasure.objects.select_related("conversion_base").filter(
        company_id=identity["companyId"], pk__in=proof["units"], is_active=True)}
    if units != proof["units"] or any(u["companyId"] != identity["companyId"] for u in units.values()):
        _fail("NATIVE_CALCULATION_UNIT_PROOF_CHANGED", "当前单位定义与冻结换算证明不一致或跨公司。")
    if contract["paintProcessTypeId"] != item.get("paintProcessTypeId"):
        _fail("NATIVE_CALCULATION_PAINT_REFERENCE_MISMATCH", "涂装分支的工艺引用与冻结修订不一致。")
    quantity = _number(item.get("physicalQuantity"), "physicalQuantity", positive=True)
    quantity_unit = units.get(str(item.get("physicalUomId")))
    if not quantity_unit or quantity_unit["dimension"] != "count" or quantity != quantity.to_integral_value():
        _fail("NATIVE_CALCULATION_QUANTITY_INVALID", "当前结构需要明确的整数件数及数量单位。")
    values = {"J": _mm(item.get("designLength"), item.get("designUomId"), proof, "designLength"),
              "K": _mm(item.get("designWidth"), item.get("designUomId"), proof, "designWidth"),
              "M": str(quantity), "H": STRUCTURES[contract["structure"]],
              "I": PAINT_BRANCHES[contract["paintBranch"]], "V": quantity_unit["code"],
              "AZ": LINE_MODES[contract["lineMode"]]}
    for field, slot in (("casingDepth", "L"), ("horizontalAdd", "AO"), ("verticalAdd", "AP")):
        values[slot] = _mm(contract[field]["value"], contract[field]["uomId"], proof, field)
    return {"ruleFamily": "ROOM_DOOR", "canonicalInputs": values,
            "sourceKey": item["sourceKey"], "sourceIdentity": identity,
            "inputProof": {"baselineItemId": item["baselineItemId"], "contentHash": item["baselineContentHash"],
                "designRevisionId": identity["designRevisionId"], "contract": contract,
                "quantityBasis": "Frozen design object total; consumed once as M; no multiplication by sales-line quantity"}}


def preview_native_inputs(items):
    from .calculation_batch_reuse import evaluate_row, evaluate_linear_row, VERSION
    rows, blockers, mappings = [], [], []
    for item in items:
        try:
            mapped = map_native_input(item); mappings.append(mapped)
            calculated = [*evaluate_row(mapped), *evaluate_linear_row(mapped)]
            for row in calculated:
                row.update(sourceBasis=item["sourceKey"], nature="受控原生设计修订核算；用途资格独立判定")
            rows.extend(calculated)
        except EngineeringCalculationError as error:
            blockers.append({"code": error.code, "designObject": item["sourceKey"],
                             "reason": error.message, "details": error.details})
    digest = sha256(json.dumps(mappings, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    return {"rows": rows, "resultPositionCount": len(rows), "blockers": blockers, "batchFingerprint": digest,
            "inputRevisionHash": digest, "version": VERSION, "nativeMappings": mappings,
            "businessWriteSideEffectCount": 0}
