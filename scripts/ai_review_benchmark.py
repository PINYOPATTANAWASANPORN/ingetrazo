# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate or run the metadata-only, read-only specialist review corpus."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import ai, ai_review
from core.ai_review_eval import (make_snapshot, review_digest, run_case,
                                 summarize_review_records, validate_review_corpus)
from core.ai_review_assessment import summarize_assessments

DEFAULT_CORPUS = ROOT / "benchmarks/ai/review-corpus-v1.json"
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def load_connections(path: Path) -> dict:
    """Resolve secrets from environment only; reject literal keys in config."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema_version", "roles"} \
            or data["schema_version"] != "1.0":
        raise ValueError("connection config must use schema 1.0 and roles")
    roles = data["roles"]
    if not isinstance(roles, dict) or set(roles) != set(ai_review.ROLES):
        raise ValueError("configure both specialist roles")
    resolved = {}
    for role in ai_review.ROLES:
        item = roles[role]
        if not isinstance(item, dict) or set(item) - {
                "provider", "model", "key_env", "ollama_url"}:
            raise ValueError("connection config contains unsupported fields")
        provider, model = item.get("provider"), item.get("model")
        if (not isinstance(provider, str) or provider not in ai.PROVIDERS or
                not isinstance(model, str) or not 1 <= len(model.strip()) <= 200):
            raise ValueError("provider and model must be explicit for each role")
        url = item.get("ollama_url", "http://localhost:11434")
        if not isinstance(url, str) or not 1 <= len(url) <= 2048:
            raise ValueError("invalid Ollama URL")
        if provider == "ollama":
            if "key_env" in item:
                raise ValueError("local Ollama does not use key_env")
            key = ""
        else:
            name = item.get("key_env")
            if not isinstance(name, str) or not ENV_NAME.fullmatch(name):
                raise ValueError("cloud providers require an environment key name")
            key = os.environ.get(name, "")
            if not key.strip():
                raise ValueError(f"required environment key is missing: {name}")
        resolved[role] = {"provider": provider, "model": model.strip(),
                          "key": key, "ollama_url": url}
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--run", action="store_true",
                        help="send these public fixtures to configured providers")
    parser.add_argument("--config", type=Path,
                        help="provider/model choices and environment key names")
    parser.add_argument("--output", type=Path,
                        help="new JSONL output path; existing files are not overwritten")
    parser.add_argument("--results", type=Path,
                        help="summarize an existing review JSONL file offline")
    parser.add_argument("--assessments", type=Path,
                        help="validate metadata-only human judgments against --results")
    parser.add_argument("--show-findings", action="store_true",
                        help="show public-fixture review prose on stderr for manual assessment")
    args = parser.parse_args(argv)
    if args.show_findings and not args.run:
        parser.error("--show-findings requires --run")
    if args.show_findings and args.corpus.resolve() != DEFAULT_CORPUS.resolve():
        parser.error("--show-findings is limited to the bundled public corpus")
    if args.assessments is not None and args.results is None:
        parser.error("--assessments requires --results")
    cases = validate_review_corpus(json.loads(args.corpus.read_text(encoding="utf-8")))
    if args.results is not None:
        if args.run:
            parser.error("--results and --run are separate operations")
        records = [json.loads(line) for line in
                   args.results.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        summary = summarize_review_records(cases, records)
        if args.assessments is not None:
            assessments = json.loads(args.assessments.read_text(encoding="utf-8"))
            if not isinstance(assessments, list):
                raise ValueError("assessments must be an array")
            summary["human_assessment"] = summarize_assessments(records, assessments)
        print(json.dumps(summary,
                         ensure_ascii=False, indent=2))
        return 0
    if not args.run:
        sizes = []
        for case in cases:
            packet = make_snapshot(case)
            sizes.append({"case_id": case["id"], "entities": len(packet["entities"])})
        print(json.dumps({"schema_version": "1.0", "cases": sizes,
                          "provider_calls": 0}, ensure_ascii=False, indent=2))
        return 0
    if args.config is None or args.output is None:
        parser.error("--run requires --config and --output")
    connections = load_connections(args.config)
    # Validate all fixtures before creating a result file or making a request.
    for case in cases:
        make_snapshot(case)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                     cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT, text=True).strip())
    run_id = uuid.uuid4().hex
    def show_findings(case_id, role, packet, result):
        # Explicit opt-in, public fixtures only. The benchmark JSONL stays prose-free.
        print(json.dumps({"run_id": run_id, "case_id": case_id,
                          "role": role, "snapshot": packet,
                          "review_digest": review_digest(result),
                          "summary": result["summary"],
                          "findings": result["findings"]},
                         ensure_ascii=False, indent=2), file=sys.stderr)

    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        for case in cases:
            result = run_case(case, connections,
                              review_callback=show_findings if args.show_findings else None)
            record = {
                "schema_version": "1.0", "run_id": run_id,
                "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "application_commit": commit,
                "application_dirty": dirty,
                "corpus": args.corpus.name,
                "platform": platform.platform(),
                **result,
            }
            output.write(json.dumps(record, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")) + "\n")
            output.flush()
    print(json.dumps({"run_id": run_id, "cases": len(cases),
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
