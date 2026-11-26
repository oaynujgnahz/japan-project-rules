# 团队 Skills 安装指南

Cursor Agent 在 `workflow.mdc` 中引用的 Skills **不在 {{system_name}} 仓库内**，需每人安装一次（或团队统一分发）。

> 未安装的 Skill：**跳过并在回复 / RV 中注明**，按下文「C. 仓库内速查」执行，不视为 Blocker。
> 规则仓库 `japan-project-rules` 的 `install.sh` 会把 `md-design-doc`、`{{name}}-report-file-io` 安装到 `~/.cursor/skills/`；`verification-before-completion`、`review-bugbot`、`review-security` 不在规则仓库内（可选）。

## 必装（{{system_name}} 开发）

| Skill | 用途 | 安装 |
|-------|------|------|
| **{{name}}-report-file-io** | Excel/PPT/PDF/CSV 取込出力、Content-Disposition | 见下 |
| **md-design-doc** | Markdown 設計書（Future 06/07） | 见下 |

## 安装方式（任选其一）

### A. 从已有同事复制

```bash
# Cursor（示例路径，以本机为准）
mkdir -p ~/.cursor/skills
cp -r /path/to/shared/{{name}}-report-file-io ~/.cursor/skills/
cp -r /path/to/shared/md-design-doc ~/.cursor/skills/
```

### B. Codex 路径

```bash
mkdir -p ~/.codex/skills
# 同上复制 {{name}}-report-file-io
```

### C. 仓库内速查（无完整 skill 时）

Agent 仍受 `.cursor/rules/` 约束；以下为核心要点：

**文件 I/O**

- 先 `rg` 搜同类 download/upload/template
- 对齐 Content-Type、UTF-8 文件名、classpath 模板
- 取込：扩展名、sheet 名、行级错误行号
- 前端：blob 下载、FormData 上传、locale 同步

**設計書**

- 一功能一文件夹：`docs/{機能}/`
- `06_画面設計書/` + `07_API設計書/` + `openapi.yaml`
- 范例：`docs/PCF算定_Excel取込/`

## 推荐可选 Skills

| Skill | 环节 |
|-------|------|
| `verification-before-completion` | 单元测试阶段宣称完成前 |
| `review-bugbot` | PR 大变更 |
| `review-security` | auth/SQL/配置 |
| `brainstorming` | 新功能 理解现状 / 写设计书 |

## 团队统一

建议负责人维护 **内部共享盘 / git 子模块**，版本与 {{system_name}} rules 同步更新；更新后在 `docs/ai-native/README.md` 注明版本日期。
