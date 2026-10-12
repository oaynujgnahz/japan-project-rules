# Examples

## 按功能建目录（第一步）

```bash
# 例：CMPF 仓库根目录
mkdir -p docs/PCF算定_Excel取込/{05_UI設計,06_画面設計書,07_API設計書}
```

然后写入：
- `docs/PCF算定_Excel取込/README.md`
- `docs/PCF算定_Excel取込/機能設計書.md` 或 `06_…` / `07_…` 拆分文件

**错误**：`docs/新機能設計書.md`（根下平铺）  
**正确**：`docs/新機能/機能設計書.md`

## 完整树示例

```text
CMPF-SRC/                          # 项目主目录
└── docs/
    ├── PCF算定_Excel取込/
    │   ├── README.md
    │   ├── 機能設計書.md
    │   ├── 06_画面設計書/
    │   │   └── SCR-B-46-00-02_取込.md
    │   ├── 07_API設計書/
    │   │   ├── openapi.yaml
    │   │   └── API-B-46-00-02_upload.md
    │   └── PCF活動量情報_校验一覧.md
    └── 报告出力_排出量PPT/
        ├── README.md
        └── …
```

## Invoke

- 「为電力連携功能写設計書，按功能分文件夹」
- 「在 docs 下新建 XXX 機能目录并写 06 画面」

## Future 06 / 07 片段

（内容同前；路径均带 `docs/{機能}/` 前缀）

## 遗留迁移

| 旧 | 新 |
|----|-----|
| `docs/PCF算定_Excel取込出力_設計書.md` | `docs/PCF算定_Excel取込/機能設計書.md` |

新文档只用功能文件夹；迁移时可在旧文件顶部加一行：`> 已迁至 docs/PCF算定_Excel取込/`
