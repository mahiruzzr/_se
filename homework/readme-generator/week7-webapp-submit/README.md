# Week 7 · Task Board

第七週測試作業：一個以 **Rust + Axum** 開發的任務清單網站，完整示範三層測試：

1. **單元測試**：Rust 伺服器端網域邏輯（`cargo test --lib`）
2. **系統測試**：對真實 HTTP Web API 發出請求（`cargo test --test api_test`）
3. **E2E 測試**：Playwright 無頭 Chromium 操作真實瀏覽器（`npm run test:e2e`）

前端使用原生 HTML / CSS / JavaScript，不需要打包工具。

## 快速開始

環境需求：Rust 1.80+、Node.js 18+。

```powershell
cargo run
# 開啟 http://127.0.0.1:3000
```

指定其他埠號：

```powershell
$env:PORT = 8080
cargo run
```

## 測試指令

```powershell
# 1. 單元測試（只測 domain，共 9 個）
cargo test --lib

# 2. 系統測試（實際啟動伺服器 + HTTP 請求，共 9 個）
cargo test --test api_test

# 以上兩層一起跑
cargo test

# 3. E2E 測試（首次需安裝瀏覽器，共 4 個）
npm install
npx playwright install chromium
npm run test:e2e
```

E2E 會由 `playwright.config.js` 自動啟動伺服器（PORT=3100），不需要手動開 `cargo run`。
每個測試開始前會透過 API 清空任務，確保測試互不影響。

進階選項：

```powershell
npm run test:e2e:headed   # 顯示瀏覽器
npm run test:e2e:report   # 開啟 HTML 報告
```

## 三層測試設計

| 層級 | 測什麼 | 工具 | 位置 | 數量 |
| --- | --- | --- | --- | --- |
| 單元測試 | `Store` 的建立、驗證、切換完成、刪除、ID 遞增 | Rust `#[test]` | `src/domain.rs` | 9 |
| 系統測試 | 真實 HTTP 伺服器的狀態碼、JSON、驗證與資源生命週期 | reqwest + tokio | `tests/api_test.rs` | 9 |
| E2E 測試 | 使用者在瀏覽器新增、完成、刪除、篩選與重新載入 | Playwright / Chromium | `e2e/tasks.spec.js` | 4 |

### 1. 單元測試

針對 `src/domain.rs` 的 `Store`，不啟動伺服器、不碰網路：

- 空白/只有空白的標題會被拒絕
- 標題會去除前後空白
- 標題長度邊界：120 字可通過、121 字被拒絕（以 Unicode 字元計算）
- ID 會遞增，且新增後預設為未完成
- 切換完成狀態可來回切換
- 刪除只影響指定任務，重複刪除回傳 `false`
- 操作不存在的 ID 會得到 `None`

### 2. 系統測試（Web API）

每個測試用 `TcpListener` 綁定隨機埠，啟動真正的 Axum 伺服器，再以 reqwest 發送 HTTP 請求：

- `GET /api/health` 回傳 `{"status":"ok"}`
- 新增任務回傳 `201`，並可在清單中讀回
- 空白標題回傳 `400 empty_title`
- 超過 120 字回傳 `400 title_too_long`，且不會寫入資料
- 切換完成狀態回傳 `200`，再次切換可復原
- 不存在的任務回傳 `404 not_found`
- 刪除回傳 `204`，之後再刪除回傳 `404`
- 兩台獨立伺服器的資料互不共享

### 3. E2E 測試（Playwright）

`playwright.config.js` 會自動建置並啟動伺服器，測試透過語意化定位器（role / label）操作頁面：

- 新增任務 → 勾選完成 → 統計數字更新 → 重新載入後狀態保留
- 輸入空白名稱 → 顯示錯誤提示，清單不新增
- 刪除指定任務 → 其他任務不受影響
- 在「全部 / 進行中 / 已完成」之間切換篩選

首次執行 E2E 前必須安裝 Chromium：

```powershell
npx playwright install chromium
```

## 專案結構

```text
week7-webapp/
├─ src/
│  ├─ domain.rs        # Task、Store、驗證與單元測試
│  ├─ api.rs           # Axum 路由、handlers、靜態檔案
│  ├─ lib.rs           # 對外匯出 create_app
│  └─ main.rs          # 啟動伺服器（PORT 環境變數）
├─ static/
│  ├─ index.html
│  ├─ styles.css
│  └─ app.js
├─ tests/
│  └─ api_test.rs      # 系統測試
├─ e2e/
│  └─ tasks.spec.js    # Playwright E2E
├─ playwright.config.js
├─ package.json
└─ Cargo.toml
```

## Web API

| 方法 | 路徑 | 成功 | 失敗 |
| --- | --- | --- | --- |
| `GET` | `/api/health` | `200 {"status":"ok"}` | — |
| `GET` | `/api/tasks` | `200` 任務陣列 | — |
| `POST` | `/api/tasks` | `201` 新任務 | `400` 驗證錯誤 |
| `PATCH` | `/api/tasks/{id}/toggle` | `200` 更新後任務 | `404` |
| `DELETE` | `/api/tasks/{id}` | `204` | `404` |

任務物件：

```json
{ "id": 1, "title": "買牛奶", "completed": false }
```

錯誤物件：

```json
{ "error": "empty_title", "message": "任務名稱不能為空" }
```

驗證規則：標題去除前後空白後不可為空，最多 120 個字元。

## 備註

- 資料保存在記憶體中，伺服器重新啟動後會清空；重點在展示測試分層，不涉及資料庫。
- `cargo test` 會同時執行單元測試與系統測試；兩者都不需要網路。
- E2E 使用單一 worker，避免共用記憶體狀態造成競態。
