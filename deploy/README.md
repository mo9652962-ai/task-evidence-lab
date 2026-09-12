# 公网部署安全版：第一阶段

本目录提供“Caddy + oauth2-proxy + FastAPI”边界模板。它的目标是先建立部署边界，不把代理转发的身份头误认为已经完成业务授权。

## 组件职责

- Caddy：公网入口、自动申请/续期 HTTPS 证书、静态前端和反向代理。
- oauth2-proxy：OIDC 登录、上游 IdP 会话和安全 Cookie。
- FastAPI：只监听 `127.0.0.1`，接受来自本机反向代理的请求；第一阶段仅完成 Host/代理边界和安全响应头。
- 后续阶段：FastAPI 需要自行验证可信代理提供的身份映射，并在每个资源操作上执行对象级权限检查。

## 启动边界

生产 profile 必须设置这些变量：

```powershell
$env:TASK_EVIDENCE_DEPLOYMENT_PROFILE = "production"
$env:TASK_EVIDENCE_PUBLIC_BASE_URL = "https://evidence.example.com"
$env:TASK_EVIDENCE_ALLOWED_HOSTS = "evidence.example.com"
$env:TASK_EVIDENCE_TRUSTED_PROXY_IPS = "127.0.0.1"
$env:TASK_EVIDENCE_SESSION_COOKIE_SECURE = "true"
$env:TASK_EVIDENCE_SECURE_HEADERS = "true"
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
4. 验证未登录 API 返回拒绝、登录后代理能提供 `X-Auth-Request-*` 头，且这些头不能从公网客户端直接伪造到 FastAPI。

## 明确未包含

第一阶段尚未实现 FastAPI 内部的用户表、会话撤销、角色权限、任务所有者/协作者和对象级授权。Caddy/oauth2-proxy 成功登录只证明入口身份会话成立，不证明某个用户有权读取或修改某个任务。
