# 设计书 xlsx 导出（API設計書 / 画面設計書）

MD 是原稿。流程：`docs/{機能}/` 的 MD → 写一份中间文件 `docs/{機能}/design.json` → 跑脚本导出两份 xlsx。
单体 case 的脚本也直接读这份 `design.json`，所以 id 和 refs 要写全。

## 依赖

- Python 3.8 以上 + `openpyxl`（`python3 -m pip install -r requirements.txt`）。中间文件用 JSON，不需要 PyYAML。
- 画面设计书里放图片时，openpyxl 需要 `Pillow`（`python3 -m pip install pillow`）。不放图片可以不装；没装时会跳过图片、打印警告并在该位置写「（画像省略：文件名）」，其余照常生成。

## 用法

```bash
python3 tools/design-xlsx/export_api.py docs/{機能}/design.json   # → docs/{機能}/API設計書_{機能}.xlsx
python3 tools/design-xlsx/export_scr.py docs/{機能}/design.json   # → docs/{機能}/画面設計書_{機能}.xlsx
```

- `-o 路径` 指定输出文件；`--template 路径` 换模板（默认 `templates/` 下的空模板）。
- 默认输出到 JSON 所在目录，文件名可用 `api_doc.file_name` / `screen_doc.file_name` 改。**同名文件会被覆盖**，要保留旧版请先改名。
- 脚本运行前会先检查 JSON：缺 id/type/name/refs、id 重复会报错并停止，不生成 xlsx。
- 先试一下：`python3 export_api.py example/sample_design.json -o /tmp/a.xlsx`

## 从 MD 写 design.json

| design.json | 取自 MD |
|---|---|
| `apis[]` | `07_API設計書/*.md` 一个 API 一项：URL・HTTP、リクエスト/レスポンス表（或 openapi.yaml）、処理/ビジネスロジック → `steps[]` |
| `screens[]` | `06_画面設計書/*.md` 一个画面一项：概要・截图・変更点 → `layout`，画面項目表 → `items[]`，各操作/事件 → `events[]` |
| `refs` | 文中出现的 BR-xx / AC-xx / Q-xx，按元素分别填 |

MD 写法因人而异（表格列、语言、契约放在 openapi.yaml 等），没法可靠地自动转换，所以不提供 md2spec；由 Cursor 按下面的提示词转写，再人工对一遍。

**Cursor 提示词（复制使用）：**

<!-- [CMPF] 正文语言：xlsx 正文用日文、MD 原稿以中文为主，是本项目（对日）的约定；sheet 名和表头也是日文 -->
> 读 `docs/{機能}/` 下的 `07_API設計書/*.md`、`06_画面設計書/*.md`（以及它们引用的 openapi.yaml），按 `tools/design-xlsx/README.md` 的「JSON 格式说明」写出 `docs/{機能}/design.json`，参考 `tools/design-xlsx/example/sample_design.json`。要求：1) 只转写 MD 里有的内容，不自己补规格，MD 不清楚的地方写成 `{"kind":"text","text":"【要確認】…"}` 并在回复里列出；2) 正文用日文；3) 每个画面、画面项目、事件、API、处理步骤、检查项都要有唯一 id（`SCR-xxx`、`SCR-xxx-I01`、`SCR-xxx-E01`、`API-xxx`、`API-xxx-S01`、`API-xxx-S01-C01`）和 `refs: {"br":[], "ac":[], "q":[]}`；4) 写完跑 `python3 tools/design-xlsx/export_api.py` 和 `export_scr.py`，有报错就改 JSON 直到通过。

## JSON 格式说明

<!-- [CMPF] ID 写法：SCR-/API- 及 -I/-E/-S/-C/-B 后缀是本项目约定，脚本只查唯一性、不查格式；将来 ID 规则只在 project.json 定义一份，设计书和单体case 两个工具共读 -->
**追踪用的固定字段**（画面、画面项目、事件、API、处理步骤、检查项都必须有；单体 case 按这些对接）：

