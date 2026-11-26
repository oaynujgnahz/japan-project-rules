# 単体テスト項目 xlsx 生成ツール（unit-test-xlsx）

设计书（`docs/{機能}/`）→ 人或 Cursor 写 `cases.json` → `gen_ut_xlsx.py` 按仓库模板生成 `単体テスト項目_{機能}.xlsx`。
规则以 `.cursor/rules/unit-test-case-docs.mdc` 为准，本工具只负责「按规则落到模板里」和机械检查。

## 文件

<!-- [项目约定] 模板：templates/単体テスト項目_テンプレート.xlsx 是示例项目单体模板（6 sheet：試験観点/項目総計/画面レイアウト判定/画面操作処理判定/項目チェック判定/DB書き込み判定(隐藏)），sheet 名・列对应・行号写死在 gen_ut_xlsx.py；xlsx 内不加标注 -->
| 文件 | 用途 |
|---|---|
| `scripts/gen_ut_xlsx.py` | cases.json → xlsx（OOXML 最小修改，不整本重存）+ lint + 生成后自检 |
| `scripts/read_design.py` | 读设计书，列出需要 Case 覆盖的 画面/API/BR/AC/错误码 ID（`--ids`）；从 design.json 起草 Case 骨架（`--draft`）；正文转纯文本（`--dump`） |
| `scripts/clean_template.py` | 清除模板 xlsx 里的个人/组织/打印机等元数据（换新模板时用） |
| `templates/単体テスト項目_テンプレート.xlsx` | 已清理的模板（6 sheet，结构与 `docs/ai-native/` 原模板相同） |
| `cases.schema.json` | cases.json 的 JSON Schema（字段 ↔ xlsx 列） |
| `examples/sample.cases.json` | **架空示例**（「お知らせ管理」），只演示格式 |

## 安装

```bash
python3 -m pip install -r requirements.txt   # 只依赖 openpyxl，其余是标准库（Python 3.8+）
```

## 用法（在项目仓库根目录执行）

```bash
T=tools/unit-test-xlsx/scripts   # 放置位置按实际调整
CFG=.japan-project-rules/project.json   # init.sh 生成的项目配置（必须；示例配置会被拒绝）
# 1) 列出设计书 ID（<src> = 设计书 bot 的 design.json / docs/{機能}/ 目录（读 MD・YAML）/ 設計書 xlsx）
python3 $T/read_design.py docs/{機能}/ --ids --config $CFG          # --dump 转纯文本（不需要 --config）
# 有 design.json 时可先起草骨架：python3 $T/read_design.py design.json --config $CFG --draft -o /tmp/draft.cases.json（TODO 全部要改）
# 2) 生成 + 检查
python3 $T/gen_ut_xlsx.py docs/{機能}/cases.json --config $CFG \
    -o docs/{機能}/単体テスト項目_{機能}.xlsx \
    --design docs/{機能}/ \
    --trace-report /tmp/trace_{機能}.md
# 只检查不生成：--lint-only；有警告就失败：--strict；看骨架：--schema
```

<!-- [项目约定] 模板：默认后备模板路径 docs/ai-native/単体テスト項目_テンプレート.xlsx 是示例项目仓库约定 -->
- 模板：`--template` ＞ 配置 `unit_test.template` ＞ 本工具 `templates/`（已清理版）＞ `docs/ai-native/単体テスト項目_テンプレート.xlsx`。
  规则仓库只带清理过的模板（无打印设置、公司名、敏感度标签、内部打印机等元数据）；要和公司原版逐字节一致，init 时在 `unit_test.template` 填公司原版的本地路径（不提交）。
<!-- [项目约定] 多语言＋错误码格式：语言固定 ja/en，默认 locale 目录 frontend/src/locale；错误码按 [A-Z]{2,8}\d{3,5}-[EIW]（示例项目为 XXXXnnnn-E），code 行自动展开日文行＋英文行 -->
- 消息文言：省略 `--locale-dir` 时用配置 `i18n.locale_dir`（相对项目根），每种语言按 `unit_test.locale_files` 顺序读。check 行写 `"code"` 时取各语言文言，按 `i18n.languages` 展开（第一个语言是正文行，其余是 多言語対応チェック 行；书式 `unit_test.error_message_templates`，分岐2 的语言名 `unit_test.language_labels`）。错误码只认 `ids.error_code`。
- `--design` 覆盖检查：design.json（设计书 bot 格式：screens / apis / business_rules / acceptance / checks）取 画面・API・BR・AC・错误码；目录读其中 MD/YAML，xlsx 读全部 sheet（改訂履歴・実装対照 除外），按配置的 ID 正则抽取。
<!-- [项目约定] ID 写法：画面/API ID 按配置 ids.screen_id / ids.api_id；BR-/AC- 是设计书模板的约定 -->
<!-- [项目约定] 模板：自检的 sheet 名・顺序・隐藏 sheet・画面操作処理判定 表头按示例项目模板写死 -->
- 生成后自检：sheet 名/顺序、`DB書き込み判定` 隐藏、`画面操作処理判定` 表头、`試験観点`・`DB書き込み判定` 字节不变。失败 exit 2。
- 不要用 openpyxl 打开后另存生成的 xlsx（会丢扩展下拉）；要改就改 cases.json 重新生成。

