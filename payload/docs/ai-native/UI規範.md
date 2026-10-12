# UI 規範（CMPF Frontend）

对应 CO2MOS 复盘：UI 长度不齐、低级错误、既存デグレ。实装前 **必须先查通用组件**。

## 实装前检查清单

- [ ] `frontend/src/components/` 是否有可复用组件？
- [ ] `frontend/src/hook/LocalNaiveUI.ts` 是否有对话框/表格按钮模式？
- [ ] 同类画面（如列表+详情）如何布局？对齐参照画面
- [ ] classic / new 双路由是否都需要改？

## 优先使用的共通组件

| 用途 | 路径 / API |
|------|------------|
| 确认对话框 | `useConfirm()` in `hook/LocalNaiveUI.ts` |
| 表格内操作按钮 | `TableButton()` |
| 数字输入 | `LocalInputNumber`、`LocalInputDecimal`、`LocalNumber` |
| 远程下拉 | `RemoteSelect`、`RemoteSelect/guideSelect.vue` |
| 可拖拽 Modal | `components/Modal/MyModal.vue` |
| 树形穿梭 | `LocalTreeTransfer`、`LocalTransfer` |
| 加载 | `components/Loading/Loading.vue` |
| SVG 图标 | `SvgIcon` |
| 图表 | `components/Charts/*` + `UnitSetting` |
| 表格列宽拖拽 | `directive/TableColumnDragSize` |

**新规组件**：仅当上表无法满足时，在 `components/` 追加并在本文档「新规记录」登记。

## 布局与交互

| 项目 | 规范 |
|------|------|
| 列表页 | `n-card` + 检索区 + `n-data-table`；操作列右固定 |
| 表单 | 必填标记与 Naive 校验一致；错误在字段下或 `useMessage` |
| 按钮顺序 | 取消/关闭（次要）在左，确定/保存（主要）在右 |
| 间距 | 与相邻同类画面一致；勿单独加大 margin |
| 权限 | `Authority()` / `ACCESS_R_*` 与既有画面相同模式 |

## 文案与 i18n

- 所有可见文字 `$t('...')`
- **ja / en** 双语同步（`locale/zh` 不维护），术语见 [用語辞書_日英.md](./用語辞書_日英.md)

## RV 要点（AI + Human）

1. 与参照画面并排对比（列宽、按钮、空状态）
2. classic / new UI 模式均确认（如适用）
3. 回归：同模块列表/编辑/删除/权限边界

## 新规组件记录

| 日期 | 组件 | 用途 | 追加者 |
|------|------|------|--------|
| — | （实装时填写） | | |
