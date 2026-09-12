from __future__ import annotations

from html import escape


def md(value: object) -> str:
    return str(value or "").replace("\r", "").strip()


def _run_markdown(run: dict) -> list[str]:
    lines = [f"### 运行 #{run['id']}：{md(run.get('executor'))}（{md(run.get('status'))}）", ""]
    lines += [f"- 模型：{md(run.get('model')) or '未记录'}", f"- 开始：{md(run.get('started_at')) or '未记录'}", f"- 结束：{md(run.get('finished_at')) or '未记录'}", "- 说明：导入内容仅展示，未执行其中任何命令。", ""]
    lines.append("步骤：")
    lines += [f"- #{step['step_index']} {md(step['step_type'])}｜{md(step['status'])}｜{md(step['content'])}" for step in run.get("steps", [])] or ["- 暂无步骤"]
    lines.append("工具调用：")
    lines += [f"- {md(call['tool_name'])}｜{md(call['status'])}｜风险：{md(call['risk_level'])}｜输入：{md(call['input_json'])}" for call in run.get("tool_calls", [])] or ["- 暂无工具调用"]
    lines.append("文件变更：")
    lines += [f"- {md(item['path'])}｜{md(item['change_type'])}｜+{item['additions']} / -{item['deletions']}｜风险：{md(item['risk_level'])}" for item in run.get("changed_files", [])] or ["- 暂无文件变更"]
    lines.append("测试：")
    lines += [f"- {md(item['name'])}｜{md(item['status'])}｜{item.get('duration_ms') or 0} ms" for item in run.get("tests", [])] or ["- 暂无测试结果"]
    return lines


def render_markdown(task: dict, criteria: list[dict], evidence: list[dict], evaluation: dict | None, reviews: list[dict], runs: list[dict]) -> str:
    completed = [item for item in criteria if item["status"] in ("verified", "not_applicable")]
    unfinished = [item for item in criteria if item["status"] not in ("verified", "not_applicable")]
    lines = [f"# 任务复盘：{md(task['title'])}", "", "## 任务目标", "", md(task["description"]), "", "## 完成标准", ""]
    lines += [f"- [{'x' if item in completed else ' '}] {md(item['title'])}（{'必需' if item['required'] else '可选'}，{item['status']}）" for item in criteria] or ["- 暂未填写"]
    lines += ["", "## 已完成内容", "", "- " + ("；".join(md(item["title"]) for item in completed) or "暂无"), "", "## 未完成内容", "", "- " + ("；".join(md(item["title"]) for item in unfinished) or "暂无"), "", "## 证据清单", ""]
    lines += [f"- {md(item['title'])}｜{md(item['evidence_type'])}｜状态：{md(item['verification_status'])}｜来源：{md(item['source'])}" for item in evidence] or ["- 暂无证据"]
    lines += ["", "## 证据核验", ""]
    lines += [f"- {md(item['title'])}：人工状态={md(item['verification_status'])}；链接检查={md(item.get('link_check_status')) or '未检查'}；本地副本={md(item.get('local_path')) or '无'}；SHA-256={md(item.get('sha256')) or '无'}" for item in evidence] or ["- 暂无证据核验记录"]
    lines += ["", "## 测试结果", "", f"- 导入运行记录：{len(runs)} 条", "", "## 运行明细", ""]
    for run in runs:
        lines += _run_markdown(run) + [""]
    lines += ["## 风险标记", "", "- 见运行明细中的文件和工具风险，以及评测结果中的静态风险标记。", "", "## 评测结果", ""]
    if evaluation:
        lines += [f"- 完成度：{evaluation['completion_score']}", f"- 证据充分性：{evaluation['evidence_score']}", f"- 验证状态：{evaluation['verification_score']}", f"- 执行情况：{evaluation['execution_score']}", f"- 风险评分：{evaluation['risk_score']}", f"- 综合分：{evaluation['overall_score']}", f"- 系统推断 verified：{evaluation['verified']}", f"- 人工确认 human_confirmed：{evaluation['human_confirmed']}", f"- 评分依据：{evaluation['summary']}"]
    else:
        lines.append("- 尚未运行确定性评测。")
    lines += ["", "## 人工复盘", ""]
    lines += [f"- {md(item['reviewer'])}：{md(item['content'])}" for item in reviews] or ["- 暂无人工复盘"]
    lines += ["", "## 后续行动", "", "- 补充未验证验收项和人工确认。", "", "## 是否建议沉淀为经验", "", "- 待人工确认。"]
    return "\n".join(lines) + "\n"


def render_html(task: dict, criteria: list[dict], evidence: list[dict], evaluation: dict | None, reviews: list[dict], runs: list[dict]) -> str:
    esc = lambda value: escape(md(value))
    criteria_rows = "".join(f"<tr><td>{'✓' if item['status'] in ('verified', 'not_applicable') else '□'}</td><td>{esc(item['title'])}</td><td>{esc(item['status'])}</td></tr>" for item in criteria) or '<tr><td colspan="3">暂无验收项</td></tr>'
    evidence_rows = "".join(f"<tr><td>{esc(item['title'])}</td><td>{esc(item['evidence_type'])}</td><td>{esc(item['verification_status'])}</td><td>{esc(item.get('link_check_status')) or '未检查'}</td></tr>" for item in evidence) or '<tr><td colspan="4">暂无证据</td></tr>'
    run_sections = "".join(f"<section><h3>运行 #{run['id']}：{esc(run.get('executor'))}</h3><p>状态：{esc(run.get('status'))}；记录只展示，不执行命令。</p><ul>" + "".join(f"<li>步骤 #{step['step_index']}：{esc(step['content'])}（{esc(step['status'])}）</li>" for step in run.get('steps', [])) + "</ul></section>" for run in runs) or "<p>暂无运行记录。</p>"
    score = f"<p class=\"score\">综合分：{evaluation['overall_score']}</p>" if evaluation else "<p>尚未运行确定性评测。</p>"
    review_html = "".join(f"<li><b>{esc(item['reviewer'])}</b>：{esc(item['content'])}</li>" for item in reviews) or "<li>暂无人工复盘</li>"
    return f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>任务复盘：{esc(task['title'])}</title><style>body{{font-family:Segoe UI,Microsoft YaHei,sans-serif;max-width:960px;margin:40px auto;color:#172033;line-height:1.6}}h1{{border-bottom:2px solid #29405f;padding-bottom:12px}}h2{{margin-top:32px;color:#234a72}}table{{width:100%;border-collapse:collapse;margin:12px 0 24px}}th,td{{border:1px solid #ccd5e2;padding:8px;text-align:left}}.score{{font-size:24px;font-weight:700}}section{{break-inside:avoid;border:1px solid #d7dee8;border-radius:8px;padding:12px;margin:12px 0}}@media print{{body{{margin:12mm;max-width:none}}button{{display:none}}}}</style></head><body><h1>任务复盘：{esc(task['title'])}</h1><p>{esc(task.get('description'))}</p><h2>完成标准</h2><table><tr><th>状态</th><th>验收项</th><th>当前状态</th></tr>{criteria_rows}</table><h2>证据核验</h2><table><tr><th>证据</th><th>类型</th><th>人工状态</th><th>链接检查</th></tr>{evidence_rows}</table><h2>运行明细</h2>{run_sections}<h2>评测结果</h2>{score}<h2>人工复盘</h2><ul>{review_html}</ul></body></html>"""
