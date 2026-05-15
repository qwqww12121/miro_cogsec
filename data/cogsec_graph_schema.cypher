// CogSec-MiroFish graph extension
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
