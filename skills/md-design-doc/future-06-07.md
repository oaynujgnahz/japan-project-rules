# Future 06 / 07 + 按功能分目录

> Future 出处：[Markdown設計ドキュメント規約](https://future-architect.github.io/arch-guidelines/documents/forMarkdown/markdown_design_document.html)

## 1. 项目目录（先于写文执行）

**每个功能在仓库根下的 `docs/` 中独占一个文件夹。** 所有该功能的設計書、openapi、校验一覧均放在此文件夹内。

```text
{repo-root}/                    # 项目主目录
└── docs/
    └── {機能フォルダ}/         # ← 按功能新建，名称与业务/菜单一致
        ├── README.md
        ├── 機能設計書.md       # 単文件（可选）
        ├── 05_UI設計/
        ├── 06_画面設計書/
        │   └── SCR-{id}_{名称}.md
        ├── 07_API設計書/
        │   ├── openapi.yaml
        │   └── API-{id}_{名称}.md
        └── {对象}_校验一覧.md
```

**Agent 动作**：写文档前 `mkdir -p docs/{機能}/{06,07}_…`（按需）；禁止默认写到 `docs/` 根。

### README.md（每个機能文件夹必备）

```markdown
# {機能名}

| 項目 | 内容 |
|------|------|
| 文档/API/画面编号 | … |
| 对象范围 | … |

## 文档一覧

| 文件 | 说明 |
|------|------|
| [機能設計書.md](./機能設計書.md) | 全栈単文件（若有） |
| [06_画面設計書/](./06_画面設計書/) | 画面行为設計 |
| [07_API設計書/](./07_API設計書/) | OpenAPI + API 処理設計 |
```

## 2. Future 职责分离（06 / 07 / 05）

| 文档 | 路径 | 写什么 | 不写什么 |
|------|------|--------|----------|
| **05_UI設計** | `docs/{機能}/05_UI設計/` | Figma、画面遷移、レイアウト | API 処理詳細 |
| **06_画面設計書** | `docs/{機能}/06_画面設計書/` | API 呼出、イベント、バリデーション | Figma 見た目 |
| **07_API設計書** | `docs/{機能}/07_API設計書/` | OpenAPI + **完整ビジネスロジック**（BL-00～）+ DB | openapi 已写死的参数字段；BL 不得仅写类名 |

**広い表**：数十画面項目 → Excel/Figma；MD 引用路径写在本機能文件夹内。

## 3. 図

- シーケンス：**PlantUML** `!theme toy` 或 Mermaid
- システム構成：draw.io（`.drawio.svg`）可放在 `docs/{機能}/` 下

## 4. CMPF 遗留

| 旧路径 | 新路径（推荐） |
|--------|----------------|
| `docs/PCF算定_Excel取込出力_設計書.md` | `docs/PCF算定_Excel取込/機能設計書.md` |
| `docs/PCF算定_Excel取込_表格チェック一覧.md` | `docs/PCF算定_Excel取込/PCF活動量情報_校验一覧.md` |

迁移时保留旧文件或加 README 重定向，由用户决定；**新規一律用功能文件夹**。
