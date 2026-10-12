# MCP & Skill 一覧（CMPF）

> **环节强制要求以 `.cursor/rules/workflow.mdc` 为准。**

## 按工程环节

| 环节 | 必用 | 禁止 |
|------|------|------|
| 要件/设计 | `md-design-doc`（与 `design-docs.mdc` 冲突时以后者为准）、`验收标准_模板.md`；xlsx 拆 API設計書 / 画面設計書 两份导出 | 无 docs |
| 既存理解 | Grep / SemanticSearch / `explore` | 猜测 |
| 文件 I/O | `cmpf-report-file-io`（没有则读既存实现并注明） | 自造取込逻辑 |
| RV | `review.mdc` | 跳过 checklist |
| 单体 | `unit-test-case-docs.mdc`（有单体case bot 时由它生成）、回归矩阵模板（`verification-before-completion` 有则用） | skipTests 即完成 |
| E2E | Playwright MCP / Browser + `e2e/`（没有则人工 case 并注明） | 仅 MagicPod |
| DB | PostgreSQL MCP 只读（没有则读 DDL / mapper 并注明） | 臆造 schema |
| PR | `.github/pull_request_template.md`（只写业务内容） | 空 test plan；贴 RV 结果 / BR・AC 编号 / `docs/` 路径 |

## 接入

| 资产 | 路径 |
|------|------|
| MCP 配置 | [MCP_Setup.md](./MCP_Setup.md)、`.cursor/mcp.json.example` |
| Skills 安装 | [skills/README.md](./skills/README.md) |
| E2E | `e2e/README.md` |

## 状态

| 能力 | 状态 |
|------|------|
| Cursor rules | ✅ 本地专用（不在 git 中） |
| Playwright e2e | ✅ 脚手架 + smoke |
| MCP | ⚠️ 每人本地启用 |
| Skills | ⚠️ 每人安装 |
| E2E in CI | ❌ 待加 pipeline（可选） |
