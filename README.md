# japan-project-rules（对日项目的规则）

CMPF-SRC 用的 AI 开发规则：Cursor Rules、AGENTS.md、设计书 / 单体测试模板、Skills。
**只在本地用，绝对不要提交进甲方仓库。**

## 安装（约 1 分钟）

```bash
git clone git@github.com:<org>/japan-project-rules.git ~/work/japan-project-rules
cd ~/work/japan-project-rules
./init.sh ~/work/CMPF-SRC cmpf          # 第一次：只读扫描项目，逐项确认，生成本地配置
                                          # → ~/work/CMPF-SRC/.japan-project-rules/project.json（自动写进 .git/info/exclude）
CFG=~/work/CMPF-SRC/.japan-project-rules/project.json
./install.sh ~/work/CMPF-SRC --config $CFG --dry-run   # 先看会改什么（可选）
./install.sh ~/work/CMPF-SRC --config $CFG             # 正式安装
```

`init.sh` 只在本地生成配置，不 commit、不 push。`projects/cmpf/project.json` 是只读示例（带 `"_example": true`），
init 拿它当模板，脚本不会直接用它；所有脚本都必须用 `--config` 指定 init 生成的配置，没有配置、缺键、还有占位符都会报错退出，不会回落到 CMPF 的值。
bot（没有交互终端）用 `./init.sh <项目> <名> --emit-questions` 拿问题、在聊天里问用户，再 `--answers answers.json` 生成；
代码变了用 `./init.sh <项目> <名> --verify --out <配置>` 核对错误码条数。详见 `python3 tools/init_project.py --help`。

`install.sh` 会做这 4 件事（项目相关的值都取自 `--config`）：

1. 把规则复制进 CMPF-SRC（`AGENTS.md`、`.cursor/`、`docs/ai-native/`、`docs/単体テスト項目テンプレート/`、`e2e/`、Java 8 用 Maven 包装脚本（CMPF 为 `mvn8`）、PR 模板、`tools/design-xlsx/`、`tools/unit-test-xlsx/`）。已有文件如果内容不同，先备份到 `.rules-backup/<时间>/` 再覆盖。
   `payload/` 里的 `{{name}}`、`{{system_name}}`、`{{repo_name}}`、`{{root_artifact}}`、`{{base_package}}`、`{{build_cmd}}`、`{{build_wrapper}}`、`{{error_code_prefix}}`、`{{error_code}}` 在复制时换成配置里的值（对应键见 `tools/project_config.py` 的 `PAYLOAD_PLACEHOLDERS`，由 init 询问）；缺键就报错退出，不会回落成 CMPF 的值。`payload.build_wrapper` 为空时不装包装脚本。
   模块名来自配置顶层 `modules`（每项 name / kind / role，kind=api 中一个 `"main": true`，kind=frontend 一个），渲染成 `{{modules_list}}`、`{{main_module}}`、`{{frontend_module}}` 等（见 `MODULE_PLACEHOLDERS`）。
   技术栈版本 `stack.java_version` / `stack.spring_boot_version`（init 从 pom.xml 读）、前端 `stack.node_version` / `stack.npm_version`（前端 pom.xml 的 frontend-maven-plugin，可空串 = 不写 Node 行）和 `stack.frontend_patches`（`<前端>/patches/*.patch`，可空列表 = 不写 patch 行）、部署环境 `deploy.manifest_envs` / `deploy.prod_manifests`（init 从 `manifests/` 读），以及项目专属的范例文本 `examples`（范例设计书、术语表核心概念、backlog 等；id 一览见 `EXAMPLE_IDS`，每个 id 都要写；表格单元格等 inline id（`EXAMPLE_INLINE_IDS`）空串显示「—」；句子里可省的一段 fragment id（`EXAMPLE_FRAGMENT_IDS`）空串什么都不写；其余 block id 空串 = 那一行不装；inline / fragment 不能含换行和「|」。渲染规则的回归检查：`python3 tools/project_config.py --self-test`）都是必需键，缺了就报错。
   规则文件名是通用名（`.cursor/rules/project-core.mdc`、`.cursor/agents/orchestrator.md`）；以前装过的旧名 `cmpf-core.mdc`、`cmpf-orchestrator.md` 会被移到同一个 `.rules-backup/<时间>/`（不删除）。
2. 把这些文件写进 `.git/info/exclude`：只在你本地生效，`git status` 里看不到，也不用改 `.gitignore`。
3. 把 `skills/` 下的 skill 装到 `~/.cursor/skills/`。
4. 按配置的 `env_checks` 检查环境（CMPF 是 Java 8 + Maven、node），再查 python3 / openpyxl，缺什么会直接提示。

装完用 Cursor 打开 CMPF-SRC，规则就会自动生效。

## 每个人要自己做的

| 项目 | 做法 |
|------|------|
| Java 8 / Maven | `./mvn8` 会自动找；找不到的话，在 `~/.zshrc` 里设 `export JAVA8_HOME=<JDK8 路径>`，Maven 装在 `/opt/homebrew/bin` 以外时设 `MAVEN_BIN` |
| MCP（可选） | `cp .cursor/mcp.json.example .cursor/mcp.json`，**只填只读账号**，不要提交 |
| E2E（可选） | `cd e2e && npm install && npx playwright install chromium`，账号写在 `e2e/.env` |

