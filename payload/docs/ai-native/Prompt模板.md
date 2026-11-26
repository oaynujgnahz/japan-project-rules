# Prompt 模板（简版）

规则在 `.cursor/rules/`。占位符：`{機能}` `{docs路径}` `{范围}`

阶段：**理解现状 → 写设计书 → 设计评审 → 功能开发 → 实现评审 → 单元测试 → 联调验收**

---

## 常用一句

| 场景 | Prompt |
|------|--------|
| 理解现状 | `理解现状：{機能}，只读，输出主键/权限/参照路径，不写代码` |
| 写设计书 | `按 docs/ai-native/設計書模板/ 为 {機能} 写设计书到 {docs路径}` |
| 设计评审 | `设计评审：{docs路径}，按 review.mdc 输出 RV，不改源码` |
| 功能开发 | `开发：{范围}，按 {docs路径} minimal diff，ja/en locale（不需 zh）` |
| 实现评审 | `实现评审：对照 {docs路径} 与 diff，按 review.mdc RV，不改代码` |
| 单元测试 | `测试：{{build_cmd}} -pl {{main_module}} -am test -DskipTests=false，frontend npm run build；确认単体テスト項目_{機能}.xlsx 已同步` |
| 联调 | `联调：{docs路径}/06_画面設計書 主路径 smoke` |
| Debug | `Debug：{现象}，根因+最小 diff+重跑测试` |
| PR | `按 .github/pull_request_template.md 写 PR 描述（只写业务内容，不含 RV 结果 / BR・AC 编号 / docs 路径），不 commit` |

---

## 一条龙（可选）

```
Orchestrator：按 workflow.mdc 推进 {機能}，设计书 {docs路径}。
设计评审通过后再写代码。完成前输出 review.mdc checklist。
验证：{{build_cmd}} -pl {{main_module}} -am test -DskipTests=false && cd {{frontend_module}} && npm run build
```

---

## 团队启用（摘要）

`.cursor/rules/`、`docs/ai-native/`、`e2e/` 为**本地专用**，不在 git 中，拉代码不会得到。  
每人自配：`e2e/.env`、`mcp.json`（见 `e2e/.env.example`）。  
Cursor 以 rules 为准；Codex 可读根目录 `AGENTS.md`。

---

## Skills

文件 I/O / Excel·PPT → `{{name}}-report-file-io`（`install.sh` 安装到 `~/.cursor/skills/`，没有则跳过并注明）  
设计书 Markdown 原稿 → `md-design-doc`（冲突时以 `design-docs.mdc` 为准）；xlsx 导出（API設計書 / 画面設計書 两份）→ 设计书 bot，不用 bot 时由 Cursor 导出  
安装说明 → [skills/README.md](./skills/README.md)
