# AGENTS.md

This file is the working guide for AI coding agents in this repository. Keep it concise, accurate, and updated as new project rules are discovered.

## 本地专用（禁止提交）

本仓库由甲方管理。本规则体系仅在本地使用，**甲方不可见**：

<!-- [CMPF] e2e/、scripts/、mvn8 是 CMPF-SRC 特有的本地文件和目录；将来由项目配置的本地专用清单替换 -->
- 下列文件/目录**禁止 commit / push**：`AGENTS.md`、`.cursor/`、`.github/pull_request_template.md`、`docs/`、`e2e/`、`scripts/`、`mvn8`
- 本地 `.gitignore` 中追加的 `/docs/` 等忽略设置为本地改动，**`.gitignore` 本身也不得提交**；提交由用户人工选择文件进行
- 提交内容（commit message、PR 说明、代码注释、JUnit 方法名 / `@DisplayName`）中**不得出现**：BR / AC / Q 编号、`docs/` 路径、设计书名、RV checklist、bot 分工；需要说明时用业务语言
- RV 结果、测试基线、回归矩阵只留在本地或团队群，不贴进 PR
- 提交前按 `review.mdc` §提交前扫描 检查暂存区
- 下文中「提交到 Git」「同一 PR」等表述均按本节解释为「本地留存、与代码同一任务内更新」

## 与 Cursor 的关系（团队协作必读）

| 机制 | Cursor 是否使用 | 团队推荐 |
|------|-----------------|----------|
| **`.cursor/rules/*.mdc`** | 是，Project Rules，可 `alwaysApply` / 按 glob 生效 | **主机制**：本地专用，不提交（见上节） |
| **`AGENTS.md`（本文件）** | 官方支持根目录与子目录自动注入 | **补充**：人类可读完整指南；细节以 Rules 为准 |
| **`docs/ai-native/`** | 否（需 Agent 读取或 `@` 引用） | 流程与编排文档，给人和 Orchestrator 看 |

<!-- [CMPF] 画面改修 Rules 分层（frontend/、06_画面設計書/、Vue/Naive）属 CMPF 技术栈和 PPT 优先流程 -->
**Rules 分层（画面改修）**

| 文件 | 注入时机 | 内容 |
|------|----------|------|
| `cmpf-core.mdc` | 始终 | 3 条硬规则摘要 |
| `ppt-first-ui.mdc` | 编辑 `frontend/` 或 `06_画面設計書/` 时 | 差异表、优先级、PR 拆分、**PPT 再验证理解纠错 Gate** |
| `frontend-vue.mdc` | 编辑 `frontend/**/*.{vue,ts,tsx}` 时 | Vue/Naive 实装规范 |

