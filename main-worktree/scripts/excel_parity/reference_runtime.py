"""Non-production Excel compatibility reference runtime.

Scope is the inventoried workbook's scalar formulas. Unsupported operations and
broken source propagate outside IFERROR: they are adapter failures, not Excel
cell errors. Microsoft Excel remains the required parity authority.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from formula_ast import Parser, SUPPORTED, Unsupported, BrokenSource, shift_reference, split_reference
from workbook_source import coord, address


class EmptyCell:
    pass


class OmittedArgument:
    pass


BLANK = EmptyCell()
OMITTED = OmittedArgument()


class ExcelError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def numeric(value):
    if value is BLANK or value is OMITTED:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if not value.strip():
            raise ExcelError("#VALUE!")
        try:
            return float(value)
        except ValueError:
            raise ExcelError("#VALUE!") from None
    raise ExcelError("#VALUE!")


def truth(value):
    if value is BLANK or value is OMITTED:
        return False
    if isinstance(value, (bool, int, float)):
        return bool(value)
    if isinstance(value, str) and value.upper() in ("TRUE", "FALSE"):
        return value.upper() == "TRUE"
    raise ExcelError("#VALUE!")


def excel_text(value):
    if value is BLANK or value is OMITTED:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ExcelError("#NUM!")
        return format(value, ".15g")
    return str(value)


def compare(left, right):
    # Excel comparison has type ordering number < text < logical. Blank adapts
    # to the other operand, without conflating stored zero/False/empty text.
    if left is BLANK:
        left = "" if isinstance(right, str) else False if isinstance(right, bool) else 0
    if right is BLANK:
        right = "" if isinstance(left, str) else False if isinstance(left, bool) else 0
    def key(x):
        if isinstance(x, bool):
            return 2, x
        if isinstance(x, str):
            return 1, x.casefold()
        return 0, x
    a, b = key(left), key(right)
    return (a > b) - (a < b)


def wildcard(pattern, text):
    if not isinstance(text, str):
        return False
    parts, i = [], 0
    while i < len(pattern):
        char = pattern[i]
        if char == "~" and i + 1 < len(pattern):
            i += 1
            parts.append(re.escape(pattern[i]))
        else:
            parts.append(".*" if char == "*" else "." if char == "?" else re.escape(char))
        i += 1
    return re.fullmatch("".join(parts), text, flags=re.I | re.S) is not None


def exact_lookup(key, value):
    # Lookup range blanks are not numeric zero/empty-text records. A blank
    # lookup-value reference is coerced to zero, not matched to an empty slot.
    # Keep this separate from ordinary worksheet comparison's blank adaptation.
    if value is BLANK:
        return False
    if key is BLANK:
        key = 0
    if isinstance(key, str) and any(x in key for x in "*?~"):
        return wildcard(key, value)
    return compare(key, value) == 0


def criteria_match(value, criterion):
    if criterion is BLANK:
        criterion = 0
    if not isinstance(criterion, str):
        return compare(value, criterion) == 0
    m = re.match(r"^(<=|>=|<>|=|<|>)(.*)$", criterion, re.S)
    operator, target = (m[1], m[2]) if m else ("=", criterion)
    if target and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", target):
        target = float(target)
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                return operator == "<>"
    elif any(x in target for x in "*?~") and operator in ("=", "<>"):
        found = wildcard(target, value)
        return found if operator == "=" else not found
    c = compare(value, target)
    return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[operator]


@dataclass
class Range:
    ctx: object
    sheet: str
    r1: int
    c1: int
    r2: int
    c2: int

    @property
    def shape(self):
        return self.r2-self.r1+1, self.c2-self.c1+1

    def get(self, row, col=0):
        if not (0 <= row < self.shape[0] and 0 <= col < self.shape[1]):
            raise ExcelError("#REF!")
        return self.ctx.cell(self.sheet, address(self.r1+row, self.c1+col))

    def positions(self):
        for r, c in self.ctx.positions.get(self.sheet, []):
            if self.r1 <= r <= self.r2 and self.c1 <= c <= self.c2:
                yield r-self.r1, c-self.c1

    def populated(self):
        for r, c in self.positions():
            yield self.get(r, c)

    def vector(self):
        rows, cols = self.shape
        if rows != 1 and cols != 1:
            raise ExcelError("#N/A")
        if cols == 1:
            # Preserve blank offsets and the first trailing blank for exact MATCH.
            end = min(rows, max((r for r, c in self.positions()), default=-1)+2)
            for i in range(end):
                yield i, self.get(i)
        else:
            for i in range(cols):
                yield i, self.get(0, i)


def scalar(value):
    if isinstance(value, Range):
        if value.shape != (1, 1):
            raise Unsupported("Implicit intersection / array scalar coercion")
        return value.get(0, 0)
    return value


def serialized(value):
    if value is BLANK:
        return {"type": "blank", "value": None}
    if value is OMITTED:
        return {"type": "omitted", "value": None}
    if isinstance(value, ExcelError):
        return {"type": "error", "value": value.code}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, (int, float)):
        return {"type": "number", "value": value}
    return {"type": "text", "value": value}


class Context:
    omitted = OMITTED

    def __init__(self, book, cells_to_family, functions, overrides=None):
        self.book, self.cells_to_family, self.functions = book, cells_to_family, functions
        self.overrides = overrides or {}
        self.cache, self.active = {}, set()
        self.parsed_source = {}
        self.positions = {s: sorted({coord(a) for a in cells} | {coord(a) for ss, a in self.overrides if ss == s}) for s, cells in book.sheets.items()}

    def cell(self, sheet, addr):
        key = (sheet, addr)
        if key in self.overrides:
            return self.overrides[key]
        if key in self.cache:
            return self.cache[key]
        if key in self.active:
            raise Unsupported("Circular source dependency: " + sheet + "!" + addr)
        if sheet not in self.book.sheets:
            raise BrokenSource("Missing worksheet " + sheet)
        cell = self.book.sheets[sheet].get(addr)
        if cell is None:
            return BLANK
        if not cell["formula"]:
            if cell["type"] == "e":
                raise ExcelError(cell["value"])
            return BLANK if cell["value"] is None else cell["value"]
        family = self.cells_to_family.get(sheet + "!" + addr)
        has_broken_text = "#REF!" in cell["formula"]
        if family not in self.functions and not has_broken_text:
            raise Unsupported("No generated function: " + sheet + "!" + addr)
        self.active.add(key)
        try:
            row, col = coord(addr)
            if has_broken_text:
                # Inspect the unchanged source AST lazily. A #REF! token in an
                # unvisited branch/argument is not a reached source dependency.
                # This does not generate a replacement formula or a 113th family.
                if key not in self.parsed_source:
                    self.parsed_source[key] = Parser().parse(cell["formula"], allow_broken=True)
                tree = self.parsed_source[key]
                result = self.source_ast(tree, sheet, row, col)
            else:
                result = self.functions[family](self, row, col)
            # Direct reference to a genuinely empty cell yields Excel numeric 0.
            if result is BLANK or result is OMITTED:
                result = 0
            self.cache[key] = result
            return result
        finally:
            self.active.remove(key)

    def source_ast(self, node, sheet, row, col):
        """Same scalar evaluator for unchanged source expressions/probe tests.

        Broken references raise only when visited. IFERROR may handle ordinary
        Excel errors but cannot conceal a visited source-damage/adapter failure.
        """
        kind = node['kind']
        if kind in ('number', 'text', 'boolean'):
            return node['value']
        if kind == 'omitted':
            return OMITTED
        if kind == 'error':
            if node['value'] == '#REF!':
                raise BrokenSource(sheet + '!' + address(row, col) + ' visited #REF!')
            raise ExcelError(node['value'])
        if kind == 'reference':
            return self.reference(node['value'], sheet)
        if kind == 'binary':
            return self.binary(node['operator'], self.source_ast(node['left'], sheet, row, col), self.source_ast(node['right'], sheet, row, col))
        if kind in ('unary', 'percent'):
            return self.unary('%' if kind == 'percent' else node['operator'], self.source_ast(node['operand'], sheet, row, col))
        if kind == 'call' and node['name'] in SUPPORTED:
            return self.call(node['name'], [lambda n=n: self.source_ast(n, sheet, row, col) for n in node['arguments']], row=row, col=col)
        raise Unsupported('Source AST kind/function: ' + str(node))

    def reference(self, ref, sheet, row_delta=0, col_delta=0):
        ref = shift_reference(ref, row_delta, col_delta)
        try:
            target, parts = split_reference(ref, sheet)
        except Unsupported:
            matches = [n for n in self.book.names if n["name"].casefold() == ref.casefold() and "localSheetId" not in n]
            if len(matches) == 1:
                return self.reference(matches[0]["expression"], sheet)
            raise
        if len(parts) == 1 and re.search(r"\d", parts[0]):
            return self.cell(target, parts[0].replace("$", ""))
        if len(parts) != 2:
            raise Unsupported("Not a cell/range: " + ref)
        left, right = parts
        full = not re.search(r"\d", left+right)
        r1, c1 = coord(left + "1" if full else left)
        r2, c2 = coord(right + "1048576" if full else right)
        return Range(self, target, r1, c1, r2, c2)

    @staticmethod
    def error(code):
        raise ExcelError(code)

    @staticmethod
    def unary(op, value):
        value = numeric(scalar(value))
        return value if op == "+" else -value if op == "-" else value / 100

    @staticmethod
    def binary(op, left, right):
        left, right = scalar(left), scalar(right)
        if op == "&":
            return excel_text(left) + excel_text(right)
        if op in ("=", "<>", "<", ">", "<=", ">="):
            c = compare(left, right)
            return {"=": c == 0, "<>": c != 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[op]
        a, b = numeric(left), numeric(right)
        if op == "+": return a+b
        if op == "-": return a-b
        if op == "*": return a*b
        if op == "/":
            if b == 0: raise ExcelError("#DIV/0!")
            return a/b
        if op == "^":
            try: return math.pow(a,b)
            except (ValueError, OverflowError): raise ExcelError("#NUM!") from None
        raise Unsupported("Operator " + op)

    def call(self, name, args, *, row, col):
        if name == "IF":
            if not 2 <= len(args) <= 3: raise ExcelError("#VALUE!")
            selected = 1 if truth(scalar(args[0]())) else 2
            result = args[selected]() if selected < len(args) else False
            return 0 if result is OMITTED or result is BLANK else result
        if name == "IFERROR":
            if len(args) != 2: raise ExcelError("#VALUE!")
            try: return args[0]()
            except ExcelError: return args[1]()
        if name == "IFS":
            if len(args) % 2: raise ExcelError("#VALUE!")
            for i in range(0, len(args), 2):
                if truth(scalar(args[i]())):
                    result = args[i+1]()
                    return 0 if result is BLANK or result is OMITTED else result
            raise ExcelError("#N/A")
        if name == "ROW":
            if args: raise Unsupported("ROW(reference) not in current target; address-preserving AST required")
            return row
        values = []
        for i, argument in enumerate(args):
            try:
                values.append(argument())
            except ExcelError as exc:
                # Native R2 B146: an error-valued SUMIFS criterion is not an
                # eager function error; ordinary criteria cells do not match it.
                # Preserve the error as a typed criterion, never a magic result.
                if name == "SUMIFS" and i >= 2 and i % 2 == 0:
                    values.append(exc)
                else:
                    raise
        if name in ("AND", "OR"):
            logical = []
            for v in values:
                if isinstance(v, Range):
                    logical.extend(truth(x) for x in v.populated() if isinstance(x, (int, float, bool)))
                else:
                    logical.append(truth(scalar(v)))
            if not logical: raise ExcelError("#VALUE!")
            return all(logical) if name == "AND" else any(logical)
        if name == "INDEX":
            table = values[0]
            if not isinstance(table, Range): raise ExcelError("#VALUE!")
            r = int(numeric(values[1]))
            c = int(numeric(values[2])) if len(values)>2 else 1
            if r == 0 or c == 0: raise Unsupported("INDEX array return")
            result = table.get(r-1, c-1)
            return 0 if result is BLANK else result
        if name in ("MATCH", "VLOOKUP"):
            key, table = values[:2]
            if not isinstance(table, Range): raise ExcelError("#VALUE!")
            if name == "MATCH":
                mode = numeric(values[2]) if len(values)>2 else 1
                if mode != 0: raise Unsupported("Approximate MATCH requires sorted-collation oracle")
                for i, value in table.vector():
                    if exact_lookup(key, value): return i+1
            else:
                exact = len(values)>3 and not truth(values[3])
                if not exact: raise Unsupported("Approximate VLOOKUP requires sorted-collation oracle")
                c = int(numeric(values[2]))
                if not 1 <= c <= table.shape[1]: raise ExcelError("#REF!")
                end = min(table.shape[0], max((r for r, _ in table.positions()), default=-1)+2)
                for r in range(end):
                    if exact_lookup(key, table.get(r, 0)):
                        result = table.get(r, c-1)
                        return 0 if result is BLANK else result
            raise ExcelError("#N/A")
        if name == "SUM":
            total = 0
            for value in values:
                if isinstance(value, Range):
                    for x in value.populated():
                        if isinstance(x, (int, float)) and not isinstance(x, bool): total += x
                else:
                    total += numeric(value)
            return total
        if name == "COUNTIF":
            table, criterion = values
            if not isinstance(table, Range): raise ExcelError("#VALUE!")
            result, populated = 0, 0
            for value in table.populated():
                populated += 1
                result += criteria_match(value, criterion)
            if criteria_match(BLANK, criterion):
                result += table.shape[0]*table.shape[1]-populated
            return result
        if name in ("SUMIF", "SUMIFS"):
            if name == "SUMIF":
                ranges, tests = [values[0]], [values[1]]
                total_range = values[2] if len(values)>2 else values[0]
            else:
                total_range, ranges, tests = values[0], values[1::2], values[2::2]
            if not isinstance(total_range, Range) or not all(isinstance(r, Range) for r in ranges): raise ExcelError("#VALUE!")
            if any(r.shape != total_range.shape for r in ranges):
                raise Unsupported("SUMIF/SUMIFS unequal-shape semantics")
            total = 0
            for r, c in total_range.positions():
                def matches(rng, test):
                    try:
                        value = rng.get(r,c)
                    except ExcelError:
                        if isinstance(test, ExcelError):
                            # Not covered by the frozen native corpus. Do not
                            # guess error-to-error criterion matching semantics.
                            raise Unsupported("SUMIFS error criterion against error cell requires native evidence") from None
                        # An error-valued criteria cell does not satisfy an
                        # ordinary criterion. Do not evaluate its sum cell.
                        # Source damage (BrokenSource) remains fail-closed.
                        return False
                    if isinstance(test, ExcelError):
                        return False
                    return criteria_match(value, test)
                if all(matches(rng, test) for rng,test in zip(ranges,tests)):
                    value = total_range.get(r,c)
                    if isinstance(value, (int,float)) and not isinstance(value,bool): total += value
            return total
        values = [scalar(v) for v in values]
        if name == "ROUND":
            return float(Decimal(str(numeric(values[0]))).quantize(Decimal(1).scaleb(-int(numeric(values[1]))), rounding=ROUND_HALF_UP))
        if name == "TEXT":
            fmt = values[1]
            if not isinstance(fmt,str) or not re.fullmatch(r"0+",fmt):
                raise Unsupported("TEXT format not inventoried/implemented: " + str(fmt))
            n = numeric(values[0])
            rounded = Decimal(str(abs(n))).quantize(Decimal(1),rounding=ROUND_HALF_UP)
            return ("-" if n<0 else "")+str(int(rounded)).zfill(len(fmt))
        if name in ("CONCAT", "CONCATENATE"):
            return "".join(excel_text(v) for v in values)
        if name == "TRIM": return re.sub(" +", " ", excel_text(values[0]).strip(" "))
        if name == "LEFT":
            n = int(numeric(values[1])) if len(values)>1 else 1
            if n<0: raise ExcelError("#VALUE!")
            return excel_text(values[0])[:n]
        if name == "FIND":
            start = int(numeric(values[2])) if len(values)>2 else 1
            string = excel_text(values[1])
            if start<1 or start>len(string): raise ExcelError("#VALUE!")
            index = string.find(excel_text(values[0]), start-1)
            if index<0: raise ExcelError("#VALUE!")
            return index+1
        if name == "CHAR":
            n = int(numeric(values[0]))
            if not 1 <= n <= 255: raise ExcelError("#VALUE!")
            if n>127: raise Unsupported("CHAR code-page dependent; native locale required")
            return chr(n)
        raise Unsupported("Function " + name)
