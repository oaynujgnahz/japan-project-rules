# 仕様 MD 化バックログ

新功能 **必须** 先建 `docs/{機能}/`。下列为既有功能逐步 MD 化优先级（PPT：系统仕样 MD 化）。

## 状态

| 状态 | 含义 |
|------|------|
| `done` | `docs/{機能}/` 完备，可作 AI 上下文 |
| `wip` | 部分 MD / 仅有 xlsx 要件 |
| `todo` | 仅代码或散落 xlsx，无 `docs/` |

## 一覧

| 优先级 | 機能 | docs 路径 | 状态 | 备注 |
|--------|------|-----------|------|------|
| — | PCF算定 Excel 取込 | `docs/PCF算定_Excel取込/` | done | 范例 |
| — | 报告出力 排出量 PPT | `docs/报告出力_排出量PPT/` | done | 范例 |
| 高 | PCF算定 UIUX改善 | `docs/PCF算定_UIUX改善/` | wip | 复制 API/UI 实装中；Step 合并 todo |
| 高 | 電力データ連携 申請一覧/詳細 | `docs/電力データ連携_申請/` | todo | xlsx 在 `{{main_module}}/新的画面和后台需求/` |
| 高 | 証書・クレジット一覧 | `docs/証書クレジット_一覧/` | todo | xlsx 在 `{{main_module}}/参考设计书/` |
| 中 | ESG アップロード / Activity | `docs/ESG_活動量/` | todo | 复盘：error check / 主键 |
| 中 | 公開データ連携 | `docs/公開データ連携/` | todo | IF xlsx 在 `{{main_module}}/新需求/` |
| 低 | 削減貢献量 | `docs/削減貢献量/` | todo | |
| 低 | サプライヤ開示 | `docs/サプライヤ開示/` | todo | |
| 低 | GXD / PCF データ連携 | `docs/GXD_PCF連携/` | todo | |

## 追加手顺

1. 创建 `docs/{機能}/README.md` 索引
2. 用 `md-design-doc` skill 写 06/07 或 `詳細設計書.md`
3. 本表状态 → `done`
4. 在 `workflow.mdc`「写设计书」阶段 gate 可引用该路径

## 维护

- 新機能着手前：若无行则追加一行 `todo`
- MD 化完成：改 `done` 并链到 README
