# 単体テスト項目 xlsx 生成ツール（unit-test-xlsx）

设计书（`docs/{機能}/`）→ 人或 Cursor 写 `cases.json` → `gen_ut_xlsx.py` 按仓库模板生成 `単体テスト項目_{機能}.xlsx`。
规则以 `.cursor/rules/unit-test-case-docs.mdc` 为准，本工具只负责「按规则落到模板里」和机械检查。

## 文件

<!-- [CMPF] 模板：templates/単体テスト項目_テンプレート.xlsx 是 CMPF 单体模板（6 sheet：試験観点/項目総計/画面レイアウト判定/画面操作処理判定/項目チェック判定/DB書き込み判定(隐藏)），sheet 名・列对应・行号写死在 gen_ut_xlsx.py；xlsx 内不加标注 -->
| 文件 | 用途 |
|---|---|
| `scripts/gen_ut_xlsx.py` | cases.json → xlsx（OOXML 最小修改，不整本重存）+ lint + 生成后自检 |
| `scripts/read_design.py` | 读设计书，列出 SCR/API/BR/AC/Q/错误码 ID 一览（用于追溯核对） |
| `scripts/clean_template.py` | 清除模板 xlsx 里的个人/组织/打印机等元数据（换新模板时用） |
| `templates/単体テスト項目_テンプレート.xlsx` | 已清理的模板（6 sheet，结构与 `docs/ai-native/` 原模板相同） |
| `cases.schema.json` | cases.json 的 JSON Schema（字段 ↔ xlsx 列） |
| `examples/sample.cases.json` | **架空示例**（「お知らせ管理」），只演示格式 |

## 安装

```bash
python3 -m pip install -r requirements.txt   # 只依赖 openpyxl，其余是标准库（Python 3.8+）
```

## 用法（在 CMPF-SRC 根目录执行）

```bash
T=tools/unit-test-xlsx/scripts   # 放置位置按实际调整
# 1) 列出设计书 ID（可多个来源；目录会自动找 design.json / API設計書_*.xlsx / 画面設計書_*.xlsx / MD）
python3 $T/read_design.py docs/{機能}/ --ids          # --all 连 Q/BL/F 和画面项目・事件・步骤等要素 ID 一起列；--json 输出 JSON；--dump 转纯文本
# 有 design.json 时可先起草骨架：python3 $T/read_design.py docs/{機能}/design.json --draft -o /tmp/draft.cases.json（TODO 全部要改）
# 2) 生成 + 检查
python3 $T/gen_ut_xlsx.py docs/{機能}/cases.json \
    -o docs/{機能}/単体テスト項目_{機能}.xlsx \
    --design docs/{機能}/ \
    --trace-report /tmp/trace_{機能}.md
# 只检查不生成：--lint-only；有警告就失败：--strict；看骨架：--schema
```

<!-- [CMPF] 模板：默认后备模板路径 docs/ai-native/単体テスト項目_テンプレート.xlsx 是 CMPF 仓库约定 -->
- 模板：默认用本工具 `templates/`，找不到再用 `docs/ai-native/単体テスト項目_テンプレート.xlsx`；`--template` 可指定。
<!-- [CMPF] 多语言＋错误码格式：语言固定 ja/en，默认 locale 目录 frontend/src/locale；错误码按 [A-Z]{2,8}\d{3,5}-[EIW]（CMPF 为 CMPFnnnn-E），code 行自动展开日文行＋英文行 -->
- 消息文言：省略 `--locale-dir` 时自动找 `frontend/src/locale`（`ja/index.ts`、`en/message.ts`）。check 行写 `"code"` 时从这里取 ja/en 文言，自动展开日文行 + 英文行。
- 读设计书优先级：**中間 JSON `docs/{機能}/design.json`**（也认 `*.design.json`）＞ `API設計書` + `画面設計書` 两份 xlsx + MD。JSON 读不了或格式不对会提示并自动改读 xlsx/MD；缺一份 xlsx 会提示并用 MD 补；`--no-json` 可强制读 xlsx/MD 做对照。
<!-- [CMPF] ID 写法：SCR-/API-/BR-/AC-/Q-（以及 BL-/F-、要素 ID -I01/-E01/-S01/-C01/-B01）是 CMPF 的约定；将来 ID 规则只在 project.json 定义一份，设计书和单体 case 两个工具共读 -->
- 中間 JSON 的格式见设计书工具的 [`tools/design-xlsx/README.md`](../design-xlsx/README.md)「JSON 格式说明」（示例 `tools/design-xlsx/example/sample_design.json`）。本工具递归读 `screens[]`/`apis[]` 及其下的 items・events・steps・check 行・table 分支行，收集每个要素的 `id`、`refs.br/ac/q`、`error_code`、`api_id`。
  画面・API・错误码是**必须有 Case** 的 ID；画面项目・事件・步骤・检查项・分支的要素 ID 只列出（`--all`），通过它们的 BR/AC 追溯。要素带 `status: "withdrawn"`（或「欠番」）、或正文写「BR-nn 欠番」时识别为欠番，不要求覆盖、引用时警告。
