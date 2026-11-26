# {{system_name}} Cursor 团队启用 Checklist

面向第一次在 {{repo_name}} 中使用 Cursor 的开发者、Reviewer、Human Lead。

> **本地专用**：`docs/`、`.cursor/`、`AGENTS.md` 等不在 git 中、不提交到甲方仓库（见 `AGENTS.md` §本地专用）。

## 1. 每人一次准备

- [ ] `git pull` 最新 {{repo_name}}，并用 Cursor 打开仓库根目录
- [ ] 本规则体系不在 {{system_name}} git 中：clone 私有仓库 `japan-project-rules`，执行 `./install.sh <{{repo_name}} 路径>`（自动复制规则、写入 `.git/info/exclude`、安装 skills）；提交时不要把这些文件带进 {{system_name}} 的提交
- [ ] 确认 `.cursor/rules/` 存在；`project-core.mdc`、`workflow.mdc`、`review.mdc`、`unit-test-case-docs.mdc` 为常驻规则
- [ ] 后端命令使用仓库本地 `{{build_cmd}}`（自动查找 Java 8 和 mvn；找不到时设 `JAVA8_HOME` / `MAVEN_BIN`）
- [ ] 前端使用项目约定的 Node / npm；执行前先 `cd {{frontend_module}} && npm install`
- [ ] 如需联调，执行 `cd e2e && npm install && npx playwright install chromium`
- [ ] 如需 MCP，复制 `.cursor/mcp.json.example` 到 `.cursor/mcp.json` 并只填本地/只读账号

## 2. 开发前判断

| 场景 | 推荐做法 |
|------|----------|
| 小 bug / 局部改修 | 直接说清范围，先理解现状再改 |
| 新功能 / 跨前后端 / DB / locale | 按七阶段流程，先建 `docs/{機能}/` |
| 画面布局 / 列 / 按钮 / 控件变更 | 先提供 PPT/截图/06 画面设计书，并输出 PPT vs 现状差异表 |
| 文件下载 / 上传 / Excel / PPT / PDF | 使用 `{{name}}-report-file-io`（`install.sh` 已安装到 `~/.cursor/skills/`；没有则跳过并注明），先找同类实现 |
| 只做 Review | 明确要求“不改代码”，按 `review.mdc` 输出 RV |

## 3. 大需求标准流程

1. 理解现状：读代码，输出主键、权限、校验、参照路径
2. 写设计书：复制 `docs/ai-native/設計書模板/` 到 `docs/{機能}/`
3. 验收标准：复制并填写 `验收标准_模板.md`
4. 设计评审：按 `review.mdc`，无 Blocker 后再开发
5. 功能开发：Java / Vue / SQL / locale 最小改动
6. 实现评审：设计书和代码 diff 对照
7. 单元测试：Maven / frontend build / 回归矩阵 / 单体 Case（`単体テスト項目_{機能}.xlsx`）同步
8. 联调验收：E2E 或人工 case，填写结合测试大纲
9. PR：按 `.github/pull_request_template.md`，只写业务内容（不含 RV 结果 / BR・AC 编号 / `docs/` 路径）；验证与风险的详细记录留在本地

## 4. 常用入口

| 用途 | 路径 |
|------|------|
| 总索引 | `docs/ai-native/README.md` |
| Prompt 示例 | `docs/ai-native/Prompt模板.md` |
| 设计书模板 | `docs/ai-native/設計書模板/README.md` |
| 流程说明 | `docs/ai-native/開発フロー.md` |
| Agent 编排 | `docs/ai-native/Agent编排.md` |
| MCP / Skill | `docs/ai-native/MCP_Setup.md`、`docs/ai-native/MCP_Skill一覧.md` |
| UI / 术语 | `docs/ai-native/UI規範.md`、`docs/ai-native/用語辞書_日英.md` |

## 5. 完成前必须说清

- [ ] 参照了哪些既存代码 / 设计书
- [ ] 改了哪些文件，为什么改
- [ ] `review.mdc` 是否有 Blocker
- [ ] 运行了哪些验证命令，pass / fail / 未运行原因
- [ ] 是否更新了 `docs/{機能}/`
- [ ] 是否有残留风险或 Follow-up
