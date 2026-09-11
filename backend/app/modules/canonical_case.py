"""Small provenance-aware canonical case layer.

``CanonicalCase`` is an internal bridge between input normalization,
CognitiveProfile, and the existing SocialState schema.  It intentionally does
not model a second full social graph: actors here carry stable identity and
provenance, while dynamic behaviour remains in ``ActorState``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import uuid
from typing import Any, Dict, Iterable, List, Optional


VALID_PROVENANCE = frozenset({"observed", "inferred", "synthetic"})


@dataclass
class EvidenceItem:
    evidence_id: str
    content: str
    source_type: str = "text"
    source_ref: Optional[str] = None
    timestamp: Optional[str] = None
    actor_hint: Optional[str] = None
    confidence: float = 1.0
    provenance: str = "observed"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.provenance not in VALID_PROVENANCE:
            raise ValueError(f"Invalid evidence provenance: {self.provenance}")
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InputPackage:
    """Normalized internal input; users still submit text/fragments/files."""

    primary_text: str
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    explicit_scenario: Optional[str] = None

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        explicit_scenario: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "InputPackage":
        return cls.from_fragments(
            primary_text=text,
            fragments=[{"content": text, "source": "chat", "role": "user"}],
            explicit_scenario=explicit_scenario,
            metadata=metadata,
        )

    @classmethod
    def from_fragments(
        cls,
        primary_text: str,
        fragments: Iterable[Any],
        *,
        explicit_scenario: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "InputPackage":
        evidence_items: List[EvidenceItem] = []
        for index, fragment in enumerate(fragments, start=1):
            if isinstance(fragment, EvidenceItem):
                evidence_items.append(fragment)
                continue
            item = dict(fragment) if isinstance(fragment, dict) else {
                "content": str(fragment),
            }
            content = str(item.get("content", "") or "")
            if not content:
                continue
            fragment_id = item.get("fragment_id") or item.get("evidence_id")
            evidence_id = str(fragment_id or f"EVIDENCE_{index:03d}")
            source = str(item.get("source_type") or item.get("source") or item.get("kind") or "text")
            provenance = str(item.get("provenance") or "observed")
            evidence_items.append(EvidenceItem(
                evidence_id=evidence_id,
                content=content,
                source_type=source,
                source_ref=item.get("source_ref") or item.get("filename"),
                timestamp=_string_or_none(item.get("timestamp")),
                actor_hint=item.get("actor_hint"),
                confidence=item.get("confidence", 1.0),
                provenance=provenance if provenance in VALID_PROVENANCE else "observed",
                metadata=dict(item.get("metadata") or {}),
            ))
        if not evidence_items and primary_text:
            evidence_items.append(EvidenceItem(
                evidence_id="EVIDENCE_001",
                content=primary_text,
                source_type="text",
            ))
        return cls(
            primary_text=primary_text or "",
            evidence_items=evidence_items,
            metadata=dict(metadata or {}),
            explicit_scenario=explicit_scenario,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["evidence_items"] = [item.to_dict() for item in self.evidence_items]
        return payload


@dataclass
class CanonicalActor:
    actor_id: str
    role: str
    display_name: str = ""
    provenance: str = "observed"
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.provenance not in VALID_PROVENANCE:
            raise ValueError(f"Invalid actor provenance: {self.provenance}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalClaim:
    claim_id: str
    text: str
    status: str = "reported"
    provenance: str = "observed"
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalRelation:
    relation_id: str
    source_actor_id: str
    target_actor_id: str
    relation_type: str = "information_flow"
    provenance: str = "inferred"
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimelineEvent:
    event_id: str
    description: str
    timestamp: Optional[str] = None
    provenance: str = "observed"
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalCase:
    case_id: str
    scenario_type: str
    scenario_confidence: float
    summary: str
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    actors: List[CanonicalActor] = field(default_factory=list)
    claims: List[CanonicalClaim] = field(default_factory=list)
    relations: List[CanonicalRelation] = field(default_factory=list)
    timeline: List[TimelineEvent] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    cognitive_profile: Optional[Any] = None
    simulation_state_id: Optional[str] = None

    def to_dict(self, include_profile: bool = False) -> Dict[str, Any]:
        payload = {
            "case_id": self.case_id,
            "scenario_type": self.scenario_type,
            "scenario_confidence": self.scenario_confidence,
            "summary": self.summary,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
            "actors": [actor.to_dict() for actor in self.actors],
            "claims": [claim.to_dict() for claim in self.claims],
            "relations": [relation.to_dict() for relation in self.relations],
            "timeline": [event.to_dict() for event in self.timeline],
            "missing_information": list(self.missing_information),
            "provenance": dict(self.provenance),
            "simulation_state_id": self.simulation_state_id,
        }
        if include_profile and self.cognitive_profile is not None:
            profile = self.cognitive_profile
            payload["cognitive_profile"] = profile.to_dict() if hasattr(profile, "to_dict") else str(profile)
        return payload


def build_canonical_case(
    input_package: InputPackage,
    *,
    scenario_type: str,
    scenario_confidence: float = 0.0,
    cognitive_profile: Any = None,
    case_id: Optional[str] = None,
) -> CanonicalCase:
    """Build stable observed identities and lightweight case semantics."""
    from .social_state.builder import extract_actors_from_text

    evidence_items = list(input_package.evidence_items)
    summary = input_package.primary_text or "\n".join(item.content for item in evidence_items)
    extraction_text = "\n".join(item.content for item in evidence_items) or summary
    extracted = extract_actors_from_text(
        extraction_text,
        max_actors=100,
        scenario_type=scenario_type,
    )
    actors: List[CanonicalActor] = []
    for index, actor in enumerate(extracted, start=1):
        refs = [item.evidence_id for item in evidence_items if _actor_text_present(actor, item.content)]
        if not refs and evidence_items:
            refs = [evidence_items[0].evidence_id]
        actors.append(CanonicalActor(
            actor_id=f"ACTOR_{index:03d}",
            role=actor.role,
            display_name=actor.display_name,
            provenance="observed",
            evidence_refs=refs,
            metadata={"extraction": "role_keyword_rule"},
        ))

    claims = _build_claims(evidence_items, extraction_text)
    relations = _build_relations(actors, evidence_items)
    timeline = _build_timeline(evidence_items)
    missing = _missing_information(scenario_type, evidence_items, actors, claims, timeline)
    observed_evidence = sum(item.provenance == "observed" for item in evidence_items)
    inferred_evidence = sum(item.provenance == "inferred" for item in evidence_items)
    synthetic_evidence = sum(item.provenance == "synthetic" for item in evidence_items)
    grounding_level = _grounding_level(
        observed_evidence=observed_evidence,
        observed_actor_count=len(actors),
        timeline_count=len(timeline),
        claim_count=len(claims),
        relation_count=len(relations),
    )
    provenance = {
        "grounding_level": grounding_level,
        "evidence_item_count": len(evidence_items),
        "observed_evidence_count": observed_evidence,
        "inferred_evidence_count": inferred_evidence,
        "synthetic_evidence_count": synthetic_evidence,
        "observed_actor_count": len(actors),
        "inferred_actor_count": 0,
        "synthetic_actor_count": 0,
        "shared_simulation_state": False,
        "case_source": "normalized_input_package",
    }
    return CanonicalCase(
        case_id=case_id or f"CASE_{uuid.uuid4().hex[:12].upper()}",
        scenario_type=scenario_type,
        scenario_confidence=max(0.0, min(1.0, float(scenario_confidence))),
        summary=summary,
        evidence_items=evidence_items,
        actors=actors,
        claims=claims,
        relations=relations,
        timeline=timeline,
        missing_information=missing,
        provenance=provenance,
        cognitive_profile=cognitive_profile,
    )


def _actor_text_present(actor: Any, text: str) -> bool:
    return bool(text and (actor.display_name in text or actor.role in text))


def _build_claims(evidence_items: List[EvidenceItem], text: str) -> List[CanonicalClaim]:
    markers = ("称", "表示", "指出", "声称", "发布", "宣称", "曝光", "质疑", "回应")
    claims: List[CanonicalClaim] = []
    for item in evidence_items:
        for marker in markers:
            if marker in item.content:
                index = item.content.find(marker)
                snippet = item.content[max(0, index - 30): index + 100].strip()
                claims.append(CanonicalClaim(
                    claim_id=f"CLAIM_{len(claims) + 1:03d}",
                    text=snippet,
                    provenance=item.provenance if item.provenance in VALID_PROVENANCE else "observed",
                    evidence_refs=[item.evidence_id],
                ))
                break
        if len(claims) >= 10:
            break
    if not claims and text:
        first = evidence_items[0].evidence_id if evidence_items else "EVIDENCE_001"
        claims.append(CanonicalClaim(
            claim_id="CLAIM_001",
            text=text[:160] + ("..." if len(text) > 160 else ""),
            evidence_refs=[first],
        ))
    return claims


def _build_timeline(evidence_items: List[EvidenceItem]) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []
    for item in evidence_items:
        if item.timestamp is not None:
            events.append(TimelineEvent(
                event_id=f"TIME_{len(events) + 1:03d}",
                description=item.content[:180],
                timestamp=item.timestamp,
                provenance=item.provenance,
                evidence_refs=[item.evidence_id],
            ))
    return events


def _build_relations(
    actors: List[CanonicalActor],
    evidence_items: List[EvidenceItem],
) -> List[CanonicalRelation]:
    """Add only a minimal inferred information-flow relation."""
    if len(actors) < 2:
        return []
    refs = [item.evidence_id for item in evidence_items[:2]]
    return [CanonicalRelation(
        relation_id="REL_001",
        source_actor_id=actors[0].actor_id,
        target_actor_id=actors[1].actor_id,
        relation_type="information_flow",
        provenance="inferred",
        evidence_refs=refs,
    )]


def _missing_information(
    scenario_type: str,
    evidence_items: List[EvidenceItem],
    actors: List[CanonicalActor],
    claims: List[CanonicalClaim],
    timeline: List[TimelineEvent],
) -> List[str]:
    missing: List[str] = []
    if not evidence_items:
        missing.append("missing source material")
    if not actors:
        missing.append("unknown observed actors")
    if not timeline:
        missing.append("unknown response timing")
    if not claims:
        missing.append("unknown claim content")
    if scenario_type == "event_propagation" and not any(
        "首发" in item.content or "来源" in item.content for item in evidence_items
    ):
        missing.append("unknown original source")
    if scenario_type in {"public_opinion", "event_propagation"} and not any(
        "官方" in item.content or "回应" in item.content or "辟谣" in item.content
        for item in evidence_items
    ):
        missing.append("unknown official response")
    return missing


def _grounding_level(
    *,
    observed_evidence: int,
    observed_actor_count: int,
    timeline_count: int,
    claim_count: int,
    relation_count: int,
) -> str:
    if (
        observed_evidence >= 2
        and observed_actor_count >= 2
        and (timeline_count > 0 or relation_count > 0)
        and claim_count > 0
    ):
        return "G2"
    if observed_evidence > 1 or observed_actor_count > 0 or claim_count > 1:
        return "G1"
    return "G0"


def _string_or_none(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


__all__ = [
    "CanonicalActor",
    "CanonicalCase",
    "CanonicalClaim",
    "CanonicalRelation",
    "EvidenceItem",
    "InputPackage",
    "TimelineEvent",
    "build_canonical_case",
]
