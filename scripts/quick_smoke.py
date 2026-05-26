"""Quick smoke test against local backend."""
import urllib.request, json, sys

payload = {"scenario": "来电者自称公安机关，称账户涉嫌洗钱，要求全程保密并把资金转入安全账户接受核查", "scenario_type": "authority_impersonation"}
body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:5001/api/cogsec/analyze",
    data=body,
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=90) as r:
    d = json.loads(r.read().decode("utf-8"))

rb = ((d.get("data") or {}).get("metrics") or {}).get("risk_breakdown") or {}
print("success:", d.get("success"))
print("risk_level:", rb.get("risk_level"))
print("final_risk:", rb.get("final_risk"))
print("error:", d.get("error", "none"))
