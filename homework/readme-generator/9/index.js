// edge-blog：部落格 + 留言板。Worker 負責 /api/*，其餘由 public/ 靜態資源提供。
const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

const enc = new TextEncoder();
const safeEqual = (a, b) => {
  const x = enc.encode(a), y = enc.encode(b);
  return x.length === y.length && crypto.subtle.timingSafeEqual(x, y);
};
const clean = (v, max) => (typeof v === "string" ? v.trim().slice(0, max) : "");

// 第一次請求時自動建表（IF NOT EXISTS，重複執行無害），部署時不必另外跑 SQL
let ready;
const init = (db) =>
  (ready ??= db
    .batch([
      db.prepare(`CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')))`),
      db.prepare(`CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')))`),
      db.prepare("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id)"),
    ])
    .catch((e) => {
      ready = null;
      throw e;
    }));

async function route(req, env, pathname) {
  const m = req.method;
  const db = env.DB;
  const isAdmin = () =>
    !!env.ADMIN_TOKEN && safeEqual(req.headers.get("x-admin-token") ?? "", env.ADMIN_TOKEN);
  const needAdmin = () => (isAdmin() ? null : json({ error: "需要管理金鑰" }, 401));
  const body = () => req.json().catch(() => ({}));

  if (pathname === "/api/me" && m === "GET") return json({ admin: isAdmin() });

  if (pathname === "/api/posts") {
    if (m === "GET") {
      const { results } = await db
        .prepare(
          `SELECT p.id, p.title, substr(p.body, 1, 120) AS excerpt, p.created_at,
                  (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comments
           FROM posts p ORDER BY p.id DESC LIMIT 50`
        )
        .all();
      return json(results);
    }
    if (m === "POST") {
      const denied = needAdmin();
      if (denied) return denied;
      const b = await body();
      const title = clean(b.title, 100), text = clean(b.body, 20000);
      if (!title || !text) return json({ error: "標題與內容都要填" }, 400);
      const row = await db
        .prepare("INSERT INTO posts (title, body) VALUES (?, ?) RETURNING id")
        .bind(title, text)
        .first();
      return json(row, 201);
    }
  }

  let r = pathname.match(/^\/api\/posts\/(\d+)$/);
  if (r) {
    const id = Number(r[1]);
    if (m === "GET") {
      const post = await db.prepare("SELECT * FROM posts WHERE id = ?").bind(id).first();
      if (!post) return json({ error: "找不到這篇文章" }, 404);
      const { results } = await db
        .prepare("SELECT id, author, body, created_at FROM comments WHERE post_id = ? ORDER BY id")
        .bind(id)
        .all();
      return json({ ...post, comments: results });
    }
    if (m === "DELETE") {
      const denied = needAdmin();
      if (denied) return denied;
      await db.batch([
        db.prepare("DELETE FROM comments WHERE post_id = ?").bind(id),
        db.prepare("DELETE FROM posts WHERE id = ?").bind(id),
      ]);
      return json({ ok: true });
    }
  }

  r = pathname.match(/^\/api\/posts\/(\d+)\/comments$/);
  if (r && m === "POST") {
    const id = Number(r[1]);
    const b = await body();
    const author = clean(b.author, 30) || "匿名";
    const text = clean(b.body, 500);
    if (!text) return json({ error: "留言內容不能空白" }, 400);
    const post = await db.prepare("SELECT id FROM posts WHERE id = ?").bind(id).first();
    if (!post) return json({ error: "找不到這篇文章" }, 404);
    const row = await db
      .prepare("INSERT INTO comments (post_id, author, body) VALUES (?, ?, ?) RETURNING id")
      .bind(id, author, text)
      .first();
    return json(row, 201);
  }

  r = pathname.match(/^\/api\/comments\/(\d+)$/);
  if (r && m === "DELETE") {
    const denied = needAdmin();
    if (denied) return denied;
    await db.prepare("DELETE FROM comments WHERE id = ?").bind(Number(r[1])).run();
    return json({ ok: true });
  }

  return json({ error: "找不到" }, 404);
}

export default {
  async fetch(req, env) {
    try {
      await init(env.DB);
      return await route(req, env, new URL(req.url).pathname);
    } catch (e) {
      console.error(e);
      return json({ error: "伺服器發生錯誤" }, 500);
    }
  },
};
