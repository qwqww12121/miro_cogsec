"""认知安全 persona 模板。"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Dict, List, Optional


SECURITY_PERSONA_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "victim_persona_template": {
        "name": "{{user_name}}",
        "role": "potential_victim",
        "scenario_type": "{{scenario_type}}",
        "cognitive_profile": "{{cognitive_profile_json}}",
        "big_five_traits": {
            "openness": "{{openness_score}}",
            "conscientiousness": "{{conscientiousness_score}}",
            "extraversion": "{{extraversion_score}}",
            "agreeableness": "{{agreeableness_score}}",
            "neuroticism": "{{neuroticism_score}}",
        },
        "system_prompt": (
            "You are simulating a person with the following cognitive profile. "
            "Respond naturally to the conversation, exhibiting the described psychological traits. "
            "DO NOT break character. If your authority_compliance is high, you tend to comply with authority figures. "
            "If your decision_delay is low, you tend to act quickly without deliberating. "
            "Profile: {{cognitive_profile_summary}}"
        ),
    },
    "adversary_persona_template": {
        "name": "{{adversary_role_name}}",
        "role": "adversary",
        "attack_goal": "{{attack_goal}}",
        "allowed_strategies": "{{retrieved_strategies_json}}",
        "cialdini_available": ["authority", "scarcity", "social_proof"],
        "system_prompt": (
            "You are simulating a social engineering attacker. Your goal is: {{attack_goal}}. "
            "You MUST only use tactics from the following approved strategy list: {{strategies_list}}. "
            "Do NOT invent new tactics. Use Cialdini principles strategically. "
            "Escalate when victim shows resistance."
        ),
    },
    "official_channel_persona": {
        "name": "Official Customer Service",
        "role": "verification_channel",
        "system_prompt": (
            "You represent the legitimate official service. When queried, always provide factual, calm responses. "
            "Never ask users to share screens, transfer funds to 'safe accounts', "
            "or provide verification codes via third-party channels."
        ),
    },
}


def build_victim_persona(
    user_name: str,
    scenario_type: str,
    cognitive_profile: Dict[str, Any],
    big_five_traits: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建受害者 persona。"""
    payload = deepcopy(SECURITY_PERSONA_TEMPLATES["victim_persona_template"])
    payload["name"] = user_name
    payload["scenario_type"] = scenario_type
    payload["cognitive_profile"] = json.dumps(cognitive_profile, ensure_ascii=False)
    payload["big_five_traits"] = {
        "openness": (big_five_traits or {}).get("openness", 5),
        "conscientiousness": (big_five_traits or {}).get("conscientiousness", 5),
        "extraversion": (big_five_traits or {}).get("extraversion", 5),
        "agreeableness": (big_five_traits or {}).get("agreeableness", 5),
        "neuroticism": (big_five_traits or {}).get("neuroticism", 5),
    }
    payload["system_prompt"] = payload["system_prompt"].replace(
        "{{cognitive_profile_summary}}",
        json.dumps(cognitive_profile, ensure_ascii=False),
    )
    return payload


def build_adversary_persona(
    adversary_role_name: str,
    attack_goal: str,
    strategies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建攻击者 persona。"""
    payload = deepcopy(SECURITY_PERSONA_TEMPLATES["adversary_persona_template"])
    payload["name"] = adversary_role_name
    payload["attack_goal"] = attack_goal
    payload["allowed_strategies"] = json.dumps(strategies, ensure_ascii=False)
    payload["system_prompt"] = (
        payload["system_prompt"]
        .replace("{{attack_goal}}", attack_goal)
        .replace("{{strategies_list}}", json.dumps(strategies, ensure_ascii=False))
    )
    return payload


def build_official_channel_persona() -> Dict[str, Any]:
    """构建官方核验 persona。"""
    return deepcopy(SECURITY_PERSONA_TEMPLATES["official_channel_persona"])