Cursor [官方文档](https://cursor.com/docs/context/rules) 将 `AGENTS.md` 列为 `.cursor/rules` 的简化替代。实践中偶有未自动注入的情况（Settings 里能看到但上下文里没有）；若发现 Agent 未遵守，可在对话开头 `@AGENTS.md`，或依赖已提交的 `cmpf-core.mdc`（`alwaysApply: true`）。

**维护原则**：硬性边界、按文件类型约束 → 写进 `.cursor/rules/`；项目结构、命令、流程索引 → 保留在本文件。

<!-- [CMPF] CO2MOS AI 方針、用語辞書_日英.md、UI規範.md、docs/ai-native/ 下的文档属 CMPF 专属资料 -->
## AI Native 基础整备

CO2MOS AI 本格運用方針に基づく開発工程整备。详细流程、Agent 角色、MCP/Skill 映射见：

- **索引**：`docs/ai-native/README.md`
- **Cursor Rules**：`.cursor/rules/*.mdc`（`cmpf-core.mdc` 全局生效）
- **术语**：`docs/ai-native/用語辞書_日英.md`
- **UI**：`docs/ai-native/UI規範.md`

新功能开发：先读 `docs/ai-native/開発フロー.md`，实装前必须理解既存逻辑并对照 `docs/{機能}/` 设计书。

<!-- [CMPF] 本节整节为 CMPF 项目概要：Java 8 / Spring Boot 2.5.14 / Vue 3、carbon-parent 与各模块、manifests 和 Azure Pipelines；将来由项目配置替换 -->
## Project Overview

- CMPF is a multi-module Java 8 / Spring Boot 2.5.14 project with a Vue 3 + TypeScript + Vite frontend.
- Root Maven parent: `pom.xml`, artifact `carbon-parent`.
- Maven modules:
  - `common`: shared Java utilities, i18n resources, common dependencies.
  - `carbonapi`: main carbon/PCF API service, report/export logic, MyBatis mappers, SQL resources.
  - `taskapi`: task API service.
  - `userapi`: user/account API service, Keycloak-related dependencies.
  - `message`: socket/message service.
  - `frontend`: Vue UI module, also built by Maven through `frontend-maven-plugin`.
  - `report`: JaCoCo aggregate coverage module.
- Deployment assets live under `manifests/` and Azure pipeline files at the repository root.
- The project contains Chinese, Japanese, and English documents/resources. Preserve existing language and terminology in nearby files.

<!-- [CMPF] 本节整节为 CMPF 目录结构（com.ntt.cmpf、carbonapi、frontend/src、locale ja/en、manifests 各环境）；将来由项目配置替换 -->
## Repository Layout

- Backend Java source: `<module>/src/main/java/com/ntt/cmpf/...`
- Backend resources: `<module>/src/main/resources/`
- MyBatis XML mappers: `<module>/src/main/resources/mapper/`
- SQL change scripts: usually under `carbonapi/src/main/resources/sql/` or root-level `.sql` files.
- Frontend source: `frontend/src/`
- Frontend APIs: `frontend/src/apis/`
- Frontend views: `frontend/src/views/`
- Frontend router: `frontend/src/router/`
- Frontend stores: `frontend/src/store/`
- Frontend locale files: `frontend/src/locale/{ja,en}/`（`zh/` 目录存在但不在维护范围，新功能不需更新 zh）
- Kubernetes manifests: `manifests/{dev,dev-wf,stg,prd,mieco-*}/`

<!-- [CMPF] 本节整节为 CMPF 构建命令（./mvn8、Maven 模块、npm、Node v16.14.0、naive-ui patch）；将来由项目配置的 BUILD_CMD 等替换 -->
## Common Commands

Run commands from the repository root unless noted.

### Backend / full Maven build

Use the repository-local `./mvn8` wrapper for backend Maven commands so Maven runs with the project Java 8 JDK without changing the global Java default. It auto-detects Java 8 (`/usr/libexec/java_home -v 1.8`) and `mvn` on PATH; otherwise set `JAVA8_HOME` / `MAVEN_BIN`:

```bash
./mvn8 clean package
```

The root `pom.xml` sets `skipTests` to `true` by default. When tests matter for a change, override it explicitly:

```bash
./mvn8 test -DskipTests=false
```

To build or test a single backend module plus required dependencies:

```bash
./mvn8 -pl carbonapi -am package
./mvn8 -pl taskapi -am test -DskipTests=false
./mvn8 -pl userapi -am test -DskipTests=false
```

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run build
npm run serve
```

Frontend notes:

- Node `v16.14.0` and npm `7.6.0` are configured in `frontend/pom.xml` for Maven builds.
- `npm run build` uses `node --max_old_space_size=4096`.
- `postinstall` runs `patch-package`; preserve `frontend/patches/naive-ui+2.35.0.patch`.

## Verification Expectations

- For Java changes, run the narrowest relevant Maven command first. Use `-pl <module> -am` for module-scoped work.
- For frontend changes, run `npm run build` from `frontend/` when practical.
- For route, API, locale, or UI changes, check related files together: API wrapper, view/component, router, store, and locale entries.
- For SQL or mapper changes, verify corresponding Java mapper/entity/service usage and keep XML mapper result mappings aligned.
- If a command cannot be run because of local environment, time, or missing services, report that clearly with the reason.

## Coding Rules

- Follow existing patterns in the touched module before introducing new abstractions.
- Keep changes focused on the user request. Do not perform drive-by refactors, formatting churn, or unrelated cleanup.
<!-- [CMPF] Java 8、Spring Boot 2.5.x、后端依赖栈（MyBatis、PostgreSQL、Keycloak 等）、com.ntt.cmpf 包结构属 CMPF 技术栈 -->
- Java target is Java 8. Do not use newer language features.
- Spring Boot version is 2.5.x. Prefer existing project conventions over upgrading dependencies.
- Backend commonly uses Lombok, MapStruct, MyBatis/MyBatis Plus, PageHelper, PostgreSQL, Keycloak, Redis, and SendGrid. Match the local pattern in the module being edited.
- Preserve existing package structure under `com.ntt.cmpf`.
<!-- [CMPF] 对日项目要求：注释写日文或英文、禁止中文注释，以及 .cursor/hooks 中文注释检查 -->
- This is a Japan-oriented project. New code comments should be Japanese when practical, or English when Japanese would be unclear. Do not add Chinese comments to source code. Project hook: `.cursor/hooks/` scans agent edits for Simplified-Chinese comments (see `.cursor/hooks/README.md`). The hook runs automatically only inside Cursor; agents editing outside Cursor must run it manually per edited file (see `java-backend.mdc` §注释).
- Name new feature-specific classes after the feature/business scope they actually serve. Avoid reusing broad domain prefixes such as `Ghg` for emission result PPT/export helpers unless the class is genuinely shared with that existing GHG-specific domain.
- Do not edit generated or template-like files unless the task explicitly requires it.
- Do not commit secrets, real credentials, private keys, or production-only values. Be especially careful with `application-*.yml`, `configmap-secret.yml`, keystores, and deployment manifests.
- Avoid adding new production dependencies unless there is a clear need and the user agrees.

<!-- [CMPF] 本节整节为 CMPF 前端技术栈：Vue 3 + Naive UI、只维护 ja/en 不维护 zh、classic/new 路由；将来移到技术栈配置 -->
## Frontend Rules

- Use the existing Vue 3 + TypeScript + Vite style.
- Prefer existing components in `frontend/src/components/` and established API wrappers in `frontend/src/apis/`.
- Keep locale changes synchronized across **`ja` and `en`** when the UI text is user-visible. Do **not** add or update `frontend/src/locale/zh/` for new work unless explicitly requested.
- Keep router changes consistent with `frontend/src/router/index.ts`, `routes-new.ts`, and `routes-classic.ts`.
- Use existing Naive UI patterns and project styling conventions.
- Do not remove or bypass the `patch-package` setup for Naive UI.

## Backend Rules

- Keep controller, service, mapper, DTO/entity, and XML mapper changes aligned.
- For new database-backed behavior, check whether SQL scripts, mapper XML, Java model classes, and frontend API types all need updates.
- Prefer adding focused unit or integration tests where the surrounding module already has test patterns.
<!-- [CMPF] carbonapi 报告生成、PCF 等日文业务术语属 CMPF 专属 -->
- Be careful with Excel, PDF, PPT, and report-generation code in `carbonapi`; these flows are sensitive to fonts, templates, coordinates, and generated output.
- Preserve Japanese business terms in PCF, electricity service, report, and reduction-related features unless the user requests translation.

<!-- [CMPF] 本节整节为 CMPF 部署环境：manifests、azure-pipelines、prd / mieco-prd；将来由项目配置替换 -->
## Deployment And Environment Rules

- Treat `manifests/` and `azure-pipelines-*.yml` as environment-sensitive.
- When changing manifests, compare the corresponding environment variants and update all required environments intentionally.
- Do not change production manifests (`prd`, `mieco-prd`) unless explicitly requested.

## Agent Behavior

<!-- [CMPF] PPT 再验证流程属 CMPF（需求方以 PPT 提供要件）；详见 ppt-first-ui.mdc -->
- For 画面改修 / PPT 对照：若用户要求「按 PPT 再次验证」且 Agent 承认此前理解错误 → 在**回复**中简述纠错；仅是设计书写错、不改变 BR / AC / 画面事件 / API 契约 → 可直接先改设计书再改代码；涉及上述任一项变更 → 先列为要確認事項（Q），用户或需求方确认后再改设计书和代码（`ppt-first-ui.mdc` §理解纠错 Gate）。
- Reply to the user in Chinese by default. Use another language only when the user asks for it, when quoting source text, or when preserving nearby project terminology.
- Think before coding: state assumptions, ambiguities, and tradeoffs when they affect implementation.
<!-- [CMPF] cmpf-report-file-io skill 为 CMPF 专属 -->
- For CMPF file import/export work, use the personal `cmpf-report-file-io` skill when available (if unavailable, read the existing implementation and note it in the reply). It covers downloads, templates, Excel/CSV/PPT/PDF/JSON/DOCX output, upload/取込 validation, and frontend blob/FormData flows.
<!-- [CMPF] 设计书目录结构（Future 06/07）、06_画面設計書 / 07_API設計書、単体テスト模板路径属 CMPF；将来由项目配置的模板路径替换 -->
- For 設計書 authoring, use the `md-design-doc` skill; output goes under `docs/{機能}/` per Future 06/07 structure.
- **During feature development**, document implementation logic in the matching `06_画面設計書` / `07_API設計書` / `詳細設計書` / `验收标准` entries—not only in code. See `.cursor/rules/design-docs.mdc` §开发时设计留存 and `workflow.mdc` (功能开发文档 gate).
- When creating feature docs, generate `docs/{機能}/単体テスト項目_{機能}.xlsx` from `docs/ai-native/単体テスト項目_テンプレート.xlsx`; synchronize behavior changes with its Cases while keeping `試験観点` fixed. For typo/format-only edits, record `単体Case: N/A（非行为变更）`.
<!-- [CMPF] 用語辞書_日英.md、只同步 ja/en 属 CMPF 多语言要求；将来由项目配置的语言列表替换 -->
- For locale changes, follow `docs/ai-native/用語辞書_日英.md` and `.cursor/rules/i18n-locale.mdc`; keep **ja/en** in sync only.
- Simplicity first: implement the smallest solution that satisfies the request.
- Surgical changes: every changed line should trace back to the task.
- Goal-driven execution: define how the change will be verified, then run the relevant checks when practical.
- Work with the user's existing uncommitted changes. Never revert or overwrite unrelated changes unless explicitly asked.

## Continuous Maintenance

- When an interaction reveals a durable project fact, command, convention, recurring pitfall, or verification step, **propose** the change to this `AGENTS.md` or `.cursor/rules/` (as a diff) and apply it only after the user approves. Multiple agents work in this repo; do not edit rule files on your own.
- Do not add one-off task details, temporary debugging notes, or stale assumptions.
- Keep updates short and specific. Prefer replacing inaccurate guidance over appending duplicates.
- If a new rule applies only to a subdirectory, consider creating a nested `AGENTS.md` there instead of bloating this root file.

## Before Finishing A Task

- Before final verification, check touched code for unused imports, unused parameters, unused overloads/wrapper methods, and stale helper methods introduced or made obsolete by the change. Remove them when safe.
- Before final verification, check touched feature code for unused classes, obsolete utility entry points, and empty placeholder classes. Remove them when they are not referenced and no longer serve a clear project purpose.
- Summarize changed files and the reason for each change.
- Report verification commands and whether they passed, failed, or were not run.
- Mention any residual risk, environment dependency, or follow-up needed.
- If this file was updated during the task, call out the new guidance briefly.
