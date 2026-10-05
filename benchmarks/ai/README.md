# AI evaluation corpus

`task-corpus-v1.json` is a fixed, privacy-safe request set. Run records are
JSONL and must include `case_id`, `provider`, `model`, `completed`, `tokens`,
`tool_calls`, `latency_ms`, `first_preview_ms`, `rollback_ok`, and
`manual_corrections`.

Validate the corpus without claiming performance results:

```powershell
python scripts/ai_eval.py
```

Aggregate a captured run:

```powershell
python scripts/ai_eval.py --results path/to/run.jsonl
```

The output reports completion and rollback rates, correction count, and p50/
p95 values. Empty metrics are `null`; a corpus file alone is a test plan, not
measured evidence. Keep fixture construction, provider/model, hardware, date,
and application commit beside every saved run.
