# edge-blog

部落格 + 留言板，跑在 Cloudflare Workers，資料存 D1，靜態前端由 Workers Assets 提供。
自包含：clone 後 `npm install` + `npx wrangler deploy` 即可上線。

## 架構

```
瀏覽器 ──► Cloudflare 邊緣
            ├─ /            → public/index.html（靜態資源，SPA、hash 路由）
            └─ /api/*       → src/index.js（Worker）──► D1（posts、comments）
```

## 部署

```bash
npm install
npx wrangler login

# 1. 建立 D1，把回傳的 database_id 貼進 wrangler.jsonc
npx wrangler d1 create edge-blog-db

# 2. 設定管理金鑰（用來發文、刪除文章與留言），不會進 repo
npx wrangler secret put ADMIN_TOKEN

# 3. 上線
npx wrangler deploy
```

資料表由 Worker 在第一次請求時自動建立（`CREATE TABLE IF NOT EXISTS`），不必另外執行 SQL。
部署完成後，開網站右上角「管理登入」，輸入 ADMIN_TOKEN 即可發文。

## 本機開發

```bash
cp .dev.vars.example .dev.vars   # 內含 ADMIN_TOKEN=local-dev-token
npx wrangler dev                 # 本機會自動模擬 D1
```

## API

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/api/posts` | 公開 | 文章列表（最新 50 篇，含摘要與留言數） |
| POST | `/api/posts` | 管理 | 發布文章 `{title, body}` |
| GET | `/api/posts/:id` | 公開 | 單篇文章與留言 |
| DELETE | `/api/posts/:id` | 管理 | 刪除文章與其留言 |
| POST | `/api/posts/:id/comments` | 公開 | 留言 `{author, body}` |
| DELETE | `/api/comments/:id` | 管理 | 刪除留言 |
| GET | `/api/me` | 公開 | 檢查目前金鑰是否有效 |

管理權限以 `x-admin-token` 標頭驗證，比對使用 `crypto.subtle.timingSafeEqual`。

## 安全設計

- 前端用 `textContent` 建立節點，不拼 HTML，使用者輸入不會變成腳本。
- 所有 SQL 使用 `bind()` 參數綁定。
- 長度限制：標題 100、文章 20000、名稱 30、留言 500 字。

## 下一步

- 留言防濫用：在 Cloudflare 儀表板加 Rate Limiting 規則，或接 Turnstile。
- 檔案下載：加一個 R2 bucket 綁定，做附件上傳與下載。
- 自訂網域：Workers & Pages → edge-blog → Settings → Domains & Routes。
