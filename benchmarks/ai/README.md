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
request size, parse success, bounded failure codes, finding counts, and conflict counts. It omits
credentials, raw snapshots, review prose, and error text. The runner fixes
fixture entity/task IDs so all providers receive the same snapshot for a case.
Each role records `response_mode` (`schema`, `prompt`, or `prompt_fallback`),
and the run records `application_dirty` alongside its commit. Older records
without a mode are grouped as `unspecified`. A fallback means the local server
explicitly rejected the schema request; compare it separately from schema runs.
Failure codes distinguish provider errors, invalid JSON/schema, oversized
responses, out-of-scope entity IDs, and duplicate findings. Older records
without a failure code are summarized as `unclassified`.
`tokens` and `quality_score` remain `null`: the current provider adapter does
not return usage, and valid JSON is not a quality score. Human review of the
findings and real-provider samples are still required before claiming quality
or token improvements. A partial file after an interrupted run contains only
cases completed before the interruption; inspect its sample count.

On 2026-10-06, an opt-in local baseline with `llama3.2:latest` for structure
and `qwen2.5-coder:1.5b` for requirements completed 0/3 cases (three public
fixtures, six requests). A diagnostic repeat also completed 0/3: the
requirements role produced two invalid-schema responses and one out-of-scope
entity reference; the structure role produced one out-of-scope entity reference.
The empty-model case failed both roles again after its prompt explicitly said
to return no findings for an empty entity array. These small, nondeterministic
local runs are reliability evidence for those exact model choices, not a
cross-provider quality comparison. Raw local JSONL remains outside the repo;
tokens and review quality were not measured.

The next slice requests a snapshot-specific JSON schema for local specialist
reviews. It constrains topic/verdict values and entity IDs; an empty snapshot
sets `findings.maxItems` to zero. The existing parser still rejects invalid or
duplicate findings. Servers that explicitly reject `response_format` with
HTTP 400/422 get one prompt-only fallback; unrelated failures do not retry.
Ordinary Assistant chat and cloud specialist requests retain their earlier
wire format. On committed `5f6215f` (`application_dirty=false`), the same
local model pairing completed 3/3 cases with schema mode for both roles:
overall latency p50 19,212 ms and p95 30,747 ms. This is a single three-case
run, so neither a statistical performance claim nor an assessment of finding
quality. Tokens and quality scores remain `null`.
