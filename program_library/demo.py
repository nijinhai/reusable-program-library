"""Small, deterministic demonstration: acquire, freeze, compose, evaluate."""
import json
from .synthesis import propose
from .runtime import search, score


def main():
    fit = [{"input": "abc-Def", "output": "feD-cba"},
           {"input": "XyZ-wvu", "output": "uvw-ZyX"}]
    check = [{"input": "ijk-LmN", "output": "NmL-kji"}]
    learned, fees = propose(fit, check)
    if learned is None:
        raise RuntimeError("No source function passed validation")
    library = {learned.mid: learned}
    # No further proposal or updates: the same function must be reused.
    xs = ["tag/abc-DeF", "other/ghi-JkL"]
    ys = ["FeD-cba", "LkJ-ihg"]
    baseline = search(xs, ys)
    reused = search(xs, ys, library)
    held_out = [{"input": "new/mno-PqR", "output": "RqP-onm"}]
    mask, _ = score(reused["program"], held_out, library)
    print("1. Learn from source examples and validate")
    print(learned.source)
    print("2. Freeze library; solve a wrapped task by composition")
    print(json.dumps(reused["program"], ensure_ascii=False, indent=2))
    print("3. Evaluate an unseen input after program selection")
    print(f"Input: {held_out[0]['input']} -> Expected: {held_out[0]['output']}")
    print(f"Baseline exact fit: {baseline['exact_fit']}")
    print(f"Library exact fit: {reused['exact_fit']}; held-out exact: {all(mask)}")
    print(f"Charged search calls: baseline={baseline['calls']}, library={reused['calls']}")
    print(f"Acquisition calls: {fees['calls']} (not included in search calls)")
    if baseline["exact_fit"] or not reused["exact_fit"] or not all(mask):
        raise RuntimeError("Demo did not produce the expected behavior")


if __name__ == "__main__":
    main()
