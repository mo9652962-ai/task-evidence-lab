# 公网部署安全版：第二阶段

本目录提供“Caddy + oauth2-proxy + FastAPI”边界模板。它的目标是先建立部署边界，不把代理转发的身份头误认为已经完成业务授权。

## 组件职责

- Caddy：公网入口、自动申请/续期 HTTPS 证书、静态前端和反向代理。
- oauth2-proxy：OIDC 登录、上游 IdP 会话和安全 Cookie。
- FastAPI：只监听 `127.0.0.1`，只接受来自可信代理的身份头，并在任务及其子资源上执行对象级权限检查。
- Redis：生产环境用于跨进程集中式限流；Redis 不可用时 production profile fail-closed。
- SQLite：保存内部用户、OIDC identity 映射、哈希后的不透明应用会话和任务成员关系。

## 启动边界

生产 profile 必须设置这些变量：

```powershell
$env:TASK_EVIDENCE_DEPLOYMENT_PROFILE = "production"
$env:TASK_EVIDENCE_PUBLIC_BASE_URL = "https://evidence.example.com"
$env:TASK_EVIDENCE_ALLOWED_HOSTS = "evidence.example.com"
$env:TASK_EVIDENCE_TRUSTED_PROXY_IPS = "127.0.0.1"
$env:TASK_EVIDENCE_SESSION_COOKIE_SECURE = "true"
$env:TASK_EVIDENCE_SECURE_HEADERS = "true"
$env:TASK_EVIDENCE_OIDC_ISSUER = "https://your-idp.example.com/realms/your-realm"
$env:TASK_EVIDENCE_OIDC_ADMIN_GROUPS = "task-evidence-admin"
$env:TASK_EVIDENCE_REDIS_URL = "redis://127.0.0.1:6379/0"
$env:TASK_EVIDENCE_REDIS_REQUIRED = "true"
```

在 `backend/` 目录启动 FastAPI：

```powershell
..\.venv\Scripts\python -m uvicorn app.main:app `
  --host 127.0.0.1 `
  --port 8765 `
  --proxy-headers `
  --forwarded-allow-ips 127.0.0.1
```

`--forwarded-allow-ips` 只允许本机 Caddy 注入的转发头生效。不要把 FastAPI 改为监听 `0.0.0.0`，也不要把公网网段填入可信代理列表。

构建前端并启动 Caddy：

```powershell
cd frontend
npm run build
cd ..
$env:TASK_EVIDENCE_DOMAIN = "evidence.example.com"
caddy run --config deploy/Caddyfile
```

实际部署前还需要：

1. 在 OIDC 提供方注册回调地址 `https://evidence.example.com/oauth2/callback`。
2. 将 `oauth2-proxy.env.example` 复制到不被 Git 管理的安全位置，并填入真实 Client Secret、Cookie Secret 和允许的域名/群组。
3. 用防火墙限制 `8765` 和 `4180` 仅本机可访问。
4. 确认 `X-Auth-Request-User` 被代理配置为稳定的 OIDC subject，而不是邮箱或可变昵称；邮箱只用于展示和同步。
5. 验证未登录 API 返回拒绝、登录后代理能提供 `X-Auth-Request-*` 头，且这些头不能从公网客户端直接伪造到 FastAPI。
6. 验证 Redis 可用、`/api/ready` 为 ready，双 worker 下请求共享同一个限流窗口。

审计维护命令示例：

```powershell
cd backend
..\.venv\Scripts\python -m app.audit_tools verify
..\.venv\Scripts\python -m app.audit_tools archive --destination ..\data\audit-archive
```

## 明确未包含

当前阶段已实现 FastAPI 内部用户表、OIDC identity 映射、服务端会话撤销、任务成员角色和对象级访问检查。Caddy/oauth2-proxy 成功登录仍只证明入口身份会话成立；业务访问还必须通过 FastAPI 的任务成员授权。

审计事件包含哈希链字段，可导出为压缩 NDJSON 和 manifest；归档目标当前提供本地目录抽象，生产对象存储/WORM、日志轮换策略和监控告警端点需要按部署环境接入。

真实域名、证书、OIDC 提供方、Redis、归档存储和公网联调不包含在本地测试中，必须按上线验收清单单独验证。
