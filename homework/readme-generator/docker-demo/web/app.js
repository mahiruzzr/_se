const REFRESH_INTERVAL_MS = 10000;

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function setServiceStatus(name, ok, detail) {
  const dot = document.getElementById(`dot-${name}`);
  dot.classList.toggle("ok", ok);
  dot.classList.toggle("fail", !ok);
  document.getElementById(`detail-${name}`).textContent = detail;
}

async function checkServices() {
  setServiceStatus("nginx", true, "本頁面即由 nginx 提供");

  try {
    const health = await fetchJSON("/api/node/health");
    setServiceStatus("node", true, `${health.service} v${health.version} ｜ up ${health.uptime_seconds}s`);
  } catch {
    setServiceStatus("node", false, "無法連線");
  }

  try {
    const health = await fetchJSON("/api/rust/health");
    setServiceStatus("rust", true, `${health.service} v${health.version}`);
  } catch {
    setServiceStatus("rust", false, "無法連線");
  }

  try {
    const stats = await fetchJSON("/api/node/stats");
    setServiceStatus("postgres", true, `${stats.postgres_version} ｜ db=${stats.database}`);
  } catch {
    setServiceStatus("postgres", false, "無法連線（透過 node-api 檢查）");
  }

  document.getElementById("status-updated").textContent =
    `（更新於 ${new Date().toLocaleTimeString()}）`;
}

async function loadVisits(increment) {
  try {
    const data = await fetchJSON("/api/node/visits", increment ? { method: "POST" } : {});
    document.getElementById("visits-count").textContent = data.count.toLocaleString();
    document.getElementById("visits-updated").textContent =
      `最後更新：${new Date(data.updated_at).toLocaleString()}`;
  } catch {
    document.getElementById("visits-count").textContent = "DB 無法連線";
    document.getElementById("visits-updated").textContent = "";
  }
}

function renderMessages(messages) {
  const list = document.getElementById("message-list");
  list.innerHTML = "";

  if (messages.length === 0) {
    const item = document.createElement("li");
    item.className = "muted small";
    item.textContent = "目前沒有留言";
    list.append(item);
    return;
  }

  for (const message of messages) {
    const item = document.createElement("li");

    const head = document.createElement("div");
    head.className = "message-head";

    const author = document.createElement("strong");
    author.textContent = message.author;

    const time = document.createElement("span");
    time.className = "muted small";
    time.textContent = new Date(message.created_at).toLocaleString();

    head.append(author, time);

    const body = document.createElement("p");
    body.textContent = message.content;

    item.append(head, body);
    list.append(item);
  }
}

async function loadMessages() {
  try {
    const data = await fetchJSON("/api/node/messages");
    renderMessages(data.messages);
  } catch {
    renderMessages([]);
    document.getElementById("message-list").firstChild.textContent =
      "無法讀取留言（資料庫或 node-api 未就緒）";
  }
}

function formatUptime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours > 0) {
    return `${hours} 小時 ${minutes} 分 ${rest} 秒`;
  }
  if (minutes > 0) {
    return `${minutes} 分 ${rest} 秒`;
  }
  return `${rest} 秒`;
}

async function loadRustInfo() {
  const dl = document.getElementById("rust-info");
  try {
    const info = await fetchJSON("/api/rust/info");
    const rows = [
      ["hostname（容器 ID）", info.hostname],
      ["作業系統（容器內）", `${info.os} / ${info.arch}`],
      ["CPU 核心數", String(info.cpu_cores)],
      ["服務運行時間", formatUptime(info.uptime_seconds)],
      ["服務版本", `rust-api v${info.version}`],
    ];

    dl.innerHTML = "";
    for (const [key, value] of rows) {
      const wrap = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = value;
      wrap.append(dt, dd);
      dl.append(wrap);
    }
  } catch {
    dl.innerHTML = "";
    const wrap = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = "無法連線";
    const dd = document.createElement("dd");
    dd.textContent = "rust-api 未就緒";
    wrap.append(dt, dd);
    dl.append(wrap);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  checkServices();
  loadVisits(true);
  loadMessages();
  loadRustInfo();

  setInterval(checkServices, REFRESH_INTERVAL_MS);
  setInterval(loadRustInfo, REFRESH_INTERVAL_MS);

  document.getElementById("visit-btn").addEventListener("click", () => loadVisits(true));

  document.getElementById("message-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    const authorInput = document.getElementById("message-author");
    const contentInput = document.getElementById("message-content");

    try {
      await fetchJSON("/api/node/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author: authorInput.value, content: contentInput.value }),
      });
      contentInput.value = "";
      await loadMessages();
    } catch (error) {
      alert(`留言失敗：${error.message}`);
    }
  });
});
