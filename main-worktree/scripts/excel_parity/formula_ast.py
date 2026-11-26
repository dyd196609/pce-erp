"""Deterministic Excel token -> AST -> Python reference-function translator.

No eval, arbitrary expression execution, file access or network inside formulas.
Unknown syntax is rejected, never rewritten to an approximate formula.
"""
from __future__ import annotations

import copy
import re
from openpyxl.formula.tokenizer import Tokenizer
from workbook_source import coord, address

SUPPORTED = frozenset("IF IFS IFERROR AND OR VLOOKUP INDEX MATCH SUM SUMIF SUMIFS ROUND CONCAT CONCATENATE TRIM LEFT FIND ROW CHAR TEXT COUNTIF".split())


class Unsupported(Exception):
    pass


class BrokenSource(Exception):
    pass


class Parser:
    PRECEDENCE = {"=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1, "&": 2, "+": 3, "-": 3, "*": 4, "/": 4, "^": 5}

    def parse(self, formula, *, allow_broken=False):
        if "#REF!" in formula and not allow_broken:
            raise BrokenSource("Formula text contains #REF!: excluded from translation")
        try:
            self.tokens = [t for t in Tokenizer(formula).items if t.type != "WHITE-SPACE"]
        except Exception as exc:
            raise Unsupported(f"Tokenization: {exc}") from exc
        self.i = 0
        result = self.expression(0)
        if self.i != len(self.tokens):
            raise Unsupported(f"Unconsumed token: {self.tokens[self.i].value}")
        return result

    def expression(self, minimum):
        if self.i >= len(self.tokens):
            raise Unsupported("Unexpected end of formula")
        token = self.tokens[self.i]
        self.i += 1
        if token.type == "OPERAND":
            if token.subtype == "NUMBER":
                node = {"kind": "number", "value": float(token.value) if re.search(r"[.eE]", token.value) else int(token.value)}
            elif token.subtype == "TEXT":
                node = {"kind": "text", "value": token.value[1:-1].replace('""', '"')}
            elif token.subtype == "LOGICAL":
                node = {"kind": "boolean", "value": token.value.upper() == "TRUE"}
            elif token.subtype == "ERROR":
                node = {"kind": "error", "value": token.value}
            elif token.subtype == "RANGE":
                node = {"kind": "reference", "value": token.value}
            else:
                raise Unsupported(f"Operand: {token.subtype}")
        elif token.type == "OPERATOR-PREFIX" and token.value in ("+", "-"):
            node = {"kind": "unary", "operator": token.value, "operand": self.expression(6)}
        elif token.type == "PAREN" and token.subtype == "OPEN":
            node = self.expression(0)
            self.close("PAREN")
        elif token.type == "FUNC" and token.subtype == "OPEN":
            name = token.value[:-1].upper().removeprefix("_XLFN.")
            args = []
            if self.i < len(self.tokens) and self.tokens[self.i].subtype == "CLOSE":
                self.close("FUNC")
            else:
                while True:
                    if self.i >= len(self.tokens):
                        raise Unsupported("Unterminated function")
                    next_token = self.tokens[self.i]
                    if next_token.type == "SEP" or next_token.subtype == "CLOSE":
                        args.append({"kind": "omitted"})
                    else:
                        args.append(self.expression(0))
                    if self.i < len(self.tokens) and self.tokens[self.i].type == "SEP":
                        self.i += 1
                        continue
                    self.close("FUNC")
                    break
            node = {"kind": "call", "name": name, "arguments": args}
        else:
            raise Unsupported(f"Unexpected token {token.type}/{token.subtype}: {token.value}")
        while self.i < len(self.tokens):
            token = self.tokens[self.i]
            if token.type == "OPERATOR-POSTFIX" and token.value == "%":
                self.i += 1
                node = {"kind": "percent", "operand": node}
                continue
            if token.type != "OPERATOR-INFIX" or token.value not in self.PRECEDENCE:
                break
            precedence = self.PRECEDENCE[token.value]
            if precedence < minimum:
                break
            self.i += 1
            node = {"kind": "binary", "operator": token.value, "left": node, "right": self.expression(precedence + 1)}
        return node

    def close(self, kind):
        if self.i >= len(self.tokens) or self.tokens[self.i].type != kind or self.tokens[self.i].subtype != "CLOSE":
            raise Unsupported(f"Expected closing {kind}")
        self.i += 1


def walk(node):
    if "kind" in node:
        yield node
    for value in node.values():
        if isinstance(value, dict):
            yield from walk(value)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, dict):
                    yield from walk(child)


