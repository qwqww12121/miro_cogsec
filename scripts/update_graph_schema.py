"""输出 CogSec-MiroFish 图谱扩展 schema。"""

from __future__ import annotations

from pathlib import Path
import sys


GRAPH_SCHEMA_CYPHER = """// CogSec-MiroFish graph extension
CREATE (:User {id: $id, name: $name, profile_vector: $profile_vector});
CREATE (:Adversary {id: $id, type: $type, strategy_library: $strategy_library});
CREATE (:DecisionNode {id: $id, timestamp: $timestamp, reversibility: $reversibility});
CREATE (:EvidenceItem {id: $id, cialdini_principle: $cialdini_principle});

MATCH (u:User {id: $user_id}), (a:Adversary {id: $adversary_id})
MERGE (u)-[:TRUST_IN {level: $trust_level}]->(a)
MERGE (u)-[:PRESSURED_BY {intensity: $pressure_intensity}]->(a);

MATCH (d1:DecisionNode {id: $decision_from}), (d2:DecisionNode {id: $decision_to})
MERGE (d1)-[:COUNTERFACTUAL_BRANCH {branch_id: $branch_id}]->(d2)
MERGE (d1)-[:ESCALATES_TO {probability: $probability}]->(d2);

MATCH (t:Adversary {id: $adversary_id}), (asset:EvidenceItem {id: $asset_id})
MERGE (t)-[:THREATENS_ASSET {impact: $impact}]->(asset);
"""


def write_schema(target_path: Path) -> Path:
    """将 schema 写入目标文件。"""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(GRAPH_SCHEMA_CYPHER, encoding="utf-8")
    return target_path


def main() -> int:
    """CLI 入口。"""
    if "--print" in sys.argv:
        print(GRAPH_SCHEMA_CYPHER)
        return 0

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/cogsec_graph_schema.cypher")
    path = write_schema(target)
    print(f"Cypher schema 已写入: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
