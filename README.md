# Task Evidence Lab

任务证据与质量复盘系统。

Task Evidence Lab 用于把一次任务从“提出”到“交付”之间的证据、判断和复盘沉淀下来，帮助个人或小团队回答三个问题：

1. 这项任务到底要完成什么？
2. 哪些证据证明它已经完成、质量如何？
3. 下一次应该保留什么、改进什么？

## 当前版本

这是一个 Windows 优先的本地 Web 应用：

- 前端：Vue 3 + Vite + TypeScript
- 后端：FastAPI + SQLite
- 导出：Markdown 和 JSON
- AI：默认关闭；第一版只使用可解释的确定性规则评测
- 安全边界：导入的命令、脚本、路径和工具调用只展示，绝不执行
- 任务操作：编辑、归档、恢复可见和带确认的单任务删除
- 运行复盘：步骤、工具调用、变更文件、测试结果时间线，以及两次运行的逐次明细对比
- 文件证据：可将真实本地文件复制到 `data/evidence/`，记录大小与 SHA-256
- 数据保护：可导出带版本号的 JSON 备份，并在确认后事务性恢复本地记录
- 链接证据：可由用户主动检查公开 HTTP/HTTPS 链接的可达性，并保存状态码和检查时间
- 复盘交付：增强 Markdown 报告、HTML 打印版（浏览器可另存为 PDF）和 `#task/{id}` 独立详情视图
- 批量交付：在任务对比完成后，可将多个任务聚合导出为一份 Markdown 复盘报告
- 可视化：任务对比条形指标、风险/未完成项/多次运行筛选，以及任务中心式证据关联图
- 可追溯性：任务详情展示最近 200 条关键变更审计；删除任务后审计记录仍保留为脱离任务的历史记录
- 任务模板：保存目标、优先级、完成依据、验收项和证据类型，并一键创建带待补充证据的任务
- 性能与稳定性：任务搜索服务端过滤、ASCII 关键词使用 SQLite FTS5、任务列表计数避免 N+1 查询、分页、SQLite WAL/busy timeout、前端请求超时和证据图按需加载
- 交互优化：搜索标题/目标并防抖，首屏任务/模板/经验候选并行加载，结构化参数错误可被前端统一展示
- 前端可维护性：任务列表、任务详情、任务模板和任务对比已从 `App.vue` 拆为独立组件，并各自覆盖关键交互测试
- 本地保护：可选 `TASK_EVIDENCE_API_KEY`、进程内固定窗口限流 `TASK_EVIDENCE_RATE_LIMIT`、安全响应头和可配置 CORS；默认仍保持本地单机免鉴权

## 运行

启动后端：

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8765
```

启动前端（另开终端）：

```powershell
cd frontend
npm install
npm run dev
```

然后访问 <http://localhost:5173>。

## 目录

```text
task-evidence-lab/
├─ backend/         # FastAPI、SQLite、确定性评测与导入
├─ frontend/        # Vue 3 + Vite + TypeScript
├─ migrations/      # 可审阅的 SQLite schema
├─ docs/mvp.md      # MVP 范围与后续路线
├─ AGENTS.md        # 项目协作约定
├─ .env.example
└─ .gitignore
```

## 测试

后端：

```powershell
cd backend
..\.venv\Scripts\python -m pytest
```

前端：

```powershell
cd frontend
npm test
npm run build
npm run test:e2e
```

`npm test` 包含 Vitest 组件测试；`npm run test:e2e` 使用 Playwright，首次运行需要准备对应的 Chromium 浏览器：

```powershell
npx playwright install chromium
```

本地性能基线（使用临时 SQLite 数据库，不改动当前数据）：

```powershell
cd backend
..\.venv\Scripts\python scripts\performance_smoke.py --tasks 500 --repetitions 10
```

该脚本只用于比较本机代码改动前后的列表/搜索趋势，不代表真实生产环境的 RUM、压力测试、网络延迟或多进程部署结果。

数据库 schema 命令：

```powershell
cd backend
..\.venv\Scripts\python -m app.migrations status
..\.venv\Scripts\python -m app.migrations upgrade
```

## 安全说明

- API 不接受或执行 shell 命令。
- 运行记录导入只解析 JSON、JSONL 或 Markdown 文本。
- 导入文本有大小和字段长度限制，并使用参数化 SQL。
- 本地文件证据只接受已存在的普通文件，单文件上限为 50 MB；复制后计算 SHA-256，并固定保存到应用数据目录下的 `data/evidence/`。
- 文件证据复制只做复制和登记，应用不会执行文件、命令或脚本。
- JSON 恢复只接受受支持的备份版本，恢复会替换当前 SQLite 记录并要求前端二次确认；本地证据文件本身不包含在 JSON 中。
- 外部链接检查只允许 80/443 端口，拒绝解析到本机、内网或其他非公网地址的目标，不自动检查、不跟随重定向。
- Vue 模板默认转义用户内容；Markdown 报告对文本进行转义。
- 风险评分是静态提示，不等于事实判断，也不自动阻止用户操作。
- 默认仍按本地单机运行；如需在局域网临时暴露，可设置 `TASK_EVIDENCE_API_KEY`，并按需设置 `TASK_EVIDENCE_RATE_LIMIT`（每个客户端/IP 与路径的每分钟请求数）和 `TASK_EVIDENCE_CORS_ORIGINS`。这不是完整账号、角色权限或分布式限流方案。

## 后续建议

- 增加真正的多路由页面和更细的权限策略
- 保持证据关系图的保守语义，不自动推断证据真实性或因果关系
- 任务规模继续增长时评估中文分词/FTS5 tokenizer、搜索相关性和索引重建工具
- 若开放公网，补充账号认证、对象级权限、集中式限流、审计留存/轮换、HTTPS 和部署级监控
