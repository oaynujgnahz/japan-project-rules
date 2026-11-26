---
name: md-design-doc
description: >-
  Authors and revises software design documents (設計書) in Markdown: one folder per
  feature under project docs/, Future 06/07 structure, OpenAPI split, project metadata.
  Use when the user asks for 設計書, design doc, 機能設計, API設計, 画面設計,
  requirements-to-design, or writing/updating `.md` design documentation.
---

# Markdown 設計書 Authoring

Write **implementation-ready** design documents. **Every 機能 gets its own folder under the repository `docs/` directory**; all generated files for that feature go only inside that folder.

Structure follows [Future Markdown 設計ドキュメント規約](https://future-architect.github.io/arch-guidelines/documents/forMarkdown/markdown_design_document.html) for **§06 画面** and **§07 API**.

## 按功能分目录（必守）

**规则**：在**项目根目录**下的 `docs/` 中，**每个功能单独一个子文件夹**；新建或更新設計書时，先确认/创建该文件夹，再把文件写入其中。**禁止**把某功能的設計書直接散落在 `docs/` 根下（除非用户明确要求迁移前的兼容路径）。

### 路径约定

```text
{repo-root}/
└── docs/
    └── {機能フォルダ}/          # 一機能一桶，与菜单/领域名一致
        ├── README.md            # 機能索引（编号、文件一覧、范围）
        ├── 機能設計書.md        # 単文件模式（模板 A，可选）
        ├── 05_UI設計/
        ├── 06_画面設計書/
        ├── 07_API設計書/
        │   └── openapi.yaml
        └── {对象}_校验一覧.md   # 补充文（可选）
```

### 文件夹命名

| 规则 | 示例 |
|------|------|
| 与功能/画面领域一致，可读 | `{業務領域}_{機能名}`（如 `{業務}_Excel取込`、`{帳票名}出力`） |
| 不用模块名代替功能名 | ❌ `{module}`（构建模块名） ✅ `{業務領域}_{画面名}` |
| 同一功能只保留一个文件夹 | 勿拆成 `docs/{業務領域}/` 与 `docs/{機能名}/` |

### 创建时机

1. 写任何設計書前：检查 `docs/{機能フォルダ}/` 是否存在，不存在则**先建目录**（含 `06_` / `07_` 子目录，若用拆分模式）。
2. 同一功能的后续文档（校验一覧、openapi、单画面 MD）**只追加到该文件夹**，不新建平行路径。

详见 [future-06-07.md](future-06-07.md)。

## When to Apply

- New feature: 建 `docs/{機能}/` → 背景 → 構成 → **06 画面** → **07 API** → DB/校验
- Split: `docs/{機能}/06_画面設計書/` + `docs/{機能}/07_API設計書/`
- Monolithic: `docs/{機能}/機能設計書.md`（§3=06、§4=07）
- Update: 只改对应 `docs/{機能}/` 内文件

## Workflow

1. **Identify 機能** → 确定 `docs/{機能フォルダ}/` 名称；**mkdir** 若不存在
2. **Clarify scope**: 文档/API/画面编号、版本、对象范围、「不在范围内」
3. **Choose layout**: Future 拆分（F+G）或 単文件（A）；在 README.md 注明
4. **Scan codebase**: Controller、Service、Vue、mapper、locale
5. **Draft** per [future-06-07.md](future-06-07.md)
6. **Self-check** [Quality checklist](#quality-checklist)
7. **Save** 全部路径以 `docs/{機能フォルダ}/` 为前缀（见下表）

| 产出 | 路径 |
|------|------|
| 索引 | `docs/{機能}/README.md` |
| 単文件設計書 | `docs/{機能}/機能設計書.md` |
| 画面 | `docs/{機能}/06_画面設計書/SCR-{id}_{名}.md` |
| API 契約 | `docs/{機能}/07_API設計書/openapi.yaml` |
| API 処理 | `docs/{機能}/07_API設計書/API-{id}_{名}.md` |
| 校验一覧 | `docs/{機能}/{对象}_校验一覧.md` |
| **処理フロー** | `docs/{機能}/処理フロー詳細.md`（推荐；业务语言逐步流程） |

## 業務記述・処理フロー（必守）

写 **触发 → 输入 → 处理 → 输出 → 边界** 时，遵守仓库内  
`docs/ai-native/設計書記述規範.md`：

- **主文**：业务语言；禁止函数名/ref 名堆砌（`rebuildX` → `mergeUserRows` 链）
- **処理フロー詳細.md**：跨画面/跨 Step 的完整数据流（产品/测试可读）
- **06 §11 / 07 §10**：同上结构；契约字段、DB 表、错误码可保留
- **理解现状摘要**：仅表主键 + 代码入口；流程链到処理フロー詳細
- **実装対照**：代码路径仅放附录

范例：`docs/{機能}/処理フロー詳細.md`（项目里已完成的范例见 `docs/ai-native/設計書記述規範.md`）

## Future 06 — 画面設計書（§3 或 `docs/{機能}/06_画面設計書/`）

**写**：API 呼び出し、イベント、パラメータ受渡し、バリデーション、親子组件协作、错误展示。  
**不写**：Figma 已有的見た目（色・レイアウト・控件外观）— 只链 `05_UI設計`。

| 小节 | 内容 |
|------|------|
| 関連ドキュメント | Figma / `05_UI設計` 路径；调用的 API-ID 列表 |
| 画面概要 | 目的、画面 ID、入口（菜单・打开条件） |
| 画面遷移 | Mermaid 或「详见 05_UI」 |
| 画面項目 | 项番表；**>~15 列或数十行 → Excel/Figma，MD 只引用** |
| イベント・操作 | 操作 → 触发 API → 参数 → 校验 → 反馈/遷移 |
| バリデーション | 前端规则；对应 messageKey |
| コンポーネント連携 | 親子画面职责、暴露的操作（**业务语**）；路径见 §11.2 実装対照 |
| i18n | locale 键（`ja` 原文） |

## Future 07 — API 設計書（§4 或 `docs/{機能}/07_API設計書/`）

**契約の正**：`openapi.yaml`（OAS 3.0.x）。MD **禁止**重复已写在 OpenAPI 的请求/响应字段表。

**每个 API-ID 的 MD**（プログラム設計）必填：

| 小节 | 内容 |
|------|------|
| 処理概要 | 为何需要、**処理フェーズ一览表**、错误码条件 |
| 処理シーケンス | PlantUML（`!theme toy`）或 Mermaid sequenceDiagram |
| **ビジネスロジック（完整）** | 见下节 **[API 业务逻辑完整度要求](#api-业务逻辑完整度要求必守)** |
| DB 項目 | **取得**（表+抽出条件）/ **登録** / **更新** |
| エラー処理 | Pattern、Description、recovery 或 messageKey 表 |
| 使用 SQL | SQL-01, …（项目习惯） |

### API 业务逻辑完整度要求（必守）

读者（含 Codex 验证）应能 **只读 API MD 的「ビジネスロジック」一章** 即理解端到端行为，**不得**仅写类名一览或「详见代码」。

每个 API 的 `## 3. ビジネスロジック` **必须**包含：

| 要素 | 要求 |
|------|------|
| **总览** | `BL-00`：INPUT → OUTPUT 一句话 + 编号主流程（≥6 步） |
| **分块编号** | `BL-01`、`BL-02`… 按**执行顺序**；每块有明确触发类/方法名 |
| **判断表** | 分支（新规/编辑、有数据/无数据、slide 取舍）用 **表格** 写清条件与结果 |
| **算式与规则** | 计算公式、格式化、排序、上限（如最多 8 年、Top4+その他）写 **明文** |
| **数据转换** | DTO→表示值（过滤、舍入、占位符 `-`）逐步列出 |
| **与其他 API/画面关系** | 若复用 Excel/分析画面逻辑，写明「与 XXX 相同条件」 |
| **伪代码** | 复杂分支用 `txt` 代码块；禁止空洞 bullet |
| **技术约束** | 仅在与业务验收相关时写（如「无 Scope3 则删 slide2」） |

**禁止**：

- 仅列 `Service.xxx()` 无说明
- 「业务逻辑见機能設計書」作为 API 文档的唯一指向（機能設計書可补充，不能替代）
- 把实现细节藏在「参见 XXX 类」而无规则描述

**推荐结构**（可复制到 templates）：

```markdown
## 3. ビジネスロジック
> 仅读本节即可理解本 API 行为。

### BL-00 总览
### BL-01 …（按处理顺序）
#### BL-01.1 子规则（可选）
```

**複数テーブル結合の応答**（検索 API 等）追加表：

| Parameter | Description | Settings | Note |
|-----------|-------------|----------|------|

- Description：OpenAPI 已写则可省略  
- Settings：来源表/实体  
- Note：加工・計算逻辑

**无 OpenAPI 时**（遗留功能）：在 MD 内写完整请求/响应表（项番・论理名・物理名・必须 ○△）。

## Document Conventions

### Metadata（全栈設計書）

```markdown
| 項目 | 内容 |
|------|------|
| 文档编号 | … |
| API 编号 | API-B-xx-xx-xx |
| 画面编号 | SCR-B-xx-xx-xx |
| 版本 | 1.00 |
| 作成日 | YYYY-MM-DD |
| 对象范围 | **仅** … |
| 機能目录 | `docs/{機能フォルダ}/` |
| UI 参照 | `docs/{機能}/05_UI設計/…` 或 Figma URL |
| API 契約 | `docs/{機能}/07_API設計書/openapi.yaml` |
```

### 必须记号

○ 必填 · △ 条件必填 · × 不传

### Diagrams

- 画面流 / API 流：`sequenceDiagram`
- 取込・批处理：`flowchart TD`
- Future 推荐批处理/API 詳細：PlantUML `!theme toy`

### Cross-references

- 機能内相对路径：`../07_API設計書/API-01_xxx.md`、`§4.2`
- 跨機能：`docs/{他機能}/…`（写明完整 repo 路径）
- OpenAPI：`docs/{機能}/07_API設計書/openapi.yaml#/paths/...`

## 単文件 ↔ Future 拆分（同一機能文件夹内）

| 単文件 `機能設計書.md` 章节 | 同機能下的拆分路径 |
|------------------------------|-------------------|
| §3 画面设计 | `06_画面設計書/` |
| §4 API 设计 | `07_API設計書/` + openapi |
| §5 DB | `08_データモデル/` 或 API MD 内 DB 項目 |
| 校验一覧 | `{对象}_校验一覧.md` |

**遗留路径**：仓库中已有的 `docs/{機能}_設計書.md`（根下平铺）可在改版时迁入 `docs/{機能}/`；新文档一律用功能文件夹。

## Quality Checklist

- [ ] 已使用 `docs/{機能フォルダ}/`，且该文件夹含 README.md（或说明为何単文件仅一个 md）
- [ ] 未把本機能文件写到 `docs/` 根或其他機能文件夹
- [ ] 06：未重复 Figma 見た目；含 API 呼び出し・バリデーション・操作流
- [ ] 07：openapi 与 MD 无重复字段定义；每 API 有処理概要・シーケンス・DB 項目
- [ ] 07：**ビジネスロジック完整** — 含 BL-00 总览、分块编号、判断表/算式；读者无需翻代码即可理解行为
- [ ] 広い表已拆到 Excel/Figma 或 05_UI
- [ ] 路径・messageKey 与代码一致
- [ ] 新规/编辑/异常分支齐全

## Anti-patterns

- 新機能設計書写在 `docs/` 根目录 — 必须 `docs/{機能}/`
- 多个機能共用一个文件夹 — 按功能拆分
- 在 06 写颜色/像素 — 应链 Figma
- 在 07 MD 复制 openapi 参数表 — 应 `参照 openapi.yaml`
- 数十行画面項目硬塞 MD 表 — Future 明确不推荐
- API ビジネスロジック只写类名/「详见代码」— 必须写完整规则与分支（见 [API 业务逻辑完整度要求](#api-业务逻辑完整度要求必守)）

## Additional Resources

- 目录与职责：[future-06-07.md](future-06-07.md)
- 模板：[templates.md](templates.md)（F=06、G=07、A=単文件）
- 示例：[examples.md](examples.md)
- 迁移目标结构：`docs/{機能}/機能設計書.md`；遗留（根下平铺）：`docs/{機能}_設計書.md`
