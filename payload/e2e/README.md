# {{system_name}} E2E（Playwright）

结合测试脚本目录，配合 **Playwright MCP** 或 CI 使用{{ex_test_policy_note}}。

##  setup

```bash
cd e2e
npm install
npx playwright install chromium
cp .env.example .env   # 设置 BASE_URL、测试账号
```

## 运行

```bash
npm test              # headless
npm run test:headed   # 有界面
npm run test:ui       # Playwright UI 模式
```

## 环境变量（`.env`，勿提交）

| 变量 | 说明 |
|------|------|
| `BASE_URL` | 前端地址，如 `http://localhost:5173` |
| `E2E_USER` / `E2E_PASSWORD` | Keycloak 测试账号（可选，无则 skip 登录用例） |

## 编写约定

- 一功能一 spec：`tests/{機能}.spec.ts`
- 从 `docs/{機能}/06_画面設計書/` 提取主路径
- 登录 fixture 复用 `tests/fixtures/auth.ts`（待扩展）
- 失败保留 screenshot（playwright.config 已开）

## Agent

1. 读画面设计书 → 生成/更新 spec
2. Playwright MCP 或 `cursor-ide-browser` 先 smoke
3. 固化通过后提交 spec

## MCP

见 `docs/ai-native/MCP_Setup.md`。
