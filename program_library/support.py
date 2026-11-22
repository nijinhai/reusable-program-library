"""File I/O and source freezing for reproducible benchmark runs."""
import csv
import hashlib
import json
from pathlib import Path
from . import engine, world as world1

ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def csvwrite(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def jsonlines(path, rows):
    Path(path).write_text("".join(engine.canon(row) + "\n" for row in rows), encoding="utf-8")

def freeze(out, protocol, files, tasks, extra=None):
    out.mkdir(parents=True, exist_ok=True)
    if (out / "freeze.json").exists():
        raise RuntimeError("Already frozen; choose a fresh --output directory")
    dump(out / "tasks_frozen.json", tasks)
    dump(out / "freeze.json", {"protocol": protocol,
         "files": {p.name: sha(p) for p in sorted(ROOT.glob("*.py"))},
         "tasks_sha256": sha(out / "tasks_frozen.json"), "extra": extra or {}})

def verify(out):
    frozen = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
    if sha(out / "tasks_frozen.json") != frozen["tasks_sha256"]:
        raise RuntimeError("Frozen tasks changed")
    for name, digest in frozen["files"].items():
        if sha(ROOT / name) != digest:
            raise RuntimeError(f"Frozen source changed: {name}")
    return frozen
