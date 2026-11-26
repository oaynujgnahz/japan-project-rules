---
name: design-doc-xlsx
description: >-
  根据要件 PPT + 项目现有代码，按设计书规范生成日式 Excel
  詳細設計書（.xlsx）和对外公司模板设计书时使用（多项目共用，项目差异取自 projects/{项目}/project.json）。
---
# 設計書 Excel 生成（多项目共用）

工具目录：规则仓库的 `tools/design-xlsx/`（下面的脚本路径都相对于它）；项目差异：`projects/{项目}/project.json`
- `RULES.md`：从仓库规范提炼的完整规则（**先读**）
- `read_pptx.py`：PPT → slides.md + 图片 + 嵌入文件
- `gen_design_xlsx.py`：JSON → xlsx（含 lint）；`--schema` 打印 JSON 骨架；`--blank --system <system_name>` 生成空模板；design.json 的 `meta.system` 必填（取 `design.system_name`）
- `templates/詳細設計書_テンプレート.xlsx`：内部詳細設計書空模板；`templates/画面設計書_模板.xlsx`・`API設計書_模板.xlsx`：对外公司模板（`export_scr.py` / `export_api.py`）
- `example/`：脱敏样例

## 项目参数（取自 project.json；个人环境的值放个人配置，不提交）
| 参数 | 配置键 | CMPF 的值（例） |
|---|---|---|
| 代码仓库（只读） | 个人配置 | 各人本地路径 |
| 需求 PPT 位置 | 个人配置 / 用户提供 | 用户提供 |
| 确认事项台账目录 | `ledger_dir` | 按项目配置 |
| 系统名 | `design.system_name` | `CMPF` |
| 错误码格式 | `ids.error_code` | `CMPF\d{4}-[EIW]` |
| locale 目录 | `i18n.locale_dir` | `frontend/src/locale` |
| 术语辞书 | `design.glossary` | `docs/ai-native/用語辞書_日英.md` |
配置里没有的值先读代码确认；还不明就写进要確認事項，不照 CMPF 猜、不自己编。

## 核心规则（详见 RULES.md）
1. 一功能一套：表紙→改訂履歴→目次→機能概要→要件対応表→現状分析→処理フロー→業務ルール→画面一覧→SCR-*（每画面一张）→API一覧→API-*（每 API 一张）→テーブル定義→チェック・エラー一覧→SQL一覧→受入基準→要確認事項→実装対照。
2. 主文用业务语言；函数名/变量名/文件路径只能出现在「実装対照」和「現状分析」。可以出现：API path、请求响应字段、DB 表列、画面物理名、组件类型、错误码、权限常量。
3. 每个处理场景固定块：目的→トリガー→入力→処理（编号步骤）→出力→境界・例外（+関連 BR/AC/API/slide）。
4. PPT 是画面布局的第一来源；每个 SCR 写「要件来源（PPT 文件 + slide/注釈）」；改修画面必须有 PPT vs 現状 差异表；不能从旧代码推断布局。
5. 每条设计可追溯：要件対応表 把 slide/注釈 → 设计 ID → 既存代码 → 状态（✅/⏳/△）对起来。PPT 没写但必须定的，写「slide X を設計で具体化」。
6. PPT 与代码冲突、PPT 不明确 → 不编造，写 要確認事項（问题/选项/影响/暂定方针/状态），设计按暂定方针写并标 Q 编号（只在内部詳細設計書和 MD 里）。
7. ID：SCR-B-xx-xx-xx、API-B-xx-xx-xx-xx、BR-xx、AC-xx、BL-xx、SQL-xx、F-xx、Q-x；错误码按 `ids.error_code`（含 -E/-I/-W），文言取代码 locale/ja。BR/AC/Q 编号不复用，删除的标「欠番」。
8. 受入基準每条可测试；i18n 只写 ja/en；术语按项目术语辞书。
9. 语言：sheet 名/表头/ID 日文；正文默认日文（用户要求可中文）；PPT 原文、错误 message、UI 文言不翻译。

