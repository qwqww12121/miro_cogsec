# ROLE REPORTERS — Round 5

## Why role-specific reports

The existing `CounterfactualReporter` (`cf_reporter.py`) generates a single,
one-size-fits-all report that mixes forensic evidence, risk scores, and
intervention advice.  Different audiences need different presentations:

| Role | Audience | Focus |
|---|---|---|
| `individual` | Personal user | Self-protection, copyable responses, next steps |
| `official` | Institution/gov | Key nodes, Fork A/B comparison, cross-department coordination |
| `media` | Journalist | Timeline, confirmed vs. unverified facts, harm avoidance |
| `target_group` | Affected community | Group solidarity, verification checklist, internal communication |

The role reporter layer is **post-hoc**: it reads the existing
`CogSecAnalysisResult` dict and renders role-specific Markdown without
modifying `cf_reporter.py`.

## Relationship with cf_reporter.py

`cf_reporter.py` generates the `counterfactual_report` field inside
`CogSecAnalysisResult`.  The role reporters consume that field (plus
`scenario_extension.propagation`, `metrics`, `fork_comparison`, etc.)
but never modify it.  This is purely a **rendering layer**.

## RoleReportPayload structure

```python
@dataclass
class RoleReportPayload:
    scenario_type: str
    user_role: str
    source_result: Dict      # the full CogSecAnalysisResult dict
    risk_scores: Dict        # {final_risk, trajectory_gap, irreversibility_loss, evidence_consistency}
    key_findings: List[Dict] # [{title, evidence, severity}]
    fork_comparison: Dict    # from result.fork_comparison
    propagation: Dict | None # from result.scenario_extension.propagation
    timeline: List[Dict]     # from branch_a_log/branch_b_log + propagation coverage_curve
    metadata: Dict
```

## role_report output structure

```python
@dataclass
class RenderedRoleReport:
    role: str
    title: str
    markdown: str            # ready-to-render Markdown
    sections: List[Dict]     # [{heading, content}]
    structured: Dict         # role-specific structured data
```

## How it integrates

`CogSecService.analyze_text()` now:
1. Builds the full `CogSecAnalysisResult` (including `scenario_extension` from Round 4).
2. Converts it to `dict` via `.to_dict()`.
3. Calls `render_role_report(result_dict, user_role, canonical)`.
4. Stores the rendered output in `analysis_result.role_report`.
5. On failure, stores `{"error": ..., "role": ...}` — never crashes the mainline.

## Current limitations

- Template-based: no LLM polish.  Language is structured but not personalised.
- No frontend integration yet.
- `individual` and `target_group` sections use generalised language that
  would benefit from LLM-based personalisation in a future round.
- Does not modify `cf_reporter.py` output — both `counterfactual_report`
  and `role_report` exist side by side.

## Future extensions

1. Add an optional LLM polishing pass via the existing `LLMClient`.
2. Add a `system_operator` role for dev/admin use.
3. Add localisation/i18n support for non-Chinese audiences.
