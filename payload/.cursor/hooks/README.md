# Agent hooks（项目级）

| Hook | 脚本 | 作用 |
|------|------|------|
| `afterFileEdit` | `check-no-chinese-comments.py` | 扫描源码注释中的简体中文特征词；命中则写 pending 并尝试注入 `additional_context` |
| `postToolUse` | 同上 | 可靠投递 pending 警告（`afterFileEdit` 的输出有时不被 Cursor 消费） |

## 规则

- 注释须为**日文或英文**（`cmpf-core` / `AGENTS.md`）。
- **不**用「任意汉字」判定（日文汉字会误伤）；用简体中文常用词/助词启发式。
- 跳过：`locale/`、`i18n/`、`docs/`、`*.md`。
- 仅检查：`.java` `.vue` `.ts` `.tsx` `.js` `.jsx` 中的 `//` `/* */` `<!-- -->` 注释。

## 验证

```bash
printf '%s' '{"hook_event_name":"afterFileEdit","conversation_id":"test","file_path":"/tmp/x.java","workspace_roots":["/tmp"],"edits":[{"old_string":"","new_string":"// 字符串避免混淆\nint x=1;\n"}]}' \
  | .cursor/hooks/check-no-chinese-comments.py
```

期望 stdout 含 `additional_context`，stderr 含 `BLOCKER`。

日文注释应放行：

```bash
printf '%s' '{"hook_event_name":"afterFileEdit","conversation_id":"test2","file_path":"/tmp/x.java","workspace_roots":["/tmp"],"edits":[{"old_string":"","new_string":"// 文字列にし、n-select が数値 0 と未選択 null を混同しないようにする\n"}]}' \
  | .cursor/hooks/check-no-chinese-comments.py
```

期望 stdout 为 `{}`。
