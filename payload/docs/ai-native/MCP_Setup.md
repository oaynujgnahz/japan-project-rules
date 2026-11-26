# MCP 接入指南（{{system_name}}）

团队本地启用 MCP；**勿将含密码的 `mcp.json` 提交 Git**。

## 1. 复制配置

```bash
cp .cursor/mcp.json.example .cursor/mcp.json
# 编辑 mcp.json，填入 PostgreSQL 等 env（仅本地）
```

`.cursor/mcp.json` 建议加入 `.gitignore`（若尚未忽略）。

## 2. 已配置 Server

| Server | 用途 | 环节 |
|--------|------|------|
| `@playwright/mcp` | E2E 浏览器自动化 | 联调验收 |
| `cursor-ide-browser` | Cursor 内置，smoke 验证 | 联调验收 |
| PostgreSQL（只读） | schema/数据确认 | 理解现状 / 写设计书、开发前 |

## 3. Playwright MCP

```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"]
}
```

配合仓库 `e2e/` 脚本：Agent 可 MCP 探索 + 固化到 `e2e/tests/*.spec.ts`。

## 4. PostgreSQL MCP（只读）

示例（按实际 MCP 包名调整）：

```json
"postgres": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"]
}
```

`DATABASE_URL` 仅 dev 只读账号。禁止生产写权限。

## 5. 环节强制（见 `workflow.mdc`）

- 实装前查表结构 → 有 PG MCP 则必须查询，无则读 mapper/SQL 文件并注明
- 画面 smoke → 有 Browser/Playwright MCP 则跑主路径，失败写入 RV

## 6. 验证 MCP 已加载

Cursor Settings → MCP → 对应 server 为绿色；对话中让 Agent 列出可用 MCP tools。