## cases.json 格式（详见 `cases.schema.json`、`examples/sample.cases.json`）

```jsonc
{ "meta": {"feature": "{機能}", "created": "YYYY-MM-DD", "lang": "ja"},
  "layout":    [ {"section": "【SCR-xxx 画面名】エリア", "ref": "SCR-xxx", "cases": [ {viewpoint,name,type,label,note,ref} ]} ],
  "operation": [ {"section": "【SCR-xxx / API-xxx】シナリオ", "cases": [ {viewpoint,item,step,branch,branch1,branch2,expected,ref} ]} ],
  "check":     [ {"section": "【SCR-xxx】入力チェック", "cases": [ {viewpoint,field,screen,branch1,branch2,expected|code,ref} ]} ] }
```

<!-- [项目约定] 模板：試験観点 16 词和三个 Case sheet 的分工来自示例项目单体模板 -->
- `viewpoint` 只能用 `試験観点` sheet 的 16 个词；`layout`=布局・显示・多语言，`operation`=操作・API 流程・分支・权限・DB 结果，`check`=输入校验・边界值・错误消息。
- `ref`：每条 Case 写对应 BR/AC，设计未定的加 Q；分组行 `section` 带 SCR/API 编号。欠番编号不复用。
- `verify`（可选）：`JUnit` / `結合` / `手動` 的备忘。生成器不读、不检查，也不进 xlsx。
- 结果列（判定・判定履歴・担当者・最新結果・BUG票ID）不在 cases.json 里，生成时留空。

## 写法要点（来自 unit-test-case-docs.mdc，lint 会查一部分）

<!-- [项目约定] 正文语言：Case 正文日文（lint 在 meta.lang=ja 时检查简体中文混入）。设计书 MD 原稿正文以中文为主、导出的设计书 xlsx 正文日文；read_design 只抽 ID、不比对文言，所以目前不按来源区分语言 -->
- **Case 正文用日文**；画面文言、消息保持原文，不翻译。
- 予想結果必须可判定：禁止「正常」「OK」「仕様通り」「可能」等，写出具体画面表示、值或 DB 结果。
- 业务语言，正文不写函数名、文件路径、DB 列名。
- 设计书每条 BR/AC 至少一条 Case；改既有功能时，「改修前挙動」表里未标「変更」的每格写一条「改修前と同じ」的回归 Case。
- 测试数据名加前缀（如 `UT{機能}_`），删除脚本与插入脚本一起准备，执行前给用户确认。

## 给 Cursor 的提示词（可直接复制）

<!-- [项目约定] 正文语言：下面的提示词要求 Case 正文日文、画面文言和消息保持原文 -->
```
请按 .cursor/rules/unit-test-case-docs.mdc，为功能「{機能}」写单体测试 Case：
1. 先运行 python3 tools/unit-test-xlsx/scripts/read_design.py docs/{機能}/ --ids --config <项目配置>，拿到需要覆盖的 画面/API/BR/AC/错误码一览；
   再读 docs/{機能}/ 下的设计书（API設計書・画面設計書 xlsx 或 MD）和相关现有代码、locale（只读）。
2. 按 tools/unit-test-xlsx/cases.schema.json 的格式写 docs/{機能}/cases.json（可参考 examples/sample.cases.json 的形式，内容不要照抄）：
   Case 正文用日文，画面文言和消息保持原文；每条 Case 的 ref 写 BR/AC（未定的写 Q），分组行写 SCR/API 编号；
   予想結果写具体可判定的画面表示/值/DB 结果。
3. 运行 python3 tools/unit-test-xlsx/scripts/gen_ut_xlsx.py docs/{機能}/cases.json --config <项目配置> -o docs/{機能}/単体テスト項目_{機能}.xlsx --design docs/{機能}/ --trace-report /tmp/trace.md
4. 逐条处理 lint 警告（未覆盖的 ID、不可判定的予想結果、缺 ref、缺多语言行等），改 cases.json 后重跑，直到只剩说明得了理由的警告。
5. 不要用 openpyxl 另存 xlsx，不要改 試験観点 sheet。最后报告各 sheet Case 数、未覆盖的 ID、设计书与代码不一致需要确认的地方。
```

已有 `単体テスト項目_{機能}.xlsx` 时：先把现有 Case 整理进 cases.json，只增改受影响的行，再重新生成。