| 字段 | 说明 |
|---|---|
| `id` | 全文件唯一。建议：画面 `SCR-xxx`、项目 `SCR-xxx-I01`、事件 `SCR-xxx-E01`、API `API-xxx`、步骤 `API-xxx-S01`、检查项 `API-xxx-S01-C01`、分支 `API-xxx-S01-B01` |
| `type` | `screen` / `item` / `event` / `api` / `step` / `check`（`table` 行可选 `branch`） |
| `name` | 名称（不带编号） |
| `refs` | `{"br": ["BR-01"], "ac": ["AC-01"], "q": ["Q-1"]}`，没有就写空数组 |
| `title` | 可选。显示用标题；省略时自动生成「{序号} {name}（BR・AC・Q）」 |

**顶层**：`feature`（功能名，表紙）、`version`（MD 版本）、`system`（系统名，表紙）、`date`（`YYYY-MM-DD`，作成日）、`author`（作成者，默认「—」）、`history[]`（`version`/`date`/`author`/`content`，変更履歴）、`api_doc` / `screen_doc`（`id`：変更履歴的文书 ID，默认取第一个 API/画面的 id；`file_name`；`history` 可覆盖顶层）、`screens[]`、`apis[]`（没有就 `[]`）。

**apis[]**：`url`、`method`（名称栏显示为「name（method）」）、`summary`（API一覧的処理概要）、`sheet`（可选 sheet 名，默认「API（name）」）、
`request.items[]` / `response.items[]`：`name` 论理名、`physical` 物理名、`data_type`、`note`、`child: true`（缩进的子项）；`id`/`refs` 可选。
`steps[]`：追踪字段 + `body[]`，`body` 每个块用 `kind` 区分：

| kind | 字段 |
|---|---|
| `text` / `label` | `text`（正文 / 小标题） |
| `check` | `headers`（可选 4 列）、`rows[]`：追踪字段 + `condition` 错误条件、`note`、`error_code`（可选）。`name` 写检查项目 |
| `table` | `headers`（4 列，第 1 列是项番）、`rows[]`：`cols: [列2, 列3, 列4]`；作为分支追踪时加 `id`/`type:"branch"`/`name`/`refs` |
| `set` | `headers`（可选）、`rows[]`：`item`、`value`、`note`（登録/更新的设定值） |
| `sql` | `select[]`（`table`/`item`/`note`）、`tables[]`（`name`，JOIN 时加 `join`/`on`）、`where[]`（`item`/`op`/`value`，第 2 条起 `conj` 默认 AND）、`group[]`、`sort[]`（`item`/`order`） |
| `response` | `rows[]`：`item`、`value`、`level: 1`（上层项目） |
| `result` | `rows[]`：`item`、`value`（「処理結果コード ← 200(成功)」） |
| `gap` | `n` 空行数 |

**screens[]**：`sheet_suffix`（可选；多画面时默认用 name，sheet 名为「レイアウト（name）」等）、
`layout`：`summary`、`images[]`（`caption`、`path` 相对 JSON 文件、`width_px` 默认 1000）、`notes[]`（変更点，每条一行）；
`items[]`：追踪字段 + `group`（分组，连续同组只在第一行写，后面写 `""`，会自动合并）、`widget` 论理项目种别（见模板「各種凡例」）、`physical`、`event` 操作详细（处理名）、`fixed` 固定/可変、`io`、`required`、`validation`、`max_length`、`min`、`max`、`unit`、`format`、`initial`、`sort`（默认「-」）、`remarks`；
`params[]`：`name`、`note`（起動パラメータ）；
`events[]`：追踪字段 + `steps[]`，块的 `kind`：`step`（`text` 步骤标题）、`text`、`ref`（`text`、`see` 参照说明）、`api`（`api` 显示名、`api_id`、`rows[]`：`item`/`io`/`value`/`note`）、`params`（画面迁移参数，`rows[]` 同上）、`display`（`rows[]`：`group`/`item`/`state`/`value`/`note`）。块里可以带 `id`/`refs`，渲染时忽略，单体 case 可用。

## 文件

<!-- [CMPF] 版式：templates/*.xlsx 是按 CMPF 样本做的；模板本身不加标注 -->
`export_api.py` / `export_scr.py` 渲染器；`tpl.py` 共通（套模板行样式、合并、JSON 检查）；`templates/` 空模板（只有表头和版式）；`example/` 虚构示例。
模板的正文行是渲染时复制样式用的原型行（行号写在 export_api.py 开头的常量和 export_scr.py 里），改模板时不要增删这些行。
