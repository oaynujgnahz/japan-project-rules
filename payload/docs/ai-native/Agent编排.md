# Agent 编排（CMPF / Cursor）

> **角色与 Stop Condition 以 `.cursor/rules/workflow.mdc` 为准。** 本文为架构说明。
>
> **本地专用**：不提交到甲方仓库（见 `AGENTS.md` §本地专用）。

## 角色对应（Grok Bot 群「碳排放小组」）

| 本文角色 | 担当 bot |
|----------|----------|
| Orchestrator | Grok Bot |
| Docs（设计书） | 碳排放-设计书 |
| Docs（单体 Case） | 碳排放-单体case |
| Feature / Test / Debug | 碳排放-coder |
| Review（含 bugbot / security） | 碳排放-reviewer |

详细分工见 [開発フロー.md](./開発フロー.md) §团队分工。

> **不使用 Grok Bot 时**（只用 Cursor 开发）：各角色全部由 Cursor Agent 自己承担（可按 `cmpf-orchestrator.md` 分阶段 / 分 subagent），流程、门禁、产出物不变。

## 架构

```
Human Lead（目标 · 最终 RV · PR 合并）
    ↓
Orchestrator（workflow 开发阶段 · Prompt模板.md）
    ↓
Feature / Test / Review / Debug / Docs
    ↓
Skills（docs/ai-native/skills/，没有则跳过并注明）+ MCP + ./mvn8 + e2e/
    ↓
review.mdc（RV 结果本地留存）+ 人工 PR（仅业务内容）+ CI
```

## Cursor 中的 Multi-Agent

1. **分对话** = 分角色（见 [Prompt模板.md](./Prompt模板.md) 七个阶段）
2. **Subagent**：`explore` / `shell` / `bugbot` / `ci-investigator`
3. **Rules 按 glob** = 领域专家（java-backend、frontend-vue 等）

## Scope 边界（CMPF）

| 领域 | Feature Scope | 禁止 |
|------|---------------|------|
| 报告/PPT/Excel | `carbonapi/.../report/`、`excel/` | 无设计书改模板坐标 |
| 新画面 | apis + views + router + locale | 漏 routes-classic |
| 电力连携 | controller/service + sql | 未读外部 IF 定义书 |
| userapi | 模块内 | 改 prd manifest |

## 复盘映射

| 问题 | Agent | 资产 |
|------|-------|------|
| 翻译错误 | Feature + Docs | `用語辞書`、`i18n-locale.mdc` |
| 主键/error check | Review + Feature | `review.mdc` |
| UI デグレ | Feature + Test | `UI規範`、回归矩阵 |
| 场景测试 | Test + Docs | 結合テスト大纲、`e2e/` |
