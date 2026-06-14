# Scenario Format & Dataset Guide

> Authoritative format reference for `data/scenarios.json` plus practical
> guidance on building high-quality eval datasets.

---

## File Format

`data/scenarios.json` is a **JSON array** of scenario objects.

```json
[
  {
    "id": "unique-scenario-id",
    "input": "string or {\"key\": \"value\"}",
    "expected_behavior": "string (optional)",
    "context": "string (optional)",
    "metadata": {}
  }
]
```

---

## Field Reference

| Field | Type | Required | Aliases | Description |
|---|---|---|---|---|
| `id` | string | Yes | `scenario_id` | Unique identifier. Must be unique within the file. Referenced in all run output files. |
| `input` | string or object | Yes | — | The input passed to the model. String is injected via `{{input}}` in the prompt. Dict is JSON-serialized first. |
| `expected_behavior` | string | No | `expected` | The ideal or expected model response. Required by most judges for scoring. |
| `context` | string | No | — | Supporting context for the response (e.g., retrieved documents). Required by `deepeval.faithfulness` and `deepeval.contextual_relevancy`. |
| `metadata` | object | No | — | Arbitrary key-value data. Passed through to output records and judge context. Useful for test grouping, source tracking, or template variables. |

### Dict input format

When `input` is a dict, the judge test case also reads special keys:

| Key in `input` dict | Used by |
|---|---|
| `text` or `query` | Extracted as the primary input string for the judge test case |
| `context` | Mapped to DeepEval `context` (list of one string) |
| `retrieval_context` | Mapped to DeepEval `retrieval_context` (for hallucination checks) |

---

## Fields Required Per Judge Type

Different judges need different scenario fields populated. Failing to provide
them causes a `MissingTestCaseParamsError` at run time.

| Judge type | `input` | `expected_behavior` | `context` | `retrieval_context` | `actual_field` |
|---|---|---|---|---|---|
| `deepeval.geval` | Required | Recommended | — | — | — |
| `deepeval.answer_relevancy` | Required | — | — | — | — |
| `deepeval.contextual_relevancy` | Required | — | Required | — | — |
| `deepeval.faithfulness` | Required | — | Required | — | — |
| `deepeval.hallucination` | Required | — | — | Required | — |
| `deepeval.contextual_precision` | Required | Required | — | Required | — |
| `deepeval.contextual_recall` | Required | Required | — | Required | — |
| `deepeval.toxicity` | Required | — | — | — | — |
| `deepeval.conversation_completeness` | Required | — | — | — | — |
| `deepeval.conversational_geval` | Required | — | — | — | — |
| `deepeval.turn_relevancy` | Required | — | — | — | — |
| `classifier` | Required | — | — | — | Required |
| `regression` | Required | — | — | — | Required (numeric) |

**`actual_field`**: For deterministic judges, the ground-truth value is resolved
from the scenario via `config.actual_field` (default: `"actual"`). It is read
from `scenario.input` dict keys first, then top-level scenario fields.

**Providing `context` / `retrieval_context`**: Put these in the `input` dict:
```json
{
  "id": "rag-001",
  "input": {
    "query": "What is the refund policy?",
    "retrieval_context": ["Our refund policy allows returns within 30 days..."]
  },
  "expected_behavior": "The refund window is 30 days."
}
```

---

## Dataset Quality Principles

### Coverage

- **Happy path**: Normal, well-formed inputs the model should handle easily.
- **Edge cases**: Boundary conditions — very short inputs, very long inputs, ambiguous phrasing.
- **Adversarial**: Inputs designed to confuse, misuse, or expose failure modes (e.g., prompt injection attempts, off-topic requests, contradictory context).
- **Domain breadth**: Cover the full range of topics, tones, and user types the production system will encounter.

### Volume guidelines

| Eval maturity | Scenario count | Purpose |
|---|---|---|
| Smoke test | 5–20 | Quick sanity check during development |
| Development eval | 50–200 | Representative coverage for iteration |
| Production eval | 200–1000+ | Statistically reliable pass rates |

More is not always better — 100 high-quality, diverse scenarios outperform 1000 near-duplicate ones.

### `expected_behavior` quality

- Write what the model **should do**, not a verbatim expected output.
- Be specific enough to be measurable: "The response should acknowledge the request, provide the refund policy (30 days), and offer a next step."
- Avoid vague criteria like "respond helpfully" — judges cannot score against these reliably.
- For `deepeval.geval`, `expected_behavior` feeds into custom criteria matching, so align its content with your `criteria` and `evaluation_steps`.

### ID conventions

- Use readable, stable IDs: `"refund-policy-001"`, `"edge-empty-input"`, `"adversarial-prompt-inject-01"`.
- IDs appear in all output files — good names make debugging much faster.
- Never reuse an ID across scenarios. Gavel validates uniqueness and will reject duplicate IDs.

### Metadata best practices

Use `metadata` for grouping and filtering, not for judge-visible content:
```json
{
  "metadata": {
    "category": "refund",
    "difficulty": "hard",
    "source": "production-logs-2026-03",
    "jira": "EVL-42"
  }
}
```

This lets you filter runs by category in post-processing without affecting judge scores.

### Building from production data

1. Export real user inputs from logs (anonymize PII first).
2. Sample representatively across query types, not just the most frequent.
3. Have a human label `expected_behavior` for each sampled scenario — do not generate these with the same model you are evaluating.
4. Seed with known failure cases: past incidents, bug reports, user complaints.

### Iterating on scenarios

- After each run, read `runs/{run_id}/results_judged.jsonl` and look at the `judges[].reasoning` for failed scenarios.
- If many failures share a pattern, add more scenarios that cover that pattern.
- Remove scenarios that are always-pass (they provide no signal) or are testing the wrong thing.
- Track scenario changes in git — scenario drift is a common source of unexplained metric changes.

---

## Validation Checklist

Before running an eval, verify:

- [ ] All `id` values are unique
- [ ] All scenarios have non-empty `input`
- [ ] Scenarios used with faithfulness/contextual_relevancy have `context`
- [ ] Scenarios used with hallucination have `retrieval_context` in `input` dict
- [ ] `expected_behavior` is present and specific for judges that need it
- [ ] The file is valid JSON (no trailing commas, no comments)
