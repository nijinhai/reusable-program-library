"""Historical task generator, retained from the original experiment."""
import random
from . import world as world1

def source_task(seed, phase, i):
    rng = random.Random(f"natural-pool:{seed}:{phase}:{i}")
    rows = []
    for _ in range(20):
        a, b, c = (world1.word(rng) for _ in range(3))
        pad = " " * rng.randint(1, 3)
        family, variant = i % 6, (i // 6) % 5
        sep = ("|", ":", ";", "/", "(")[variant]
        if family == 0:
            x, y = f"{pad}{a} {b}{pad}{sep}{c}{pad}", f"{a} {b}"
        elif family == 1:
            x = f"{pad}{a}-{b}{pad}"
            y = (str.lower, str.upper, str.title, str.lower, str.upper)[variant](x.strip())
        elif family == 2:
            number = str(rng.randint(10000, 999999))
            x, y = "0" * rng.randint(2, 4) + number, number[:-(variant % 3 + 1)]
        elif family == 3:
            core = f"{a} {b}"
            x = f"{pad}{core}{pad}"
            y = core[(variant % 3 + 1):]
        elif family == 4:
            x, y = f"{c}/{pad}{a} {b}{pad}|tail", f"{a} {b}"
            if variant % 2:
                y = y.upper()
        else:
            x = f"{rng.randint(10, 99)}-{a}_{rng.randint(100, 999)}"
            y = a.upper() if variant % 2 else a.lower()
        rows.append({"input": x, "output": y})
    return {"task_id": f"na-{seed}-{phase}-{i:03}", "fit": rows[:4], "check": rows[4:8], "query": rows[8:]}
