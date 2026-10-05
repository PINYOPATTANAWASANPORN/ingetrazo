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

## Read-only specialist review benchmark

`review-corpus-v1.json` has three public, metadata-only fixtures. Its runner
uses the same task snapshot and two-specialist review functions as the
Assistant. Validate fixtures without contacting any provider:

```powershell
python scripts/ai_review_benchmark.py
```

To run actual requests, create a local JSON config with **model names and
environment-variable names only**. Never put API keys in the config:

```json
{
  "schema_version": "1.0",
  "roles": {
    "model_structure": {
      "provider": "ollama", "model": "your-installed-model"
    },
    "task_requirements": {
      "provider": "openai", "model": "your-selected-model",
      "key_env": "OPENAI_API_KEY"
    }
  }
}
```

Use only providers and models you intend to contact. Each `--run` sends each
public fixture to both configured providers and writes a new JSONL file;
existing files are never overwritten:

```powershell
python scripts/ai_review_benchmark.py --run --config path/to/providers.json `
  --output path/to/review-run.jsonl
python scripts/ai_review_benchmark.py --results path/to/review-run.jsonl
```

The JSONL contains only case IDs, provider/model labels, measured elapsed time,
request size, parse success, finding counts, and conflict counts. It omits
credentials, raw snapshots, review prose, and error text. The runner fixes
fixture entity/task IDs so all providers receive the same snapshot for a case.
`tokens` and `quality_score` remain `null`: the current provider adapter does
not return usage, and valid JSON is not a quality score. Human review of the
findings and real-provider samples are still required before claiming quality
or token improvements. A partial file after an interrupted run contains only
cases completed before the interruption; inspect its sample count.
