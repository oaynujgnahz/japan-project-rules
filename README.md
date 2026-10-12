# japan-project-rules（对日项目的规则）

CMPF-SRC 用的 AI 开发规则：Cursor Rules、AGENTS.md、设计书 / 单体测试模板、Skills。
**只在本地用，绝对不要提交进甲方仓库。**

## 安装（约 1 分钟）

```bash
git clone git@github.com:<org>/japan-project-rules.git ~/work/japan-project-rules
cd ~/work/japan-project-rules
./install.sh --dry-run ~/work/CMPF-SRC   # 先看会改什么（可选）
./install.sh ~/work/CMPF-SRC             # 正式安装
```

脚本会做这 4 件事：

1. 把规则复制进 CMPF-SRC（`AGENTS.md`、`.cursor/`、`docs/ai-native/`、`docs/単体テスト項目テンプレート/`、`e2e/`、`mvn8`、PR 模板、`tools/design-xlsx/`、`tools/unit-test-xlsx/`）。已有文件如果内容不同，先备份到 `.rules-backup/<时间>/` 再覆盖。
2. 把这些文件写进 `.git/info/exclude`：只在你本地生效，`git status` 里看不到，也不用改 `.gitignore`。
3. 把 `md-design-doc`、`cmpf-report-file-io` 两个 skill 装到 `~/.cursor/skills/`。
4. 检查 Java 8、Maven、python3、node，缺什么会直接提示。

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
```

详细用法见各目录的 `README.md`。

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

- 更新：`git pull` 以后，再跑一次 `./install.sh <CMPF-SRC 路径>`。没变的文件会跳过，改动过的会先备份再覆盖。
- 改规则一律走本仓库的 PR，review 通过后再合并。推送前先扫一遍有没有个人路径、账号、库名、密码。
- 卸载或恢复：删掉 CMPF-SRC 里对应的规则文件，或者从 `.rules-backup/<时间>/` 复制回去；再删掉 `.git/info/exclude` 里 `japan-project-rules` 那一段。