## 确认事项台账
- 问用户之前、写要確認事項之前，先查台账 `{ledger_dir}/{機能}.md`；已决定的直接写进设计，不再问。
- 用户拍板后由当轮收尾的 bot 当场追加一行（ID、问题、决定、日期、来源）。只记用户确认过的事，不记推测，不写密码。

## 写作顺序与对外交付
- **中文 MD 先写**给用户确认；内容定稿后再出日文版。中文 MD 只给用户看；对外交付物是日文公司模板 xlsx（画面設計書 + API設計書）。两边都要保持最终版、内容同步。
- **对外 xlsx 禁止项**：不写 Q 编号、文件路径、行号、agent/bot 名，文件属性（作成者）也不留 agent 名；函数名只放「実装対照」。BR/AC 编号可以保留。
- **对外 xlsx 的生成**：项目仓库或规则仓库里有公司模板导出工具（如 `tools/design-xlsx/` 的 `export_scr.py` / `export_api.py` + `templates/`）就用它，从 design.json 导出；不要按功能复制一份构建脚本。用户另给公司模板就照模板填。模板里不留个人姓名、真实业务正文。
- **放回用户电脑**：放到 `docs/{機能}/` 前先问用户；新建 `v{版本号}_{YYYYMMDD}/` 子目录，不覆盖已有文件。

## 步骤
1. **收集输入**：PPT（用户提供的文件）、功能名、仓库（见项目参数）。代码只读，绝不改用户电脑上的文件。
2. **读 PPT**：`python3 read_pptx.py <pptx> -o <工作目录>/<機能>/ppt --render`，读 slides.md（文本框按位置排序、group 递归、表格转 Markdown、notes、①②注釈）；**一定要看 media/ 和 render/ 里的图**（UI 草图、Excel 格式截图都在图里）；embedded/ 里可能有 xlsx。
3. **读代码（理解现状，先做）**：只读执行 `rg`/`git log`/`cat`：同类后端入口（Controller/Service/Mapper/SQL）、前端画面与 API 调用、router、locale（ja/en）。也看 `docs/{機能}/` 是否已有 MD 设计书（有就以它为基础，冲突以 PPT 为准）。不要读 `.cursor/mcp.json`、`application-*.yml` 等含密钥文件；不要运行或输出 `git remote -v`（URL 里可能含 token）。
4. **查台账**，再写中文 MD 草稿给用户确认。
5. **写 JSON**：`python3 gen_design_xlsx.py --schema` 看骨架，参照 example/ 的脱敏样例。表格行可以用 list 或以表头为 key 的 dict；处理步骤给 list 自动编号。先填 現状分析、要件対応表，再写 処理フロー/画面/API，最后 チェック・受入基準・要確認事項・実装対照。
6. **生成 + lint**：`python3 gen_design_xlsx.py design.json -o <工作目录>/<機能>/<機能>_設計書.xlsx`。逐条处理 lint 警告（函数名混入主文、流程块缺项、SCR 缺 PPT 来源、改修缺差异表、API 缺 BL、ID 格式、要確認缺状态、无 AC）。对外公司模板 xlsx 用导出工具生成，并确认没有 Q 编号、路径、行号、agent 名。
7. **自检**：openpyxl 重新打开确认 sheet 列表/内容；`soffice --headless --convert-to pdf` + `pdftoppm` 抽几页看排版。按 RULES.md §7 的设计书 RV 清单自查（API/字段/校验/DB/主键分支/权限与既存一致）。
8. **交付**：交付 xlsx；需要放回用户电脑时按上面「放回用户电脑」的规则。回复里列出：sheet 数、要確認事項（Q 列表）、⏳/△ 项、以及提醒单体测试 Case（`単体テスト項目_{機能}.xlsx`）需由开发同步。不写代码、不开 PR、不 commit。
