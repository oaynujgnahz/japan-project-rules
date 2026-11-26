# {{system_name}} AI Native 基础整备

基于 CO2MOS AI 本格運用方針 v2。

> **本地专用**：`docs/`、`.cursor/`、`AGENTS.md` 等不在 git 中、不提交到甲方仓库（见 `AGENTS.md` §本地专用）。
> 团队分工（各 bot 负责什么）见 [開発フロー.md](./開発フロー.md) §团队分工。

## 开发阶段（workflow 主源）

| 顺序 | 阶段 | 做什么 |
|------|------|--------|
| 1 | **理解现状** | 读代码，输出主键/校验摘要 |
| 2 | **写设计书** | docs + 验收标准 |
| 3 | **设计评审** | 对照 review.mdc，无 Blocker |
| 4 | **功能开发** | 写 Java/Vue/SQL/locale |
| 5 | **实现评审** | 设计书 ↔ 代码比对 |
| 6 | **单元测试** | JUnit + build + 回归矩阵 + 单体 Case（`単体テスト項目_{機能}.xlsx`）同步 |
| 7 | **联调验收** | E2E / 结合测试大纲 |

## 模板是可选的，不是对话协议

**日常和 Agent 说话用自然语言即可**，不必贴 `Prompt模板.md` 里的固定段落，也不必说「理解现状模式」「功能开发模式」等关键词。Agent 会从你的话、仓库代码和对话上下文理解要做什么。

| 机制 | 作用 | 你是否必须做 |
|------|------|----------------|
| `.cursor/rules/*.mdc` | 打开本仓库后自动生效，引导编码习惯与质量要求 | 否（自动） |
| [Prompt模板.md](./Prompt模板.md) | 可复制范例，适合新功能、分阶段、多人协作 | **可选** |
| 七个开发阶段 | 团队纪律：何时先设计、何时再写代码 | 大需求建议遵守；小改可跳过 |
| 验收/回归/结合测试模板 | 本地留痕用（不贴进甲方 PR） | 大需求时填写 |

**什么时候直接说需求就够：**

- 小 bug、局部修改、问代码在哪、解释逻辑
- 范围已说清楚（例如「只改一覧复制弹窗」）
- 你明确说「设计书有了，直接开发」

**什么时候建议用模板或 @ 规则：**

- 新功能、跨前后端 + SQL + locale
- 需要验收标准、回归矩阵、结合测试大纲（本地留存）
- 大改（多文件、易漏主键/校验）— 可 `@workflow.mdc` 或新开对话贴 Prompt 模板 §1

**结论：** 模板解决的是「团队一致、少漏项」，不是「Agent 只能听懂固定格式」。Rules 在后台起作用；Prompt 模板是加速器，不是门禁卡。

## 快速入口

| 用途 | 文档 |
|------|------|
| **团队启用 Checklist** | [TEAM_ONBOARDING.md](./TEAM_ONBOARDING.md) — 新人/团队第一次使用前确认 |
| **开新对话复制 prompt** | [Prompt模板.md](./Prompt模板.md) |
| **流程约束（Cursor 主源）** | `.cursor/rules/workflow.mdc` |
| **RV checklist** | `.cursor/rules/review.mdc` |
| **团队装 Skills** | [skills/README.md](./skills/README.md) |
| **开 PR** | `.github/pull_request_template.md`（本地模板；PR 说明只写业务内容） |

## 模板（写设计书 / 单元测试 / 联调验收）

| 模板 | 用途 |
|------|------|
| **[設計書記述規範.md](./設計書記述規範.md)** | **设计书主文写法（业务语言・処理フロー）** |
| **[設計書模板/](./設計書模板/README.md)** | **新功能 MD 设计书原稿全套**（詳細設計・06 画面・07 API・openapi）；对外版 xlsx 从 MD 导出，拆成 `API設計書_{機能}.xlsx` + `画面設計書_{機能}.xlsx`（`design-docs.mdc`） |
| [验收标准_模板.md](./验收标准_模板.md) | 写设计书 → `docs/{機能}/验收标准.md` |
| [単体テスト項目_テンプレート.xlsx](./単体テスト項目_テンプレート.xlsx) | 单体测试 Case；`試験観点` 固定，其他 Sheet 填写功能专属 Case |
| [回归テスト矩阵_模板.md](./回归テスト矩阵_模板.md) | 单元测试 → 本地 `docs/{機能}/` 留存（不附 PR） |
| [結合テスト大纲_模板.md](./結合テスト大纲_模板.md) | 联调验收 → E2E / 人工 |

## 详细说明

| 文档 | 内容 |
|------|------|
| [開発フロー.md](./開発フロー.md) | 全流程图示（详细版） |
| [Agent编排.md](./Agent编排.md) | Multi-Agent 说明 |
| [MCP_Skill一覧.md](./MCP_Skill一覧.md) | MCP/Skill 对照 |
| [MCP_Setup.md](./MCP_Setup.md) | MCP 本地接入 |
| [仕様MD化_バックログ.md](./仕様MD化_バックログ.md) | MD 化优先级 |
| [UI規範.md](./UI規範.md) | 共通 UI |
| [用語辞書_日英.md](./用語辞書_日英.md) | 术语 |

> **Cursor**：`.cursor/rules/` · **Codex 等**：根目录 `AGENTS.md`

## 多语言（locale）

- 用户可见文案：**仅维护 ja / en**（`{{frontend_module}}/src/locale/ja`、`en`）
- `locale/zh/` 目录存在但 **不在维护范围**；新功能・改修不要追加 zh 文案
- 规范：`.cursor/rules/i18n-locale.mdc` · 术语：`用語辞書_日英.md`

## Cursor Rules

| 规则 | alwaysApply |
|------|-------------|
| `project-core` | ✅ 精简总览 |
| `workflow` | ✅ 开发阶段门禁 + 模板索引 |
| `review` | ✅ RV checklist |
| `unit-test-case-docs` | ✅ 功能文档 ↔ 单体 Case 同步门禁 |
| 其余 8 个 | 按 glob |

## E2E

`e2e/` · MCP：`.cursor/mcp.json.example`
{{ex_readme_design_reference}}
