"""Charged FIFO with cached successful paths and arbitrary two-step macros."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

from .dsl import INVALID, Op, apply_op


def canon(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def op(name: str, **params) -> Op:
    return Op(name, tuple(sorted(params.items())), "String", "String")


def primitives() -> tuple[Op, ...]:
    fixed = [op(n) for n in ("strip", "lower", "upper", "title", "collapse_whitespace", "strip_leading_zeros")]
    fixed += [op(n, k=k) for n in ("drop_left", "drop_right") for k in (1, 2, 3)]
    fixed += [op("field", sep=s, k=k) for s in ("|", ":", ";", "/", "(") for k in (0, 1, -1)]
    fixed += [op("match_token", **{"class": c, "k": k}) for c in ("alpha", "digit") for k in (0, -1)]
    return tuple(fixed)


@dataclass(frozen=True)
class Macro:
    mid: str
    steps: tuple[Op, ...]
    mothers: tuple[str, ...] = ()

    def packed(self):
        return {"id": self.mid, "steps": [s.as_json() for s in self.steps], "mothers": self.mothers}


class BudgetEnd(Exception):
    pass


class Meter:
    def __init__(self, limit: int):
        self.limit, self.calls, self.characters = limit, 0, 0

    def vector(self, steps: tuple[Op, ...], values: tuple[str, ...], local_left: int | None = None):
        result = []
        used = 0
        for value in values:
            for step in steps:
                if self.calls >= self.limit or (local_left is not None and used >= local_left):
                    raise BudgetEnd
                self.calls += 1
                used += 1
                self.characters += len(value)
                value = apply_op(step, value)
                if value is INVALID:
                    break
            result.append(value)
        return tuple(result)


def features(values: tuple[str, ...], targets: tuple[str, ...], macro: Macro) -> tuple:
    """Only string relations: no candidate execution, no hidden local goal."""
    all_rows = lambda predicate: int(all(predicate(x, y) for x, y in zip(values, targets)))
    first = macro.steps[0]
    sep = first.param("sep") if first.name == "field" else None
    return (
        *(int(all(s in x for x in values)) for s in ("|", ":", ";", "/", "(")),
        all_rows(lambda x, y: x != x.lstrip()),
        all_rows(lambda x, y: x != x.rstrip()),
        all_rows(lambda x, y: y in x),
        all_rows(lambda x, y: y.lower() in x.lower()),
        all_rows(lambda x, y: y == x.strip()),
        all_rows(lambda x, y: y == y.lower()),
        all_rows(lambda x, y: y == y.upper()),
        all_rows(lambda x, y: len(y) < len(x)),
        int(sep is not None and all(sep in x for x in values)),
    )


class Evidence:
    def __init__(self):
        self.task = {}
        self.local = {}
        self.support = Counter()
        self.records = []
        self.replay_calls = 0
        self.feature_characters = 0

    def build(self, history: list[dict], macros: list[Macro]):
        meter = Meter(10**9)
        seen = set()
        for item in history:
            values, targets = tuple(item["inputs"]), tuple(item["targets"])
            path = item["path"]
            for position in range(len(path) - 2):
                current, milestone = tuple(path[position]), tuple(path[position + 2])
                for macro in macros:
                    before = meter.calls
                    output = meter.vector(macro.steps, current)
                    label = "match" if output == milestone else ("neutral" if output == current else "mismatch")
                    root_key, local_key = features(values, targets, macro), features(current, targets, macro)
                    self.feature_characters += sum(len(x) + len(y) for x, y in zip(values, targets))
                    self.feature_characters += sum(len(x) + len(y) for x, y in zip(current, targets))
                    rec = {"task_id": item["task_id"], "position": position, "macro": macro.mid,
                           "root_key": root_key, "local_key": local_key, "label": label,
                           "calls": meter.calls - before}
                    self.records.append(rec)
                    if label == "neutral":
                        continue
                    if label == "match":
                        self.support[macro.mid] += 1
                    for table, key in ((self.task, root_key), (self.local, local_key)):
                        dedup = (id(table), item["task_id"], macro.mid, key, label)
                        if dedup in seen:
                            continue
                        seen.add(dedup)
                        cell = table.setdefault((macro.mid, key), Counter())
                        cell[label] += 1
        self.replay_calls = meter.calls
        return self


class Gate:
    def __init__(self, arm: str, seed: int, task_id: str, inputs, targets, evidence: Evidence):
        self.arm, self.seed, self.task_id = arm, seed, task_id
        self.inputs, self.targets = tuple(inputs), tuple(targets)
        self.evidence = evidence
        self.decisions = Counter()
        self.feature_characters = 0

    def allow(self, macro: Macro, current: tuple[str, ...]):
        if self.arm == "NO_REPLAY":
            self.decisions["direct"] += 1
            return True
        source = self.inputs if self.arm == "TASK_REPLAY" else current
        self.feature_characters += sum(len(x) + len(y) for x, y in zip(source, self.targets))
        key = features(source, self.targets, macro)
        table = self.evidence.task if self.arm == "TASK_REPLAY" else self.evidence.local
        cell = table.get((macro.mid, key), {})
        positive, negative = cell.get("match", 0), cell.get("mismatch", 0)
        if positive > negative:
            label, probability = "supported", 1.0
        elif negative > positive:
            label, probability = "negative_review", 1 / 16
        else:
            label, probability = "unknown", 1 / 4
        payload = canon([self.seed, self.task_id, current, macro.mid])
        coin = int(hashlib.sha256(payload.encode()).hexdigest()[:16], 16) / 2**64
        answer = coin < probability
        self.decisions[label + ("_allow" if answer else "_skip")] += 1
        return answer


def search(inputs, targets, *, budget: int, macros: list[Macro] | None = None,
           gate: Gate | None = None, macro_budget: int = 1024, max_length: int = 5,
           base_ops=None) -> dict:
    inputs, targets = tuple(inputs), tuple(targets)
    meter = Meter(budget)
    started = time.perf_counter()
    # program, outputs, path of values, macro IDs used
    queue = deque([((), inputs, (inputs,), ())])
    seen = {inputs}
    best = (sum(x != y for x, y in zip(inputs, targets)), 0, "[]", (), (inputs,), ())
    macro_calls = 0
    expansions = 0
    stop = "frontier_exhausted"
    exact = inputs == targets
    primitive_list = primitives() if base_ops is None else tuple(base_ops)
    while queue and not exact:
        program, values, path, used = queue.popleft()
        if len(program) >= max_length:
            continue
        actions = []
        if macro_calls < macro_budget:
            for macro in macros or []:
                if len(program) + len(macro.steps) <= max_length and (gate is None or gate.allow(macro, values)):
                    actions.append((macro.steps, macro.mid))
        actions += [((step,), None) for step in primitive_list]
        for steps, mid in actions:
            if len(program) + len(steps) > max_length:
                continue
            if mid is not None and macro_budget - macro_calls < len(steps) * len(inputs):
                continue
            before = meter.calls
            try:
                output = meter.vector(steps, values, macro_budget - macro_calls if mid else None)
            except BudgetEnd:
                if mid:
                    macro_calls += meter.calls - before
                stop = "call_budget"
                queue.clear()
                break
            if mid:
                macro_calls += meter.calls - before
            expansions += 1
            if any(x is INVALID for x in output):
                continue
            child = program + steps
            child_path = path + (output,)
            # Successful primitive paths are used for replay. Macro future paths are evaluation only.
            child_used = used + ((mid,) if mid else ())
            errors = sum(x != y for x, y in zip(output, targets))
            candidate = (errors, len(child), canon([s.as_json() for s in child]))
            if candidate < best[:3]:
                best = (*candidate, child, child_path, child_used)
            if errors == 0:
                best = (*candidate, child, child_path, child_used)
                exact, stop = True, "exact_fit"
                break
            if output not in seen:
                seen.add(output)
                queue.append((child, output, child_path, child_used))
    return {"program": best[3], "path": best[4], "used_macros": best[5], "exact_fit": exact,
            "fit_errors": best[0], "calls": meter.calls, "macro_calls": macro_calls,
            "characters": meter.characters, "expansions": expansions, "stop": "exact_fit" if exact else stop,
            "wall_seconds": time.perf_counter() - started}


def evaluate(program, rows: list[dict]) -> tuple[list[bool], int]:
    meter = Meter(10**9)
    output = meter.vector(tuple(program), tuple(row["input"] for row in rows))
    return [x == row["output"] for x, row in zip(output, rows)], meter.calls


def candidates(mothers: list[tuple[dict, dict]]) -> list[Macro]:
    found = {}
    for task, result in mothers:
        if not result["exact_fit"] or not result["check_ok"]:
            continue
        program = result["program"]
        for i in range(len(program) - 1):
            steps = tuple(program[i:i + 2])
            key = canon([s.as_json() for s in steps])
            found.setdefault(key, {"steps": steps, "mothers": []})["mothers"].append(task["task_id"])
    return [Macro(f"m{i}", found[key]["steps"], tuple(sorted(set(found[key]["mothers"]))))
            for i, key in enumerate(sorted(found)[:6])]