def functions(tree):
    return sorted({n["name"] for n in walk(tree) if n["kind"] == "call"})


def references(tree):
    return sorted({n["value"] for n in walk(tree) if n["kind"] == "reference"})


REF_PART = re.compile(r"(\$?)([A-Z]+)(\$?)(\d+)?$")


def split_reference(ref, default_sheet):
    if "[" in ref or "#REF!" in ref:
        raise BrokenSource("External or broken reference: " + ref)
    if "!" in ref:
        sheet, ref = ref.rsplit("!", 1)
        sheet = sheet.strip("'").replace("''", "'")
    else:
        sheet = default_sheet
    parts = ref.split(":")
    if len(parts) > 2 or any(not REF_PART.fullmatch(p) for p in parts):
        raise Unsupported("Named/range reference requires resolution: " + ref)
    return sheet, parts


def reference_shape(ref, origin):
    """Relative rows/columns with absolute anchors retained (R1C1-equivalent)."""
    r, c = coord(origin)
    prefix, tail = (ref.rsplit("!", 1) if "!" in ref else (None, ref))
    shape = []
    for p in tail.split(":"):
        m = REF_PART.fullmatch(p)
        if not m:
            return {"literal_reference": ref}
        cc = coord(m[2] + "1")[1]
        shape.append({"column": cc if m[1] else cc-c, "column_absolute": bool(m[1]),
                      "row": (int(m[4]) if m[3] else int(m[4])-r) if m[4] else None,
                      "row_absolute": bool(m[3])})
    return {"sheet": prefix, "parts": shape}


def normalize(tree, origin):
    result = copy.deepcopy(tree)
    for node in walk(result):
        if node["kind"] == "reference":
            node["value"] = reference_shape(node["value"], origin)
    return result


def shift_reference(ref, row_delta, col_delta):
    prefix, tail = (ref.rsplit("!", 1) if "!" in ref else (None, ref))
    parts = []
    for p in tail.split(":"):
        m = REF_PART.fullmatch(p)
        if not m:
            return ref  # names are resolved by context, never string-rewritten
        col = coord(m[2] + "1")[1] + (0 if m[1] else col_delta)
        row = (int(m[4]) + (0 if m[3] else row_delta)) if m[4] else 1
        if col < 1 or col > 16384 or row < 1 or row > 1048576:
            raise BrokenSource("Shifted reference out of Excel bounds")
        a = address(row, col)
        parts.append(a if m[4] else re.sub(r"\d+", "", a))
    return (prefix + "!" if prefix else "") + ":".join(parts)


def generate_expression(node, origin, default_sheet, aliases):
    kind = node["kind"]
    if kind in ("number", "text", "boolean"):
        return repr(node["value"])
    if kind == "omitted":
        return "ctx.omitted"
    if kind == "reference":
        ref = node["value"]
        if ref in aliases:
            return aliases[ref] + "()"
        r, c = coord(origin)
        return f"ctx.reference({ref!r}, {default_sheet!r}, row - {r}, col - {c})"
    if kind == "error":
        return f"ctx.error({node['value']!r})"
    if kind in ("unary", "percent"):
        op = node.get("operator", "%")
        return f"ctx.unary({op!r}, {generate_expression(node['operand'], origin, default_sheet, aliases)})"
    if kind == "binary":
        return f"ctx.binary({node['operator']!r}, {generate_expression(node['left'], origin, default_sheet, aliases)}, {generate_expression(node['right'], origin, default_sheet, aliases)})"
    if kind == "call":
        if node["name"] not in SUPPORTED:
            raise Unsupported("Function " + node["name"])
        arguments = ", ".join("lambda: " + generate_expression(a, origin, default_sheet, aliases) for a in node["arguments"])
        return f"ctx.call({node['name']!r}, [{arguments}], row=row, col=col)"
    raise Unsupported("AST node " + kind)
