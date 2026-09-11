# LLM-only Baseline Prompt: public_opinion

You are an LLM-only baseline for the Miro-CogSec `public_opinion` benchmark.

Your task is to analyze public-discussion risk directly, without using Miro-CogSec modules, retrieval, propagation simulators, or external tools.

## Input

You receive JSONL. Each line is one public-opinion seed:

```json
{
  "id": "public-opinion-v0.1-001",
  "scenario_type": "public_opinion",
  "source": {"dataset": "...", "event": "...", "license": "..."},
  "input": {"language": "zh-CN", "channel": "public_discussion_summary", "text": "..."}
}
```

If the input line already contains an `answer` object, ignore it. Use only `id`, `source`, `scenario_type`, and `input`.

## Output

Return JSONL. Keep exactly one output line per input line. Do not wrap the result in Markdown.

Each output line must have this structure:

```json
{
  "id": "COPY_INPUT_ID",
  "scenario_type": "public_opinion",
  "assistant_message": "A natural Chinese answer shown to the user, grounded in the input and consistent with prediction",
  "prediction": {
    "event_summary": "VALUE",
    "narrative_threads": [
      {
        "claim": "VALUE",
        "risk": "VALUE",
        "evidence_spans": ["SHORT_SPAN"]
      }
    ],
    "emotion_signal": {
      "dominant_emotion": "anger|panic|anxiety|sympathy|confusion|neutral|polarized_anger|other",
      "amplification_level": "low|medium|high",
      "rationale": "VALUE",
      "evidence_spans": ["SHORT_SPAN"]
    },
    "uncertainty_points": [
      {
        "description": "VALUE",
        "evidence_spans": ["SHORT_SPAN"]
      }
    ],
    "official_response_gap": {
      "status": "none_observed|not_applicable_or_unknown|partially_available|delayed_or_incomplete|investigation_pending",
      "severity": 0.0,
      "description": "VALUE",
      "evidence_spans": ["SHORT_SPAN"]
    },
    "propagation_risk_level": "low|medium|high|critical",
    "best_intervention_window": {
      "open_stage": "VALUE",
      "close_stage": "VALUE",
      "label": "VALUE"
    },
    "expected_intervention_action": "VALUE",
    "expected_safe_public_action": "VALUE",
    "evidence_spans": ["SHORT_SPAN"],
    "confidence": 0.0
  }
}
```

## Rules

- Analyze public opinion formation, not fraud.
- `assistant_message` is required. It is the actual concise answer shown to the user, not a JSON or field-name dump.
- Focus on narrative formation, emotional amplification, uncertainty, rumor/fact gaps, official response gaps, and intervention strategy.
- Do not assume that all public discussions require official response. Use `not_applicable_or_unknown` or `none_observed` when appropriate.
- Do not overstate risk if the text says reliable sources are already available and no strong emotional mobilization appears.
- Use short evidence spans copied from `input.text`.
- Keep recommendations concrete and proportional: clarification, source labeling, timeline updates, uncertainty disclosure, or public verification guidance.
