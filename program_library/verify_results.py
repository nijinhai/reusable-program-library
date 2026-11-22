"""Compare a fresh benchmark run with the archived per-task reference."""
import argparse
import csv
from pathlib import Path


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    reference = Path(__file__).resolve().parent.parent / "results" / "reference"
    for name in ("summary.csv", "categories.csv", "sources.csv", "birth.csv", "costs.csv", "task_results.csv"):
        actual = rows(args.output / name)
        expected = rows(reference / name)
        if actual != expected:
            raise SystemExit(f"Mismatch: {name}")
        print(f"MATCH {name}: {len(actual)} rows")
    print("All 468 strategy/task records and aggregate tables match the archived experiment.")


if __name__ == "__main__":
    main()
