from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from vectrion.vql import execute_vql, parse_vql


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--evidence", default=str(Path(__file__).resolve().parent / "data" / "evidence.csv"))
    args = p.parse_args()

    with open(args.evidence, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    q = parse_vql(args.query)
    out = execute_vql(q, rows)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
