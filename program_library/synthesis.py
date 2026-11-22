"""Small explicit meta-grammar; hypotheses are generated and parameter-fit from examples."""
from __future__ import annotations

import ast
import itertools
import re
import time
from dataclasses import dataclass
from fractions import Fraction

from . import engine


def weight(expr):
    return max(1, sum(isinstance(n, (ast.Call, ast.Subscript, ast.BinOp)) for n in ast.walk(ast.parse(expr, mode="eval"))))


@dataclass
class Learned:
    expr: str
    kind: str

    def __post_init__(self):
        self.cost = weight(self.expr)
        self.source = f"def solve(text):\n    return {self.expr}\n"
        self.mid = "g" + __import__('hashlib').sha256(self.source.encode()).hexdigest()[:12]
        namespace = {"re": re, "__builtins__": {"str": str, "int": int}}
        exec(self.source, namespace)
        self.fn = namespace["solve"]

    def apply(self, text):
        try:
            value = self.fn(text)
            return value if isinstance(value, str) else engine.INVALID
        except (ValueError, IndexError, AttributeError, TypeError, OverflowError):
            return engine.INVALID

    def packed(self):
        return {"id": self.mid, "kind": self.kind, "expr": self.expr, "source": self.source, "cost": self.cost}


def expressions(fit):
    xs, ys = [r["input"] for r in fit], [r["output"] for r in fit]
    pre = [("text", tuple(xs), 0)]
    pre.append(("text.strip()", tuple(x.strip() for x in xs), len(xs)))
    for sep in ("/", "|", ":", ";"):
        if all(sep in x for x in xs):
            for k in (0, -1):
                pre.append((f"text.split({sep!r})[{k}]", tuple(x.split(sep)[k] for x in xs), 2*len(xs)))
    generation_calls = sum(x[2] for x in pre)
    found = {}
    for expr, values, _ in pre:
        kernels = [(f"({expr})[::-1]", "reverse")]
        oldchars = sorted({c for x in values for c in x if not c.isalnum()})[:12]
        newchars = sorted({c for y in ys for c in y if not c.isalnum()} | {""})[:12]
        for old in oldchars:
            for new in newchars:
                if old != new:
                    kernels.append((f"({expr}).replace({old!r},{new!r})", "replace"))
        for sep in ("|", ":", ";", "/", "-"):
            parts = [v.split(sep) for v in values]
            sizes = {len(p) for p in parts}
            if len(sizes) != 1 or next(iter(sizes)) not in (2, 3):
                continue
            n = len(parts[0])
            joins = [s for s in ("/", " ", "-", ":", ";", "|") if all(s in y for y in ys)]
            for permutation in itertools.permutations(range(n)):
                for join in joins:
                    fields = ",".join(f"({expr}).split({sep!r})[{i}]" for i in permutation)
                    kernels.append((f"{join!r}.join([{fields}])", "reorder"))
        numbers = [re.search(r"-?\d+", v) for v in values]
        if all(numbers) and all(re.fullmatch(r"-?\d+", y) for y in ys):
            nx, ny = [int(x.group(0)) for x in numbers], [int(y) for y in ys]
            pair = next(((i, j) for i in range(len(nx)) for j in range(i+1, len(nx)) if nx[i] != nx[j]), None)
            if pair:
                i, j = pair
                a = Fraction(ny[j]-ny[i], nx[j]-nx[i]); b = ny[i]-a*nx[i]
                if a.denominator == b.denominator == 1 and -10 <= a <= 10:
                    kernels.append((f"str({int(a)}*int(re.search(r'-?\\d+',({expr})).group(0))+({int(b)}))", "affine"))
        for kernel, kind in kernels:
            for post in (kernel, f"({kernel}).lower()", f"({kernel}).upper()", f"({kernel})[1:]"):
                found.setdefault(post, kind)
    result = [Learned(expr, kind) for expr, kind in found.items()]
    result.sort(key=lambda c: (c.cost, len(c.source), c.source))
    return result[:1024], generation_calls


def propose(fit, check):
    started = time.perf_counter()
    pool, generation_calls = expressions(fit)
    calls, attempted, checks = generation_calls, 0, 0
    for candidate in pool:
        attempted += 1
        passed = True
        for row in fit:
            calls += candidate.cost
            if candidate.apply(row["input"]) != row["output"]:
                passed = False
                break
        if not passed:
            continue
        for row in check:
            calls += candidate.cost
            checks += 1
            if candidate.apply(row["input"]) != row["output"]:
                passed = False
                break
        if passed:
            return candidate, {"calls": calls, "attempted": attempted, "generated": len(pool), "check_rows": checks,
                               "generation_characters": sum(len(r["input"])+len(r["output"]) for r in fit),
                               "wall_seconds": time.perf_counter()-started}
    return None, {"calls": calls, "attempted": attempted, "generated": len(pool), "check_rows": checks,
                  "generation_characters": sum(len(r["input"])+len(r["output"]) for r in fit),
                  "wall_seconds": time.perf_counter()-started}
