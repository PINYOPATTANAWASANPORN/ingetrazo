# Read-only specialist review

In the AI Assistant, enable **Review with 2 specialists (read-only)**, choose
the scope and enter a short request. Two independent requests share one
snapshot: `model_structure` reviews organisation, naming, tags
and material metadata; `task_requirements` reviews the request, constraints,
assumptions and explicit project memory against that metadata.

Open **Specialist connections…** in the connection section to choose a provider
and model for each role. **Same as Assistant** uses the current connection.
Another provider uses the API key already saved in its main connection settings;
the UI rejects a missing key before sending either request. Blank role models
use the current model on the main provider, or that other provider's saved or
default model. Role choices are saved, but credentials are not copied to role
settings or reports. The report
records the requested provider/model for each role, including failed requests.
These identifiers describe the request, not an attestation of server-side routing.
Unknown model names produce a visible role failure; no automatic fallback hides it.

This is provider-backed parallel execution, not a local rule-based checker.
Choosing different model names does not imply independent
model expertise, and no live-provider quality or latency benchmark has been
recorded. Tests use deterministic fake provider responses.

## Data and authority

The GUI thread captures one detached JSON snapshot tied to the task's content
revision and a SHA-256 snapshot ID. At most 200 scoped entities and 64 KiB of
UTF-8 JSON are accepted; oversize scopes fail with a narrowing message.
Names, tags, material names, visibility/lock flags, child and face/edge counts
are included. Vertex geometry, images, textures, file paths and credentials
are not part of the snapshot. Only the explicit provider call receives its
configured credential. Metadata is not evidence of structural safety, code
compliance, dimensions or geometric correctness.

Each worker receives the same serialized snapshot and its own cancellation
token, with a 1500-token response budget. No scene object, recipe executor or
write tool is supplied. Responses accept only a summary and bounded findings:
`entity_id`, `topic`, `verdict`, `evidence`. Findings must reference snapshot
entities; code, action objects, unknown IDs and malformed responses fail
validation. Summary text is advisory and is never executed.

The coordinator retains both role reports. A `clear`/`concern` disagreement
on the same entity/topic is shown as an unresolved conflict; it does not
choose a winner or produce a mutation. One failed role produces `partial`,
both failures produce `failed`; neither becomes a clean bill of health.

Before displaying a result, the GUI rechecks document identity and content
revision. Stale findings are discarded. Cancel closes both active responses
and invalidates the generation so late messages cannot appear or execute.
Review leaves document history and persistent project memory untouched.
Results are kept in the Assistant's session task record. Review mode is
session-only and preserves the user's ordinary goal/execution preferences.

## Delivery boundary

The Assistant dispatches provider requests itself. MCP also provides an
external coordination protocol, advertised as `external_specialist_review`.
`multi_agent` remains false for general autonomous modeler orchestration.
Persistent signed audit, geometry evidence and coordinator-approved modeler
proposals remain future work.

## External MCP workflow

1. Call `create_task` with `execution: "analysis_only"` and the intended scope.
2. Call `begin_specialist_review` with that `task_id`. It returns a `review_id`,
   bounded detached `snapshot`, its `snapshot_id`, and two `assignments`.
   Each assignment includes a role, instructions and `submission_token`.
3. The external coordinator runs its own specialists, optionally in parallel.
   Give each the same snapshot and only its own assignment. IngeTrazo does not
   launch a provider call or access the Assistant's credentials through MCP.
4. Call `submit_specialist_review` for each role with `review_id`, `role`,
   `submission_token`, `snapshot_id`, and `result`. A successful result is
   `{summary, findings: [{entity_id, topic, verdict, evidence}]}`; a provider
   failure is `{error: "reason"}`. Summary is limited to 1000 characters,
   evidence to 500, error to 300, and each role to 20 unique entity/topic findings.
5. `get_specialist_review` returns submission progress and the combined report
   after both roles submit. Matching retries are idempotent; a changed second
   submission for the same role is a conflict. Tokens never appear in this
   getter, task reports or activity metadata.

