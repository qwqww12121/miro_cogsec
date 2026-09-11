from app.modules.story_summarizer import _compact_step_payload, _normalize_step_explanations


def test_compact_step_payload_keeps_input_and_fork_actions():
    payload = _compact_step_payload({
        "scenario": "fraud_im",
        "input_text": "支付平台说登录异常，30分钟内核验。对方让我不要告诉家人。",
        "continue_name": "继续被诱导",
        "stoploss_name": "及时止损",
        "branch_a_log": [
            {"step": 1, "action": "对方用登录异常逼迫立刻核验", "world_state": {"posterior_risk": 0.7}},
            {"step": 2, "action": "对方要求对家人保密", "world_state": {"posterior_risk": 0.85}},
        ],
        "steps": [
            {"step": 1, "hopName": "施压", "continueAction": "继续配合"},
            {"step": 2, "hopName": "隔离", "inputQuote": "不要告诉家人"},
        ],
    })
    assert "不要告诉家人" in payload["input_text"]
    assert payload["branch_a"][1]["action"] == "对方要求对家人保密"
    assert payload["steps"][1]["name"] == "隔离"


def test_normalize_step_explanations_maps_by_step():
    snapshot = {
        "steps": [
            {"step": 1, "name": "施压", "continue": "继续配合", "quote": ""},
            {"step": 2, "name": "隔离", "continue": "保密", "quote": "不要告诉家人"},
        ]
    }
    parsed = {
        "steps": [
            {
                "step": 2,
                "meaning": "这一步的隔离是对方要求不要告诉家人，把核验切断。",
                "quote": "不要告诉家人",
                "continue": "如果继续保密，身边人帮不上忙。",
                "stoploss": "这时应告诉身边人或打官网。",
                "intervene": "在核验被切断前停下来，损失面最小。",
            },
            {
                "step": 1,
                "meaning": "这一步的施压是支付平台登录异常、30分钟内核验。",
                "quote": "30分钟内核验",
                "continue": "继续按对方时限走。",
                "stoploss": "先停下来打电话给官方客服。",
                "intervene": "越早停，后面越容易拦住。",
            },
        ]
    }
    result = _normalize_step_explanations(parsed, snapshot)
    assert result["source"] == "llm"
    assert result["steps"][0]["step"] == 1
    assert "登录异常" in result["steps"][0]["meaning"]
    assert result["steps"][1]["quote"] == "不要告诉家人"
    assert "Fork" not in result["steps"][0]["meaning"]
