# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the AI corpus and aggregate optional JSONL run records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.ai_eval import summarize_results, validate_corpus


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path,
                        default=ROOT / "benchmarks/ai/task-corpus-v1.json")
    parser.add_argument("--results", type=Path,
                        help="JSONL measurements to aggregate")
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    cases = validate_corpus(data)
    records = []
    if args.results:
        records = [json.loads(line) for line in
                   args.results.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    print(json.dumps(summarize_results(cases, records), indent=2,
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
