# Docker 微服務展示系統（學習記錄）

本專案是一份 Docker 學習作業：從零開始認識 Docker，並用 **Docker Compose** 打造一個可一鍵啟動的微服務系統。

系統包含四個容器化服務：

| 服務 | 技術 | 角色 |
|---|---|---|
| nginx | nginx:1.27-alpine | Web server + 反向代理（唯一對外入口） |
| node-api | Node.js 22 + Express | 主要業務 API（訪客計數、留言板），連接 PostgreSQL |
| rust-api | Rust + Axum | 系統資訊 API（回報容器 hostname、OS、CPU、uptime） |
| db | PostgreSQL 16 | 資料庫，資料存於具名資料卷 |

最後由一個簡易 Web 看板（純 HTML/CSS/JS）展示整個系統的即時狀態。

---

## 目錄

1. [Docker 學習筆記](#1-docker-學習筆記)
2. [系統架構](#2-系統架構)
3. [專案結構](#3-專案結構)
4. [快速開始](#4-快速開始)
5. [操作與驗證教學](#5-操作與驗證教學)
6. [Dockerfile 逐行解說](#6-dockerfile-逐行解說)
7. [docker-compose.yml 解說](#7-docker-composeyml-解說)
8. [API 一覽](#8-api-一覽)
9. [疑難排解](#9-疑難排解)
10. [學習心得](#10-學習心得)

---

## 1. Docker 學習筆記

### 1.1 Docker 是什麼？

Docker 是一套「容器化」工具。它把應用程式和它需要的所有依賴（函式庫、設定、執行環境）打包成一個**映像檔（Image）**，在任何裝有 Docker 的機器上都能用相同方式**執行（Container）**，解決了經典的「在我電腦上可以跑啊」問題。

容器與傳統虛擬機（VM）的差異：

| 比較項目 | 容器（Container） | 虛擬機（VM） |
|---|---|---|
| 隔離層級 | 作業系統層（共用核心） | 硬體層（各自完整 OS） |
| 啟動速度 | 秒級 | 分鐘級 |
| 資源消耗 | 低（MB 等級） | 高（GB 等級） |
| 映像檔大小 | 小 | 大 |

### 1.2 核心概念

| 名詞 | 說明 | 本專案對應 |
|---|---|---|
| Image（映像檔） | 唯讀的執行範本，由 Dockerfile 建置而成 | `docker-demo-node-api` |
| Container（容器） | Image 的執行實例，可啟動/停止/刪除 | `demo-nginx`、`demo-db` 等 |
| Dockerfile | 描述「如何建置 Image」的腳本 | `nginx/`、`node-api/`、`rust-api/` 各一份 |
| Volume（資料卷） | 容器外的持久化儲存，容器刪掉資料還在 | `pgdata`（PostgreSQL 資料） |
| Network（網路） | 容器之間的通訊管道，容器用「服務名」互相連線 | `frontend`、`backend` |
| Registry | 存放 Image 的倉庫 | Docker Hub（`nginx:1.27-alpine` 由此下載） |
| Docker Compose | 用一個 YAML 定義並啟動多容器系統 | `docker-compose.yml` |

一個好記的比喻：

- **Image** = 食譜（唯讀）
- **Container** = 照食譜做好的菜（可執行實例）
- **Volume** = 冰箱（資料放這裡才不會隨容器消失）
- **Network** = 廚房裡的傳菜窗口（容器之間的通道）

### 1.3 常用指令備忘錄

映像檔相關：

```bash
docker pull nginx:1.27-alpine        # 從 Docker Hub 下載映像檔
docker images                        # 列出本機所有映像檔
docker rmi <image>                   # 刪除映像檔
docker build -t myapp:1.0 .          # 用目前目錄的 Dockerfile 建置映像檔並命名
```

容器相關：

```bash
docker run -d -p 8080:80 --name web nginx:1.27-alpine   # 背景執行容器並對外開 8080 埠
docker ps                            # 列出執行中的容器
docker ps -a                         # 列出所有容器（含已停止）
docker logs -f web                   # 持續追蹤容器日誌
docker exec -it web sh               # 進入容器開互動 shell
docker stop web && docker rm web     # 停止並刪除容器
```

Compose 相關（本專案主要用這些）：

```bash
docker compose up -d --build         # 建置映像檔並在背景啟動所有服務
docker compose ps                    # 查看每個服務的狀態與健康檢查結果
docker compose logs -f node-api      # 追蹤特定服務的日誌
docker compose exec db psql -U demo -d demo   # 在 db 容器裡開 psql
docker compose down                  # 停止並刪除所有容器與網路（資料卷保留）
docker compose down -v               # 連資料卷一起刪除（資料歸零）
docker compose config                # 驗證並印出最終合併後的 compose 設定
```

---

## 2. 系統架構

```
                         frontend 網路                    backend 網路
                    ┌──────────────────────┐      ┌──────────────────────┐
瀏覽器 ──:8080──▶   │  nginx               │      │                      │
                    │   ├─ /      → 靜態頁 │      │                      │
                    │   ├─ /api/node/*  ───┼──▶   │  node-api ──▶ postgres
                    │   └─ /api/rust/*  ───┼──▶   │   (node-api 同時                      │
                    │                      │      │    在兩個網路)         │
                    │        rust-api ◀────┘      │                      │
                    └──────────────────────┘      └──────────────────────┘
```

請求流程：

1. 瀏覽器連到 `http://localhost:8080`（唯一對外埠）。
2. nginx 提供前端靜態檔案（`web/`），並把 `/api/node/*`、`/api/rust/*` 反向代理到對應服務。
3. `node-api` 收到請求後向 `db`（PostgreSQL）查詢或寫入。
4. `rust-api` 回傳容器自身的系統資訊，讓看板展示每個容器的獨立性。

設計重點：

- **網路隔離**：`db` 只在 `backend` 網路，nginx 碰不到資料庫；`node-api` 橫跨兩個網路才能轉發。
- **服務發現**：Compose 內建 DNS，容器直接用服務名（`db`、`node-api`）互相連線，不需要記 IP。
- **健康檢查**：`depends_on` + `condition: service_healthy` 確保啟動順序（db 先就緒 → node-api → nginx）。
- **資料持久化**：PostgreSQL 資料存在具名資料卷 `pgdata`，`docker compose down` 後再 `up`，資料仍在。

服務埠號總表：

| 服務 | 容器內埠 | 對外埠 | 對外開放嗎 |
|---|---|---|---|
| nginx | 80 | 8080（可用 `.env` 的 `WEB_PORT` 改） | 是（唯一入口） |
| node-api | 3000 | 無 | 否，只透過 nginx |
| rust-api | 8080 | 無 | 否，只透過 nginx |
| db | 5432 | 無 | 否，只有 backend 網路內可連 |

---

## 3. 專案結構

```
docker-demo/
├── README.md                 # 本文件（Docker 學習記錄）
├── docker-compose.yml        # 定義 4 個服務、2 個網路、1 個資料卷
├── .env                      # 環境變數（帳密、對外埠號）
├── .dockerignore             # 建置時排除的檔案
├── nginx/
│   ├── Dockerfile            # nginx 映像檔建置腳本
│   └── nginx.conf            # 反向代理與靜態檔設定
├── web/                      # 前端看板（會被 COPY 進 nginx 映像檔）
│   ├── index.html
│   ├── style.css
│   └── app.js
├── node-api/
│   ├── Dockerfile            # Node.js 映像檔建置腳本
│   ├── package.json
│   ├── package-lock.json
│   └── server.js             # Express API（訪客計數、留言板）
├── rust-api/
│   ├── Dockerfile            # Rust 多階段建置腳本
│   ├── Cargo.toml
│   ├── Cargo.lock
│   └── src/main.rs           # Axum API（系統資訊）
└── db/
    └── init.sql              # 資料庫初始化腳本（首次啟動自動執行）
```

---

## 4. 快速開始

### 4.1 安裝 Docker Desktop（Windows）

前置條件：Windows 10/11 + WSL2（本機已具備 Ubuntu-24.04）。

1. 安裝 Docker Desktop（任選一種）：

   ```powershell
   winget install Docker.DockerDesktop
   ```

   或到官方網站下載安裝檔：https://www.docker.com/products/docker-desktop/

2. 安裝完成後**重新開機**（或登出再登入）。
3. 從開始功能表啟動 **Docker Desktop**，等待左下角顯示 Engine running。
4. 開啟 PowerShell 驗證：

   ```powershell
   docker --version            # 應顯示 Docker version 27.x 以上
   docker compose version      # 應顯示 Docker Compose version v2.x
   docker run hello-world      # 能印出 Hello from Docker! 就代表安裝成功
   ```

### 4.2 啟動系統

在專案目錄開啟 PowerShell，執行：

```powershell
docker compose up --build -d
```

第一次執行會：下載 4 個映像檔（nginx / node / rust / postgres）→ 建置 3 個自訂映像檔（Rust 需要編譯，約 1~3 分鐘）→ 依健康檢查順序啟動容器。

確認狀態（全部應為 `healthy`）：

```powershell
docker compose ps
```

### 4.3 開啟看板

瀏覽器打開：

```
http://localhost:8080
```

看板上會看到：

- 系統架構圖與四個服務的即時狀態（每 10 秒自動更新）
- 訪客計數器（資料存 PostgreSQL，重啟不消失）
- 留言板（瀏覽器 → nginx → node-api → PostgreSQL 全鏈路示範）
- Rust API 回報的容器 hostname / OS / CPU / uptime

---

## 5. 操作與驗證教學

### 5.1 看日誌（排查問題的第一步）

```powershell
docker compose logs -f            # 全部服務
docker compose logs -f node-api   # 只看 node-api
docker compose logs -f db         # 只看資料庫
```

### 5.2 直接測試 API（繞過瀏覽器）

```powershell
curl http://localhost:8080/api/node/health
curl http://localhost:8080/api/rust/info
curl http://localhost:8080/api/node/stats
```

`/api/node/*` 由 nginx 轉給 node-api，`/api/rust/*` 轉給 rust-api。nginx 的職責就是「統一入口 + 路由分派」。

### 5.3 進入資料庫容器打 SQL

```powershell
docker compose exec db psql -U demo -d demo
```

進入後試試：

```sql
\dt                                       -- 列出資料表
SELECT * FROM visits;                     -- 訪客計數
SELECT * FROM messages ORDER BY id;       -- 留言板
SELECT version();                         -- PostgreSQL 版本
\q                                        -- 離開
```

### 5.4 驗證資料持久化（Docker 的重要觀念）

1. 在看板按幾次「+1 再訪一次」，記下訪客數。
2. 把整個系統砍掉：

   ```powershell
   docker compose down          # 容器全數刪除，但 pgdata 資料卷保留
   docker volume ls             # 可以看到 docker-demo_pgdata 還在
   ```

3. 重新啟動：

   ```powershell
   docker compose up -d
   ```

4. 再看板一次 —— 訪客數與留言都還在。這就是 Volume 的價值：**容器是拋棄式的，資料不是**。

若想歸零資料（例如重新測試 init.sql），執行 `docker compose down -v` 再 `up` 即可。

### 5.5 驗證網路隔離

nginx 在 `frontend` 網路，postgres 在 `backend` 網路，兩者不相通：

```powershell
docker compose exec nginx sh -c "wget -q -O - http://db:5432 || echo 'nginx 無法連上 db（正確！）'"
```

node-api 因為同時加入兩個網路，所以能正常連上 `db:5432`。

### 5.6 觀察容器各自獨立

看板上的 Rust API 容器資訊區塊會顯示 `hostname`，那其實就是容器 ID。執行：

```powershell
docker compose exec rust-api hostname    # 會與看板顯示的一致
docker compose exec rust-api cat /etc/os-release   # 容器內的 OS 與主機不同
```

這說明每個服務都跑在自己獨立的隔離環境中。

---

## 6. Dockerfile 逐行解說

### 6.1 nginx/Dockerfile

```dockerfile
FROM nginx:1.27-alpine
```
以官方 nginx 映像檔為基底（alpine 版，體積約 40MB）。`1.27` 是刻意釘住版本，避免 `latest` 哪天更新導致行為改變。

```dockerfile
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY web/ /usr/share/nginx/html/
```
把自訂設定覆蓋掉預設設定；把前端靜態檔放進 nginx 的網頁根目錄，前端因此由 nginx 直接提供，不需要另外的 node 程序。

```dockerfile
EXPOSE 80
```
宣告容器監聽 80 埠（純文件性質，實際對外埠由 compose 的 `ports` 決定）。

### 6.2 node-api/Dockerfile

```dockerfile
FROM node:22-alpine
WORKDIR /app
```
基底是 Node.js 22（alpine 版）；`WORKDIR` 設定後續指令的工作目錄（不存在會自動建立）。

```dockerfile
COPY node-api/package.json node-api/package-lock.json ./
RUN npm ci --omit=dev
```
**先只複製 package 檔再安裝依賴**，是 Docker layer 快取的關鍵技巧：只要 package 檔沒改，之後重新建置時這層直接吃快取，不必重新 `npm ci`。`npm ci` 依 lock 檔安裝、版本完全可重現；`--omit=dev` 不裝開發依賴。

```dockerfile
COPY node-api/server.js ./
ENV NODE_ENV=production
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]
```
最後才複製程式碼（程式碼常改動，放越後面越不會讓前面的快取失效）。`CMD` 是容器啟動時的預設指令。

### 6.3 rust-api/Dockerfile（多階段建置 multi-stage build）

```dockerfile
FROM rust:1-slim-bookworm AS builder
```
第一階段叫 `builder`，用來編譯。Rust 編譯需要完整工具鏈，映像檔很大（GB 等級）。

```dockerfile
COPY rust-api/Cargo.toml ./
RUN mkdir -p src && printf 'fn main() {}\n' > src/main.rs && cargo build --release && rm -rf src
```
先在「只有 Cargo.toml、假 main.rs」的狀態下編譯一次。這樣 **所有依賴套件（axum、tokio…）會先被編譯並快取**；之後只有 `src/` 的程式碼改動時，不必重編依賴，建置速度快好幾倍。

```dockerfile
COPY rust-api/src ./src
RUN touch src/main.rs && cargo build --release
```
複製真正的程式碼重新編譯。`touch` 強制更新時間戳，確保 cargo 一定重新編譯專案本體。

```dockerfile
FROM debian:bookworm-slim
```
第二階段：全新的精簡映像檔，只放「執行檔」，不放編譯器。這就是多階段建置的威力：**建置環境（GB）與執行環境（幾十 MB）分離**。

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
```
安裝 curl 供健康檢查用。`rm -rf /var/lib/apt/lists/*` 是清理 apt 快取、縮小映像檔的標準做法。

```dockerfile
COPY --from=builder /app/target/release/rust-api /usr/local/bin/rust-api
CMD ["rust-api"]
```
`COPY --from=builder` 從第一階段「借」編譯好的執行檔過來。最終映像檔裡完全沒有 Rust 編譯器。

---

## 7. docker-compose.yml 解說

```yaml
services:
  nginx: ...
  node-api: ...
  rust-api: ...
  db: ...
volumes:
  pgdata:
networks:
  frontend:
  backend:
```

Compose 檔的三個頂層區塊：`services`（要跑哪些容器）、`volumes`（持久化儲存）、`networks`（容器間的網路）。

各個關鍵設定：

| 設定 | 出現在 | 作用 |
|---|---|---|
| `build.context` + `build.dockerfile` | nginx / node-api / rust-api | 從專案根目錄的脈絡建置各自的 Dockerfile |
| `image: docker-demo-xxx` | 同上 | 建置出的映像檔固定命名，方便 `docker images` 辨認 |
| `container_name: demo-xxx` | 全部 | 固定容器名稱，方便教學指令操作 |
| `ports: "${WEB_PORT:-8080}:80"` | nginx | 主機 8080 對應容器 80；`.env` 沒設定時預設 8080 |
| `environment` | node-api / db | 用環境變數注入 DB 連線與帳密（不寫死在程式碼裡） |
| `depends_on` + `condition: service_healthy` | nginx / node-api | 等相依服務健康檢查通過才啟動，避免「啟動太快連不到 DB」 |
| `healthcheck` | 全部（db 用 pg_isready） | 定義「這個容器何謂健康」，`docker compose ps` 直接顯示 |
| `restart: unless-stopped` | 全部 | 容器意外死亡自動重啟（除非手動 stop）；Docker Desktop 重開機後服務自動回來 |
| `volumes: pgdata:/var/lib/postgresql/data` | db | 把資料目錄掛到具名資料卷 |
| `./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro` | db | 官方 postgres 映像檔的機制：**第一次**啟動且資料目錄為空時，自動執行此目錄內的 SQL |
| `networks` | 全部 | nginx + rust-api 在 frontend；node-api 同時在 frontend + backend；db 只在 backend |

為什麼 init.sql 有時「沒生效」？因為它只在資料卷為空（第一次啟動）時執行。要重跑就先 `docker compose down -v` 清掉資料卷。

`.env` 檔內容（Compose 會自動載入它做變數替換）：

```
POSTGRES_USER=demo
POSTGRES_PASSWORD=demo_password_2026
POSTGRES_DB=demo
WEB_PORT=8080
```

注意：此密碼僅為教學示範用。實務上 `.env` 不應提交進版控，應使用密鑰管理工具。

---

## 8. API 一覽

全部經由 nginx（`http://localhost:8080`）轉發：

| 方法 | 路徑 | 轉發目標 | 說明 |
|---|---|---|---|
| GET | `/` | nginx 靜態檔 | 前端看板 |
| GET | `/api/node/health` | node-api | 服務存活檢查 |
| GET | `/api/node/visits` | node-api | 讀取訪客計數 |
| POST | `/api/node/visits` | node-api | 訪客計數 +1 |
| GET | `/api/node/messages` | node-api | 讀取留言（最新 20 筆） |
| POST | `/api/node/messages` | node-api | 新增留言（JSON: `author`, `content`） |
| GET | `/api/node/stats` | node-api | PostgreSQL 版本、資料庫名稱、資料表統計 |
| GET | `/api/rust/health` | rust-api | 服務存活檢查 |
| GET | `/api/rust/info` | rust-api | 容器 hostname、OS、架構、CPU 核心數、uptime |

nginx 的轉發規則在 `nginx/nginx.conf`：`location /api/node/` 把 `/api/node/health` 轉成 `http://node-api:3000/health`（結尾斜線會把前綴去掉）。

---

## 9. 疑難排解

| 症狀 | 原因與解法 |
|---|---|
| `docker: command not found` | Docker Desktop 尚未安裝或安裝後未重開機；照 4.1 節安裝 |
| 啟動時 `port is already allocated` | 8080 被其他程式占用；改 `.env` 的 `WEB_PORT=8090` 後 `docker compose up -d` |
| 看板開啟後 node-api 紅燈 | node-api 可能還在等 db 健康檢查；`docker compose logs -f node-api` 看錯誤訊息 |
| init.sql 改了卻沒生效 | 初始化腳本只在資料卷為空時執行；`docker compose down -v` 後重新 `up` |
| 建置 rust-api 很久 | Rust 首次編譯依賴需數分鐘，屬正常；之後有快取會快很多 |
| 拉映像檔很慢 | 網路環境可設定 Docker Desktop 的 registry mirror，或先 `docker pull` 對應映像檔 |
| 路徑含中文或 OneDrive 同步造成建置怪怪的 | 建議把專案移到 `C:\docker-demo` 等純英文、非同步目錄；或暫停 OneDrive 同步 |
| WSL2 相關錯誤 | 在 PowerShell（系統管理員）執行 `wsl --update` 後重啟 Docker Desktop |
| 想看某個容器到底發生什麼事 | `docker compose logs <服務名>`；容器活著的話 `docker compose exec <服務名> sh` 進去查 |

---

## 10. 學習心得

這個專案涵蓋了 Docker 最核心的觀念與實務技巧：

1. **映像檔 vs 容器**：三個自訂服務各自有 Dockerfile，讓我理解「建置」與「執行」是兩件事。
2. **Layer 快取**：node-api 先 COPY `package.json` 再 COPY 程式碼；rust-api 用假 main.rs 先編依賴再編本體 —— 這兩個技巧在實務上能讓 CI 建置時間縮短數倍。
3. **多階段建置**：Rust 服務用兩階段把 GB 級建置環境與堪用的執行環境分離，最終映像檔只有幾十 MB。
4. **Docker Compose**：一個 YAML 描述整個系統（服務、網路、資料卷、啟動順序），`up` 一鍵起飛、`down` 一鍵收工。
5. **網路隔離**：frontend / backend 兩個網路讓資料庫不暴露於外，nginx 只做入口與路由。
6. **Healthcheck 與啟動順序**：`depends_on: condition: service_healthy` 解決了容器啟動時序問題，比 sleep 優雅得多。
7. **資料持久化**：Volume 讓「容器可拋棄、資料永留存」，`down` → `up` 實測資料仍在。
8. **12-Factor 精神**：帳密與連線資訊全部由環境變數注入，程式碼零寫死。

下一步可以挑戰的方向：CI/CD 自動建置映像檔並推送 Registry、加上 Redis 快取服務、用 Traefik 取代 nginx 做動態路由、或導入 Kubernetes 編排。
