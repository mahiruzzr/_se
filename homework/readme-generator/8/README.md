# dupekit

安全、快速的重複檔案尋找與清理工具。單一檔案、純 Python 標準庫，不需安裝任何套件。

- **預設只預覽**，加上 `--apply` 才會真的變更檔案
- **三階段篩選**，只對真正有疑義的檔案做完整讀取
- **動手前再逐位元組比對**，掃描後檔案被改過也不會誤刪
- 可選擇 **刪除 / 換成硬連結 / 搬到隔離目錄**

## 需求

- Python 3.8 以上
- Linux / macOS / Windows（硬連結功能需要檔案系統支援，如 NTFS、ext4、APFS）

## 快速開始

```bash
# 1. 只看報告，不動任何檔案
python3 dupekit.py ~/Photos ~/Backup

# 2. 預覽「換成硬連結」會做什麼
python3 dupekit.py ~/Photos ~/Backup --action hardlink

# 3. 確認沒問題後，真的執行
python3 dupekit.py ~/Photos ~/Backup --action hardlink --apply
```

報告範例：

```
[1] 3 個檔案 × 20.0 MB（可回收 40.0 MB） #d870e17580ea
    保留  photos/trip.raw
    重複  backup/2025/trip.raw
    重複  downloads/trip (1).raw

============================================================
掃描檔案：605　重複組數：102　重複檔案：103
可回收空間：42.6 MB
動作 hardlink：預覽模式，共 103 項，尚未變更任何檔案（加上 --apply 才會執行）
```

## 參數

```
dupekit PATH [PATH ...] [選項]
```

| 參數 | 說明 | 預設 |
|---|---|---|
| `PATH` | 要掃描的目錄，可多個 | （必填） |
| `--min-size SIZE` | 忽略小於此大小的檔案，如 `4K`、`1.5MB`、`2G` | `1`（忽略空檔） |
| `--exclude GLOB` | 排除符合的檔名或路徑，可重複使用 | 無 |
| `--no-default-excludes` | 不自動排除 `.git`、`.svn`、`.hg`、`node_modules`、`__pycache__` | 關閉 |
| `--keep POLICY` | 每組保留哪一個（見下表） | `first` |
| `--action ACTION` | `report` / `delete` / `hardlink` / `move` | `report` |
| `--move-to DIR` | `--action move` 時的目的目錄 | 無 |
| `--apply` | 真的執行動作；不加則只預覽 | 關閉 |
| `--json FILE` | 另外輸出 JSON 報告（`-` 表示輸出到 stdout） | 無 |
| `--workers N` | 平行雜湊的執行緒數 | CPU 數 × 2，最多 8 |
| `-q`, `--quiet` | 不顯示進度訊息 | 關閉 |

### 保留策略 `--keep`

| 值 | 保留的檔案 |
|---|---|
| `first` | 命令列中**最前面的目錄**裡的檔案；同目錄則依路徑排序 |
| `oldest` | 修改時間最舊的 |
| `newest` | 修改時間最新的 |
| `shortest` | 路徑最短的 |

平手時一律依「目錄順序 → 路徑」決定，所以結果是穩定可重現的。

### 動作 `--action`

| 值 | 行為 |
|---|---|
| `report` | 只列出重複，並標示會保留哪一個 |
| `delete` | 刪除重複的檔案，每組保留一份 |
| `hardlink` | 把重複檔換成指向保留檔的硬連結：路徑都還在，但只佔一份空間。不能跨磁碟 |
| `move` | 搬到 `--move-to`，檔名加上雜湊前綴避免衝突，之後可自行檢查再清除 |

## 常用範例

```bash
# 只處理 4KB 以上的檔案，排除暫存檔
python3 dupekit.py ~/Downloads --min-size 4K --exclude "*.tmp" --exclude "*.part"

# 保留最舊的那份，其餘搬去隔離區（最保守的清理方式）
python3 dupekit.py ~/Downloads --keep oldest --action move --move-to ~/_dups --apply

# 輸出 JSON 給其他工具處理
python3 dupekit.py ~/Photos --json report.json -q

# 在腳本中使用：只取 JSON
python3 dupekit.py ~/Photos -q --json - | jq '.summary'
```

## 運作原理

```
所有檔案
  │  1. 依大小分組（只需 stat，不讀內容）            大小唯一 → 淘汰
  ▼
大小相同的候選
  │  2. 部分雜湊：檔頭 / 檔中 / 檔尾各 64KB          不同 → 淘汰
  ▼
取樣相同的候選
  │  3. 完整 BLAKE2b 雜湊（1MB 串流讀取）            不同 → 淘汰
  ▼
重複組
  │  4. 執行動作前，逐位元組比對保留檔與目標檔
  ▼
delete / hardlink / move
```

多數檔案在第 1、2 階段就被淘汰，所以大型目錄也能很快掃完。

## 安全機制

- **預設不變更任何檔案**；`delete`、`hardlink`、`move` 都必須加 `--apply`
- **每組至少保留一份**，不會把全部副本都處理掉
- **逐位元組重新驗證**：掃描之後被修改、被刪除的檔案會被略過並標為錯誤，不會誤動
- **保留檔不存在就不動作**
- **硬連結採原子替換**：先建立暫存連結，再用 `os.replace` 取代原檔；失敗時會清掉暫存檔，原檔不受影響
- **硬連結不算重複**：指向同一個 inode 的檔案本來就不佔額外空間，掃描時只計一次
- **符號連結一律略過**，不跟隨、不處理
- `--move-to` 不可位於被掃描的目錄內，避免自己掃到自己搬過去的檔案

## 結束代碼

| 代碼 | 意義 |
|---|---|
| `0` | 正常完成 |
| `1` | 套用動作時，至少有一項失敗（詳見報告中以 `!` 開頭的行） |
| `2` | 參數錯誤（目錄不存在、缺少 `--move-to`、大小格式錯誤等） |

## JSON 報告格式

```json
{
  "summary": {
    "groups": 102,
    "reclaimable_bytes": 44695552,
    "visited": 605,
    "hardlink_skipped": 0,
    "too_small": 0,
    "unreadable": 0
  },
  "groups": [
    { "size": 20971520, "digest": "d870e175…", "files": ["photos/trip.raw", "…"] }
  ],
  "actions": [
    { "kind": "hardlink", "path": "…", "keeper": "…", "size": 20971520,
      "digest": "…", "status": "planned", "detail": "" }
  ],
  "errors": []
}
```

`status` 為 `planned`（預覽）、`done`（成功）或 `error`（失敗，原因在 `detail`）。

## 測試

```bash
python3 -m unittest test_dupekit -v
```

共 22 項測試，涵蓋：

- 基本重複偵測、大小相同但內容不同
- 取樣雜湊撞車（只有未取樣區不同的大檔）
- 硬連結、符號連結、空檔、`--min-size`、預設排除
- 四種保留策略
- 預覽不變更檔案、刪除、硬連結、搬移
- 掃描後檔案被修改、保留檔消失時的安全處理
- CLI 參數錯誤與 JSON 輸出

## 已知限制

- 只比對**位元組完全相同**的檔案，不處理相似圖片或僅 metadata 不同的檔案
- 不跟隨符號連結
- 硬連結無法跨磁碟 / 跨檔案系統，跨裝置時該項會標為失敗並保持原狀
- 每次執行都重新計算雜湊，沒有快取

## 可能的擴充方向

- 互動式逐組確認
- 以 SQLite 快取雜湊（以路徑 + 大小 + mtime 為 key），加速重複掃描
- 感知雜湊（pHash）找出相似照片
- 輸出 HTML 報告
