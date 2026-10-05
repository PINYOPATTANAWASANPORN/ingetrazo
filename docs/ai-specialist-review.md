# Read-only specialist review

In the AI Assistant, enable **Review with 2 specialists (read-only)**, choose
the scope and enter a short request. The selected provider/model receives two
independent requests: `model_structure` reviews organisation, naming, tags
and material metadata; `task_requirements` reviews the request, constraints,
assumptions and explicit project memory against that metadata.

This is provider-backed parallel execution, not a local rule-based checker.
Both roles currently use the same provider/model. It does not imply independent
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

This slice is available in the in-app Assistant. The bridge advertises
`assistant_specialist_review` separately; MCP has no specialist execution
endpoint yet, and `multi_agent` remains false for general MCP orchestration.
External specialist protocols, per-role model selection, audit export,
geometry evidence and coordinator-approved modeler proposals remain future
work. The existing single-writer preview/approval flow is unchanged.

Validation: `tests/test_ai_review.py` covers concurrent dispatch, identical
snapshots, scope/revision bounds, conflicting findings, partial failures,
malformed/action responses and cancellation of both requests.
`tests/test_ai_assistant.py` exercises read-only UI flow and stale/cancelled
result rejection. Provider credentials and real network calls are not needed
for these tests.
