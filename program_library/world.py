"""New controlled tasks; intention labels never enter the solver."""
from __future__ import annotations

import random
import string

SEEDS = (611, 612, 613, 614, 615)
FAMILIES = ("direct", "postprocess", "wrapped", "alternative_goal", "uncovered", "unexpressible")


def word(rng: random.Random) -> str:
    # Variable lengths/case prevent a fixed-position or constant answer.
    return "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(5, 12)))


def example(rng: random.Random, shape: int, family: str) -> dict:
    a, b, c = word(rng), word(rng), word(rng)
    pad = " " * rng.randint(1, 3)
    if shape == 0:
        raw = f"{pad}{a} {b}{pad}|{c}{pad}"
        target = f"{a} {b}"
        alternative = c
    elif shape == 1:
        raw = f"{pad}{a}-{b}{pad}"
        target = f"{a}-{b}".lower()
        alternative = f"{a}-{b}".upper()
    else:
        raw = f"{c}:{a}-{b}"
        target = f"{a}-{b}".upper()
        alternative = c
    if family == "postprocess":
        target = target.upper() if shape == 0 else target.split("-")[0]
    elif family == "wrapped":
        raw = f"{word(rng)}/{raw}"
    elif family == "alternative_goal":
        target = alternative
    elif family == "uncovered":
        raw = f"{pad}{a}{pad};{b}{pad}"
        target = a if shape == 0 else (b.lower() if shape == 1 else b.upper())
    elif family == "unexpressible":
        raw = f"{pad}{a}-{b}{pad}"
        target = f"{a}-{b}"[::-1]
    return {"input": raw, "output": target}


def task(seed: int, phase: str, index: int, shape: int, family: str) -> dict:
    rng = random.Random(f"rb-v01:{seed}:{phase}:{index}")
    rows = [example(rng, shape, family) for _ in range(20)]
    assert len({r["input"] for r in rows}) == 20
    return {
        "task_id": f"rb-{seed}-{phase}-{index:03}", "phase": phase,
        "design_family": family, "design_shape": shape,
        "fit": rows[:4], "check": rows[4:8], "query": rows[8:],
    }


def make_world(seed: int) -> dict:
    historical_families = ("direct", "postprocess", "wrapped", "alternative_goal")
    history = [task(seed, "history", i, i % 3, historical_families[i // 3]) for i in range(12)]
    mothers = [task(seed, "mother", i, i, "direct") for i in range(3)]
    future = [task(seed, "future", i * 10 + j, j % 3, family)
              for i, family in enumerate(FAMILIES) for j in range(10)]
    random.Random(f"rb-order:{seed}").shuffle(future)
    return {"seed": seed, "history": history, "mothers": mothers, "future": future}