## xlsx 生成工具（`tools/`）

| 工具 | 用途 | 说明 |
|------|------|------|
| `tools/design-xlsx/` | MD 设计书 → `API設計書_{機能}.xlsx` / `画面設計書_{機能}.xlsx` | 先让 Cursor 按 README 的提示词从 MD 写 `docs/{機能}/design.json`，再跑 `export_api.py` / `export_scr.py` |
| `tools/unit-test-xlsx/` | 设计书 → `単体テスト項目_{機能}.xlsx` | `read_design.py` 列出要覆盖的 ID，写 `cases.json`，再跑 `gen_ut_xlsx.py`（自带 lint 和自检） |

依赖：`python3 -m pip install openpyxl`（画面设计书里放图片时再装 `pillow`）。`install.sh` 会把工具一起复制到 CMPF-SRC 的 `tools/` 下（同样写进 `.git/info/exclude`），在 CMPF-SRC 根目录直接运行：

```bash
python3 tools/design-xlsx/export_api.py docs/{機能}/design.json
python3 tools/design-xlsx/gen_design_xlsx.py docs/{機能}/design.json --config <配置> -o …   # 詳細設計書
python3 tools/unit-test-xlsx/scripts/gen_ut_xlsx.py docs/{機能}/cases.json --config <配置> -o …
```

详细用法见各目录的 `README.md`。

## 用 Grok Bot 时怎么装

Grok Bot 的技能只在同一个账号的 bot 之间共用，同事的 bot 读不到别人的技能，也不会自己去读本仓库。每个人要给自己的 bot 装一次：

1. **clone 本仓库**：让 bot 在它自己的电脑上 clone 到固定目录，建议 `/workspace/japan-project-rules`。仓库是私有的话，要先用你自己的 GitHub 账号授权 bot，这一步只能本人做。
2. **导入技能**：让 bot 把下面两份 SKILL.md 存成它自己的技能，并在技能里把相对路径换成第 1 步的绝对路径（例：`tools/design-xlsx/` → `/workspace/japan-project-rules/tools/design-xlsx/`）。
   - `skills/design-doc-xlsx/`（SKILL.md + RULES.md）：詳細設計書 / 对外设计书
   - `skills/unit-test-xlsx/SKILL.md`：単体テスト項目
   - `skills/md-design-doc/` 还没通用化，先不要导入。
3. **项目配置**：项目差异（系统名、错误码格式、locale 目录和语言、模板）都在 init 生成的本地 `project.json` 里。bot 读不到用户电脑上的文件时，在 bot 自己的电脑上跑 `./init.sh … --answers`（扫描只读用户电脑，或 `--no-scan` 全部用回答），配置放在 bot 自己的目录（例：台账目录旁边）。不要把生成的配置提交进本仓库；`projects/cmpf/project.json` 只是示例，不要改它。`ledger_dir` 按自己的环境填。
4. **bot 说明**：bot 说明里不要写别人的路径。代码目录、技能名、台账目录都换成自己的。
5. **依赖**：`python3 -m pip install -r tools/design-xlsx/requirements.txt`（openpyxl、python-pptx；`read_pptx.py --render` 另需 LibreOffice 和 poppler）。

装完先用 `python3 tools/design-xlsx/gen_design_xlsx.py --blank --config <配置> -o /tmp/blank.xlsx` 跑一次，能生成 xlsx 就说明装好了（`meta.system` 取配置的 `design.system_name`）。

## 日常使用

- 先读 `docs/ai-native/README.md`（总索引）和 `TEAM_ONBOARDING.md`。
- 流程：理解现状 → 写设计书 → 设计评审 → 开发 → 实现评审 → 单体测试 → 联调，详见 `docs/ai-native/開発フロー.md`。
- 设计书以 MD 为原稿放在 `docs/{機能}/`，对外的 xlsx 拆成 `API設計書_{機能}.xlsx` 和 `画面設計書_{機能}.xlsx` 两份导出。
- 各功能的 `docs/{機能}/`（要件、设计书、测试数据）是项目资料，**不放进本仓库**。

## 提交 CMPF 代码时的注意点

- 人工选择要提交的文件，不要用 `git add -A` 或 `git add .`。
- commit message、PR 说明、代码注释、JUnit 方法名里，不能出现 BR / AC / Q 编号、`docs/` 路径、设计书名、RV 结果。
- 本地配置（`application-dev.yml`、`mybatisGenerator.properties` 等）和 `package-lock.json` 不提交。
- 提交前按 `.cursor/rules/review.mdc` 的「提交前扫描」检查一遍暂存区。

## 更新规则

- 更新：`git pull` 以后，再跑一次 `./install.sh <CMPF-SRC 路径> --config <配置>`。没变的文件会跳过，改动过的会先备份再覆盖。
- 改规则一律走本仓库的 PR，review 通过后再合并。推送前先扫一遍有没有个人路径、账号、库名、密码。
- 卸载或恢复：删掉 CMPF-SRC 里对应的规则文件，或者从 `.rules-backup/<时间>/` 复制回去；再删掉 `.git/info/exclude` 里 `japan-project-rules` 那一段。