<!-- [CMPF] 模板：自检的 sheet 名・顺序・隐藏 sheet・項目総計 行号按 CMPF 模板写死 -->
- 生成后自检：sheet 名/顺序/隐藏、`試験観点`・`DB書き込み判定` 字节不变、`項目総計` COUNTIF 范围 = 实际 Case 行、按实际行数核对 CASE 数、下拉范围覆盖所有 Case 行。失败 exit 2。
- 不要用 openpyxl 打开后另存生成的 xlsx（会丢扩展下拉）；要改就改 cases.json 重新生成。

## cases.json 格式（详见 `cases.schema.json`、`examples/sample.cases.json`）

```jsonc
{ "meta": {"feature": "{機能}", "created": "YYYY-MM-DD", "lang": "ja"},
  "layout":    [ {"section": "【SCR-xxx 画面名】エリア", "ref": "SCR-xxx", "cases": [ {viewpoint,name,type,label,note,ref,verify} ]} ],
  "operation": [ {"section": "【SCR-xxx / API-xxx】シナリオ", "cases": [ {viewpoint,item,step,branch,branch1,branch2,expected,ref,verify} ]} ],
  "check":     [ {"section": "【SCR-xxx】入力チェック", "cases": [ {viewpoint,field,screen,branch1,branch2,expected|code,ref,verify} ]} ] }
```

<!-- [CMPF] 模板：試験観点 16 词和三个 Case sheet 的分工来自 CMPF 单体模板 -->
- `viewpoint` 只能用 `試験観点` sheet 的 16 个词；`layout`=布局・显示・多语言，`operation`=操作・API 流程・分支・权限・DB 结果，`check`=输入校验・边界值・错误消息。
- `ref`：每条 Case 写对应 BR/AC，设计未定的加 Q；分组行 `section` 带 SCR/API 编号。欠番编号不复用。
- `verify`：`JUnit` / `結合`（只能联调确认）/ `手動`。写进 trace-report，不进 xlsx。
- 结果列（判定・判定履歴・担当者・最新結果・BUG票ID）不在 cases.json 里，生成时留空。

## 写法要点（来自 unit-test-case-docs.mdc，lint 会查一部分）

<!-- [CMPF] 正文语言：Case 正文日文（lint 在 meta.lang=ja 时检查简体中文混入）。设计书 MD 原稿正文以中文为主、导出的设计书 xlsx 正文日文；read_design 只抽 ID、不比对文言，所以目前不按来源区分语言 -->
- **Case 正文用日文**；画面文言、消息保持原文，不翻译。
- 予想結果必须可判定：禁止「正常」「OK」「仕様通り」「可能」等，写出具体画面表示、值或 DB 结果。
- 业务语言，正文不写函数名、文件路径、DB 列名。
- 设计书每条 BR/AC 至少一条 Case；改既有功能时，「改修前挙動」表里未标「変更」的每格写一条「改修前と同じ」的回归 Case。
- 测试数据名加前缀（如 `UT{機能}_`），删除脚本与插入脚本一起准备，执行前给用户确认。

## 给 Cursor 的提示词（可直接复制）

<!-- [CMPF] 正文语言：下面的提示词要求 Case 正文日文、画面文言和消息保持原文 -->
```
请按 .cursor/rules/unit-test-case-docs.mdc，为功能「{機能}」写单体测试 Case：
1. 先运行 python3 tools/unit-test-xlsx/scripts/read_design.py docs/{機能}/ --ids --all，拿到需要覆盖的 SCR/API/BR/AC/Q/错误码一览；
   再读 docs/{機能}/ 下的设计书（API設計書・画面設計書 xlsx 或 MD）和相关现有代码、locale（只读）。
2. 按 tools/unit-test-xlsx/cases.schema.json 的格式写 docs/{機能}/cases.json（可参考 examples/sample.cases.json 的形式，内容不要照抄）：
   Case 正文用日文，画面文言和消息保持原文；每条 Case 的 ref 写 BR/AC（未定的写 Q），分组行写 SCR/API 编号；
   予想結果写具体可判定的画面表示/值/DB 结果；verify 标 JUnit 或 結合。
3. 运行 python3 tools/unit-test-xlsx/scripts/gen_ut_xlsx.py docs/{機能}/cases.json -o docs/{機能}/単体テスト項目_{機能}.xlsx --design docs/{機能}/ --trace-report /tmp/trace.md
4. 逐条处理 lint 警告（未覆盖的 ID、不可判定的予想結果、缺 BR/AC、欠番引用等），改 cases.json 后重跑，直到只剩说明得了理由的警告。
5. 不要用 openpyxl 另存 xlsx，不要改 試験観点 sheet。最后报告各 sheet Case 数、未覆盖的 ID、设计书与代码不一致需要确认的地方。
```

已有 `単体テスト項目_{機能}.xlsx` 时：先把现有 Case 整理进 cases.json，只增改受影响的行，再重新生成。
