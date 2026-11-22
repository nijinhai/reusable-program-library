"""冻结的小型字符串/日期 DSL。参数表只从当前 fit 生成。"""

from __future__ import annotations

import calendar
from dataclasses import dataclass

from .canon import canonical_json

SEPARATORS = (" ", "-", "_", "/", ".", ",", ";", ":", "@", "|", "(", ")", "[", "]", "\t", "\n")
PARSE_FORMATS = (
    "%H:%M:%S",
    "%H:%M",
    "%Y-%m-%d",
    "%d-%b-%y",
    "%d-%b-%Y",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S",
)
OUTPUT_FORMATS = ("%Y", "%m", "%d", "%H", "%I", "%I%p", "%H:%M", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")
TOKEN_CLASSES = ("alpha", "digit", "alnum")
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class _Invalid:
    def __repr__(self) -> str:
        return "INVALID"


INVALID = _Invalid()


@dataclass(frozen=True)
class DateParts:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    minute: int | None = None
    second: int | None = None


@dataclass(frozen=True)
class Op:
    name: str
    params: tuple[tuple[str, object], ...]
    in_type: str
    out_type: str
    constant_baseline: bool = False

    def as_json(self) -> dict:
        return {"op": self.name, "params": {key: value for key, value in self.params}}

    def param(self, key: str):
        return dict(self.params)[key]


def program_text(ops: tuple[Op, ...]) -> str:
    return canonical_json([op.as_json() for op in ops])


def _common_prefix(rows: list[str]) -> str:
    if not rows:
        return ""
    prefix = rows[0]
    for row in rows[1:]:
        limit = min(len(prefix), len(row))
        index = 0
        while index < limit and prefix[index] == row[index]:
            index += 1
        prefix = prefix[:index]
    return prefix


def _common_suffix(rows: list[str]) -> str:
    reversed_rows = [row[::-1] for row in rows]
    return _common_prefix(reversed_rows)[::-1]


def build_ops(fit_inputs: list[str], fit_outputs: list[str]) -> tuple[Op, ...]:
    ops: list[Op] = []
    for name in ("strip", "lower", "upper", "title", "collapse_whitespace", "strip_leading_zeros"):
        ops.append(Op(name, (), "String", "String"))
    for name in ("take_left", "take_right", "drop_left", "drop_right"):
        variants = [Op(name, (("k", k),), "String", "String") for k in range(1, 9)]
        variants.sort(key=lambda op: canonical_json(op.as_json()["params"]))
        ops.extend(variants)
    present = [sep for sep in SEPARATORS if any(sep in row for row in fit_inputs)]
    for name in ("before", "after"):
        variants = [
            Op(name, (("sep", sep), ("which", which)), "String", "String")
            for sep in present
            for which in ("first", "last")
        ]
        variants.sort(key=lambda op: canonical_json(op.as_json()["params"]))
        ops.extend(variants)
    field_ops = [
        Op("field", (("k", k), ("sep", sep)), "String", "String") for sep in present for k in (0, 1, 2, -1, -2)
    ]
    field_ops.sort(key=lambda op: canonical_json(op.as_json()["params"]))
    ops.extend(field_ops)
    token_ops = [
        Op("match_token", (("class", kind), ("k", k)), "String", "String")
        for kind in TOKEN_CLASSES
        for k in (0, 1, 2, -1, -2)
    ]
    token_ops.sort(key=lambda op: canonical_json(op.as_json()["params"]))
    ops.extend(token_ops)
    prefix = _common_prefix(fit_outputs)
    suffix = _common_suffix(fit_outputs)
    for name, text in (("prepend", prefix), ("append", suffix)):
        variants = [Op(name, (("c", text[:length] if name == "prepend" else text[-length:]),), "String", "String") for length in range(1, min(8, len(text)) + 1)]
        variants.sort(key=lambda op: canonical_json(op.as_json()["params"]))
        ops.extend(variants)
    if fit_outputs and all(row == fit_outputs[0] for row in fit_outputs):
        ops.append(Op("constant", (("c", fit_outputs[0]),), "String", "String", constant_baseline=True))
    for fmt in PARSE_FORMATS:
        ops.append(Op("parse_datetime", (("format", fmt),), "String", "DateParts"))
    for fmt in OUTPUT_FORMATS:
        ops.append(Op("format_datetime", (("format", fmt),), "DateParts", "String"))
    return tuple(ops)


def build_clean_field_ops(fit_inputs: list[str]) -> tuple[Op, ...]:
    """clean_field(x, s, k) = strip(field(x, sep=s, k=k))。s、k 的候选规则与 field 相同。"""
    present = [sep for sep in SEPARATORS if any(sep in row for row in fit_inputs)]
    variants = [
        Op("clean_field", (("k", k), ("s", sep)), "String", "String")
        for sep in present
        for k in (0, 1, 2, -1, -2)
    ]
    variants.sort(key=lambda op: canonical_json(op.as_json()["params"]))
    return tuple(variants)


def _digits(text: str, index: int, width: int) -> tuple[int, int] | None:
    if index >= len(text) or not text[index].isdigit():
        return None
    end = index + 1
    limit = min(len(text), index + width)
    while end < limit and text[end].isdigit():
        end += 1
    return int(text[index:end]), end


def _valid_date(year: int, month: int, day: int) -> bool:
    if month < 1 or month > 12 or day < 1:
        return False
    return day <= calendar.monthrange(year, month)[1]


def parse_datetime(text: str, fmt: str):
    index = 0
    cursor = 0
    found: dict[str, int] = {}
    while cursor < len(fmt):
        if fmt[cursor] != "%":
            if index >= len(text) or text[index] != fmt[cursor]:
                return INVALID
            index += 1
            cursor += 1
            continue
        code = fmt[cursor : cursor + 2]
        cursor += 2
        if code == "%Y":
            if index + 4 > len(text) or not text[index : index + 4].isdigit():
                return INVALID
            found["year"] = int(text[index : index + 4])
            index += 4
        elif code == "%y":
            if index + 2 > len(text) or not text[index : index + 2].isdigit():
                return INVALID
            year = int(text[index : index + 2])
            found["year"] = 2000 + year if year <= 68 else 1900 + year
            index += 2
        elif code == "%b":
            token = text[index : index + 3]
            month = MONTHS.get(token.lower())
            if len(token) != 3 or month is None:
                return INVALID
            found["month"] = month
            index += 3
        elif code in {"%m", "%d", "%H", "%M", "%S"}:
            parsed = _digits(text, index, 2)
            if parsed is None:
                return INVALID
            value, index = parsed
            key = {"%m": "month", "%d": "day", "%H": "hour", "%M": "minute", "%S": "second"}[code]
            found[key] = value
        else:
            return INVALID
    if index != len(text):
        return INVALID
    if "month" in found and not 1 <= found["month"] <= 12:
        return INVALID
    if "hour" in found and not 0 <= found["hour"] <= 23:
        return INVALID
    if "minute" in found and not 0 <= found["minute"] <= 59:
        return INVALID
    if "second" in found and not 0 <= found["second"] <= 59:
        return INVALID
    if "day" in found and not 1 <= found["day"] <= 31:
        return INVALID
    if {"year", "month", "day"} <= found.keys() and not _valid_date(found["year"], found["month"], found["day"]):
        return INVALID
    return DateParts(
        year=found.get("year"),
        month=found.get("month"),
        day=found.get("day"),
        hour=found.get("hour"),
        minute=found.get("minute"),
        second=found.get("second"),
    )


def _hour12(hour: int) -> str:
    value = hour % 12
    return f"{12 if value == 0 else value:02d}"


def format_datetime(parts: DateParts, fmt: str):
    if fmt == "%Y":
        return INVALID if parts.year is None else f"{parts.year:04d}"
    if fmt == "%m":
        return INVALID if parts.month is None else f"{parts.month:02d}"
    if fmt == "%d":
        return INVALID if parts.day is None else f"{parts.day:02d}"
    if fmt == "%H":
        return INVALID if parts.hour is None else f"{parts.hour:02d}"
    if fmt == "%I":
        return INVALID if parts.hour is None else _hour12(parts.hour)
    if fmt == "%I%p":
        if parts.hour is None:
            return INVALID
        return f"{_hour12(parts.hour)}{'AM' if parts.hour < 12 else 'PM'}"
    if fmt == "%H:%M":
        if parts.hour is None or parts.minute is None:
            return INVALID
        return f"{parts.hour:02d}:{parts.minute:02d}"
    if fmt == "%Y-%m-%d":
        if parts.year is None or parts.month is None or parts.day is None:
            return INVALID
        return f"{parts.year:04d}-{parts.month:02d}-{parts.day:02d}"
    if fmt == "%m/%d/%Y":
        if parts.year is None or parts.month is None or parts.day is None:
            return INVALID
        return f"{parts.month:02d}/{parts.day:02d}/{parts.year:04d}"
    if fmt == "%d/%m/%Y":
        if parts.year is None or parts.month is None or parts.day is None:
            return INVALID
        return f"{parts.day:02d}/{parts.month:02d}/{parts.year:04d}"
    return INVALID


def _side(text: str, sep: str, which: str, before: bool):
    if sep not in text:
        return INVALID
    if which == "first":
        left, right = text.split(sep, 1)
    elif which == "last":
        left, right = text.rsplit(sep, 1)
    else:
        return INVALID
    return left if before else right


def _tokens(text: str, kind: str) -> list[str]:
    found = []
    index = 0
    while index < len(text):
        char = text[index]
        if kind == "alpha":
            ok = char.isascii() and char.isalpha()
        elif kind == "digit":
            ok = char.isascii() and char.isdigit()
        else:
            ok = char.isascii() and char.isalnum()
        if not ok:
            index += 1
            continue
        end = index + 1
        while end < len(text):
            nxt = text[end]
            if kind == "alpha":
                still = nxt.isascii() and nxt.isalpha()
            elif kind == "digit":
                still = nxt.isascii() and nxt.isdigit()
            else:
                still = nxt.isascii() and nxt.isalnum()
            if not still:
                break
            end += 1
        found.append(text[index:end])
        index = end
    return found


def apply_op(op: Op, value):
    if op.in_type == "String" and not isinstance(value, str):
        return INVALID
    if op.in_type == "DateParts" and not isinstance(value, DateParts):
        return INVALID
    name = op.name
    if name == "strip":
        return value.strip()
    if name == "lower":
        return value.lower()
    if name == "upper":
        return value.upper()
    if name == "title":
        return value.title()
    if name == "collapse_whitespace":
        return " ".join(value.split())
    if name == "strip_leading_zeros":
        if value == "":
            return ""
        index = 0
        while index < len(value) and value[index] == "0":
            index += 1
        if index == len(value):
            return "0"
        return value[index:]
    if name == "take_left":
        return value[: int(op.param("k"))]
    if name == "take_right":
        return value[-int(op.param("k")) :]
    if name == "drop_left":
        return value[int(op.param("k")) :]
    if name == "drop_right":
        return value[: -int(op.param("k"))]
    if name == "before":
        return _side(value, str(op.param("sep")), str(op.param("which")), True)
    if name == "after":
        return _side(value, str(op.param("sep")), str(op.param("which")), False)
    if name == "field":
        parts = value.split(str(op.param("sep")))
        index = int(op.param("k"))
        if index < -len(parts) or index >= len(parts):
            return INVALID
        return parts[index]
    if name == "match_token":
        parts = _tokens(value, str(op.param("class")))
        index = int(op.param("k"))
        if index < -len(parts) or index >= len(parts):
            return INVALID
        return parts[index]
    if name == "prepend":
        return str(op.param("c")) + value
    if name == "append":
        return value + str(op.param("c"))
    if name == "constant":
        return str(op.param("c"))
    if name == "parse_datetime":
        return parse_datetime(value, str(op.param("format")))
    if name == "format_datetime":
        return format_datetime(value, str(op.param("format")))
    if name == "clean_field":
        fielded = apply_op(Op("field", (("k", op.param("k")), ("sep", op.param("s"))), "String", "String"), value)
        if fielded is INVALID:
            return INVALID
        return apply_op(Op("strip", (), "String", "String"), fielded)
    return INVALID


def input_chars(value) -> int:
    return len(value) if isinstance(value, str) else 0
