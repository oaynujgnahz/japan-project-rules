---
name: unit-test-xlsx
description: >-
  根据功能设计书（docs/{機能}/ 的 MD 或設計書 xlsx）与现有代码，按项目模板生成/同步
  単体テスト項目_{機能}.xlsx（单体测试 Case 文档）时使用。
---

# 単体テスト項目（单体 Case）Excel 生成

项目专属值读 init.sh 生成的本地 project.json（脚本用 `--config` 指定；`projects/cmpf/project.json` 只是只读示例，不能直接用），按节取值，不要把这些值写进本文件，也不要写死在命令里：
- `unit_test`：模板路径、locale 文件名候选、試験観点、表示タイプ、样式与 sheet 位置、正文语言、错误文言格式、台账文件名模式、追溯 ID 正则
- `i18n`：locale 目录、语言
- `ids.error_code`：错误码格式；`ids.prefixes`：追溯 ID 前缀
- 顶层 `ledger_dir`：确认事项台账目录

本仓库 `tools/unit-test-xlsx/` 是生成工具，以仓库版为准。`gen_ut_xlsx.py` / `read_design.py` 用 `--config <init 生成的 project.json>` 读配置（错误码格式、画面/API ID 格式、locale 目录、语言、各语言文件/文言书式/语言名、模板路径），没有配置、示例配置、缺键都会报错退出；`--template`、`--locale-dir` 只在要覆盖时传。

规则正文以 `.cursor/rules/unit-test-case-docs.mdc` 为准。

## 核心规则

1. 文件名为 `docs/{機能}/単体テスト項目_{機能}.xlsx`，必须从项目模板生成（路径见 配置 `unit_test.template`）。sheet 名、顺序、隐藏状态与 配置 `unit_test.sheets` 一致；`試験観点` 禁止修改（内容、公式、样式、数据验证，字节级不变）。采用 OOXML 最小修改，不要用 openpyxl 另存（会丢扩展数据验证），使用 `gen_ut_xlsx.py`。
2. 映射：布局、显示、多语言 → `画面レイアウト判定`；操作、API 流程、分支、权限、DB 结果、初期表示 → `画面操作処理判定`；输入校验、边界值、错误消息 → `項目チェック判定`。DB 写入判定 sheet（见 配置 `unit_test.sheets.hidden`）保持隐藏、不放 Case；DB 结果写进操作 sheet 的予想結果。
3. B 列观点只用 配置 `unit_test.viewpoints` 列出的词；`unit_test.viewpoints_required` 默认必覆盖，其余只在功能涉及时使用。
4. 设计书里每个需覆盖的 ID（画面项目、事件、遷移、API 分支、业务规则、验收标准、错误码）都要有 Case。每个错误码按 配置 `i18n.languages` 各写一条。撤回的编号（欠番）不得复用、不得当作覆盖。
5. 予想結果必须可判定：写出具体画面表示、值或 DB 结果。禁止只写「正常」「OK」「仕様通り」「同上」等（禁用词以工具 lint 和 `unit-test-case-docs.mdc` 为准）。错误文言以代码里的 locale 为准（目录和语言见 配置 `i18n`，文件名见 `unit_test.locale_files`），不从设计书抄。设计书与代码不一致时不自行编写，列入要確認事項并建议更新设计书。错误消息格式用 配置 `unit_test.error_message_templates`。
6. 用业务语言描述，正文不写函数名、源码路径。分组行写设计书 ID，便于追溯。每条 Case 标注 配置 `ids.prefixes` 里用于追溯的 ID（BR/AC；设计未定的用 Q）。
7. 結果列（判定、判定履歴、担当者、最新結果、BUG票ID）生成时一律留空，由实际执行测试的人填写。
8. 正文语言见 配置 `unit_test.body_lang`；画面文言、消息保持原文，不翻译。
9. 本流程只出 Case 文档（xlsx），不写测试代码。除非用户明确要求，不改应用源码、不 commit。
10. 写 Case 和要確認事項前，先查项目的确认事项台账（配置顶层 `ledger_dir`，各功能一个文件，文件名见 `unit_test.ledger_file_pattern`）。已经决定的直接按决定写，不再问。只记用户确认过的事，不记推测，不写密钥。
11. 同步回本地 `docs/{機能}/` 时，只放 `単体テスト項目_{機能}.xlsx`；PDF 和对照表是内部检查产物，不放回。放之前先问，不覆盖已有文件，新建版本文件夹。

## 步骤

1. **收集输入**：功能名 `{機能}`、设计书（`docs/{機能}/`，或设计书产出的 `設計書.xlsx` / `design.json`）、PPT（可选）。项目仓库只读。已有 `単体テスト項目_{機能}.xlsx` 时先读它，只增改受影响的行，不重排、不删已有判定结果。先查台账。
2. **读设计书**：`python3 tools/unit-test-xlsx/scripts/read_design.py <src> --ids --config <项目配置>` 得到必须覆盖的 ID 清单；`--dump` 读正文。可多个来源。
3. **读代码核对（只读）**：错误码实际发出的位置与条件、按钮活性/非活性、上传限制、权限常量。文言取 配置 `i18n.locale_dir` 下、`unit_test.locale_files` 列出的文件。不要读含密钥的配置，不要运行或输出 `git remote -v`。
4. **写 cases.json**：有 `design.json` 时先 `read_design.py design.json --draft -o draft.cases.json` 起草，再补全初期化、境界値、必填、权限、多语言、非同期等，并把 TODO 全部改成可判定的期待。错误码行写 `"code"`（格式符合配置 `ids.error_code`，脚本只认这个正则），生成器按 `unit_test.error_message_templates` 展开各语言行。格式见 `tools/unit-test-xlsx/cases.schema.json`。
5. **生成 + lint**：`python3 tools/unit-test-xlsx/scripts/gen_ut_xlsx.py cases.json --config <项目配置> -o <输出xlsx> --design <设计书> --trace-report <对照表>`。模板按 `unit_test.template`（不用另传 `--template`）。逐条处理警告：观点不在清单、予想結果不可判定、缺 ref、重复行、函数名混入、正文语言混入、设计书 ID 未覆盖、错误码缺某个语言、设计书错误码在 locale 不存在（→ 要確認事項）。
6. **自检**：用 openpyxl 重新打开（只读，不保存）检查各 sheet 内容；转 PDF 后抽几页看排版（分组行、行高、表头无振假名混入）。确认 `試験観点` 与隐藏 sheet 未被改动（生成器已做字节校验），項目総計的 CASE 数与下拉范围与实际行一致。
7. **交付**：交出 xlsx（可附对照表供内部检查）。同步回本地前先问，只放 xlsx，不覆盖，新建版本文件夹。回复里写：各 sheet Case 数、未覆盖的设计书 ID、要確認事項、建议用自动化测试覆盖的 Case。纯错字、链接或排版变更回复 `単体Case: N/A（非行为变更）`，不改 xlsx。

## 覆盖与评审

- 每个新增或修改的可测试行为至少一条 Case。
- 改既有功能时：设计书「改修前挙動」中未标「変更」的每一格，各写一条「与改修前相同」的回归 Case。
- 标明每条 Case 由单元测试覆盖、只能联调确认，还是手动执行（在回复里写；cases.json 可留 `verify` 备忘，生成器不读）。
- 测试数据名称加可识别前缀（如 `UT{機能}_`），删除脚本与插入脚本一起准备，执行前给用户确认；不删除既有数据。
- 完成前确认：xlsx 可打开；sheet 结构有效；予想結果全部可判定；错误文言与 locale 原文一致；結果列为空；汇总、公式、下拉未损坏。