All tools require the existing bridge session authentication. Role tokens
bind a result to a role and snapshot; they do **not** authenticate distinct
agent identities. The authenticated coordinator receives both tokens and is
trusted to dispatch honestly. A repeated begin for the same collecting task
returns the same assignment, so it is not an access-control boundary between
clients sharing bridge credentials.

Document changes invalidate pending and completed reports on retrieval or
submission. `get_task` also refreshes the associated review state. Stale results
are cleared, and new work requires a new task. `cancel_specialist_review`
rejects late submissions but cannot stop a provider outside IngeTrazo; the
external coordinator must cancel that request itself. Session restart clears
review state and tokens. At most 8 reviews may collect simultaneously; at most
64 are retained, evicting the oldest terminal review when needed.

No review operation changes model content, history, or persistent memory.
Malformed or out-of-scope findings are rejected rather than executed, and
structured failures set MCP `isError` so clients can recover correctly.

Validation: `tests/test_ai_review.py` covers concurrent dispatch, identical
snapshots, scope/revision bounds, conflicting findings, partial failures,
malformed/action responses and cancellation of both requests.
`tests/test_ai_assistant.py` exercises read-only UI flow and stale/cancelled
result rejection. Provider credentials and real network calls are not needed
for these tests.


## Review export (2026-10-05)

Finished current-revision reviews can be exported with Assistant **Export review…**
or MCP `export_specialist_review(review_id)`. MCP returns data only; the caller
chooses whether and where to save it. Assistant writes UTF-8 JSON atomically via
QSaveFile and rechecks document/task identity and revision after the save dialog.
Completed, partial and failed two-role outcomes are retained; unfinished,
cancelled and stale reviews cannot be exported. Export does not modify geometry
or Undo history.

Schema 1.0 includes UTC export time, revision, snapshot digest, role outcomes,
requested provider/model labels when available, findings and unresolved conflicts.
Only allowlisted report fields are serialized: connection settings, API keys,
submission tokens, raw snapshots and project-memory records are excluded.
Reviewer prose is included and can contain project-sensitive information; this
is not a general-purpose secret redactor. External roles may have no model label.

`integrity.payload_digest` is SHA-256 over UTF-8 JSON of `payload` with sorted
keys, no ASCII escaping, compact comma/colon separators and no NaN values
(Python `json.dumps(..., ensure_ascii=False, sort_keys=True,
separators=(",", ":"), allow_nan=False)`). It is an unsigned corruption check,
not proof of authorship or a tamper-proof audit trail. Reports are advisory
metadata checks, not geometric validation or regulatory certification.

## Session review history (2026-10-05)

`get_review_audit(after_sequence, limit)` returns pages of status events for
completed, partial, failed, cancelled and stale **recorded reports**. Identical
retries append no extra event. Each event contains sequence, UTC time, task ID,
base revision, snapshot ID, status, SHA-256 digest of the recorded report and
the previous event's digest. It contains no review prose, credentials, raw
snapshot or role tokens. The first previous digest is 64 zeroes. Recompute an
event digest over the event without its `digest` field using the canonical JSON
rule above. The response includes the current `head_digest`, total count and
`has_more`; callers can page forward with `next_sequence` (1–100 per call).

This history is in memory for the current document and bridge/Assistant task
service. It resets when that service or document is replaced. The full report
must be exported separately while its revision is current. SHA-256 links reveal
accidental changes to a captured chain but do not prove who ran a provider or
prevent an actor with access to the process from replacing the chain.

### Explicit history file

Assistant **Export review history…** saves the complete current session trail
as UTF-8 JSON with an atomic file replacement. The user chooses the file path;
the program does not silently persist review history in a model or profile.
The export is limited to 10,000 events or 16 MiB of canonical payload. Larger
histories remain available page by page through MCP. **Verify history file…**
checks a saved file independently of the live scene. It checks schema, event
count and order, each previous digest, each event digest, the head digest and
the outer payload checksum. Verification rejects files over the input size
limit. It does not import events into the current scene.

The file survives a session restart, but it is an unsigned user-held copy.
Someone who can rewrite the whole file can recompute every checksum. Do not
interpret successful verification as proof of provider identity or authorship.

Next: authenticated signatures or an independently anchored audit store,
provider compatibility and real token baselines.
