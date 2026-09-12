from __future__ import annotations

from collections import Counter


def evaluate(task: dict, criteria: list[dict], evidence: list[dict], runs: list[dict], changed_files: list[dict], tests: list[dict]) -> dict:
    required = [item for item in criteria if item["required"]]
    verified_criteria = sum(item["status"] in ("verified", "not_applicable") for item in required)
    completion = 100 if required and verified_criteria == len(required) else round((verified_criteria / len(required)) * 100) if required else 35
    has_goal = bool(task["title"].strip() and task["description"].strip())
    has_basis = bool(task["completion_basis"].strip())
    has_evidence = bool(evidence)
    completeness = round(sum((has_goal, bool(criteria), has_basis, has_evidence, bool(runs))) / 5 * 100)
    confirmed = [item for item in evidence if item["verification_status"] == "confirmed"]
    rejected = [item for item in evidence if item["verification_status"] in ("rejected", "outdated")]
    evidence_score = min(100, len(evidence) * 20 + len(confirmed) * 20) if evidence else 0
    verification_score = round((len(confirmed) / len(evidence)) * 100) if evidence else 0
    total_tests = len(tests)
    passed = sum(item["status"].lower() in ("passed", "pass", "success") for item in tests)
    failed = sum(item["status"].lower() in ("failed", "fail", "error") for item in tests)
    execution_score = round(passed / total_tests * 100) if total_tests else (60 if runs else 0)
    risks = []
    for item in changed_files:
        if item.get("risk_level") and item["risk_level"] != "none":
            risks.append(f"文件路径风险：{item['path']}")
    tool_calls = sum((run.get("tool_calls", []) for run in runs), [])
    tool_failures = sum(item.get("status", "").lower() in ("failed", "error") for item in tool_calls)
    if tool_failures:
        risks.append(f"运行记录中存在 {tool_failures} 次失败工具调用")
    risky_tools = [item for item in tool_calls if item.get("risk_level") in ("high", "medium")]
    if risky_tools:
        risks.append(f"运行记录中存在 {len(risky_tools)} 条命令、脚本或网络调用风险提示")
    risk_score = max(0, 100 - len(risks) * 20)
    overall = round((completion + evidence_score + verification_score + execution_score + risk_score) / 5)
    verified = bool(required) and completion == 100 and verification_score >= 80 and failed == 0 and not rejected
    human_confirmed = bool(task.get("completion_basis")) and bool(confirmed)
    missing = []
    if not has_basis: missing.append("缺少人工填写的完成依据")
    if required and completion < 100: missing.append("仍有必需验收项未验证")
    if not confirmed: missing.append("没有人工确认的证据")
    if runs and not tests: missing.append("有运行记录但没有测试结果")
    if not runs: missing.append("没有导入运行记录")
    summary = "；".join(missing) if missing else "必需验收项、证据和测试均满足当前规则，但仍需人工确认最终结论"
    return {
        "completion_score": completion, "evidence_score": evidence_score, "verification_score": verification_score,
        "execution_score": execution_score, "risk_score": risk_score, "overall_score": overall,
        "verified": verified, "human_confirmed": human_confirmed, "summary": summary,
        "basis": {"required_criteria": len(required), "verified_criteria": verified_criteria, "evidence_count": len(evidence),
                   "confirmed_evidence": len(confirmed), "rejected_or_outdated": len(rejected), "tests": total_tests,
                   "passed_tests": passed, "failed_tests": failed, "risk_flags": risks, "missing": missing},
    }
