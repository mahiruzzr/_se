const express = require("express");
const { Pool } = require("pg");

const appVersion = require("./package.json").version;

const pool = new Pool({
  host: process.env.PGHOST || "db",
  port: Number(process.env.PGPORT || 5432),
  user: process.env.PGUSER || "demo",
  password: process.env.PGPASSWORD || "demo_password_2026",
  database: process.env.PGDATABASE || "demo",
});

pool.on("error", (error) => {
  console.error("unexpected database error", error.message);
});

const startedAt = Date.now();

const app = express();
app.use(express.json());

app.get("/health", (request, response) => {
  response.json({
    status: "ok",
    service: "node-api",
    version: appVersion,
    node_version: process.version,
    uptime_seconds: Math.floor((Date.now() - startedAt) / 1000),
  });
});

app.get("/visits", async (request, response) => {
  try {
    const { rows } = await pool.query("SELECT count, updated_at FROM visits WHERE id = 1");
    response.json({ count: Number(rows[0].count), updated_at: rows[0].updated_at });
  } catch (error) {
    response.status(503).json({ error: "database_unavailable", message: error.message });
  }
});

app.post("/visits", async (request, response) => {
  try {
    const { rows } = await pool.query(
      "UPDATE visits SET count = count + 1, updated_at = now() WHERE id = 1 RETURNING count, updated_at"
    );
    response.json({ count: Number(rows[0].count), updated_at: rows[0].updated_at });
  } catch (error) {
    response.status(503).json({ error: "database_unavailable", message: error.message });
  }
});

app.get("/messages", async (request, response) => {
  try {
    const { rows } = await pool.query(
      "SELECT id, author, content, created_at FROM messages ORDER BY created_at DESC LIMIT 20"
    );
    response.json({ messages: rows });
  } catch (error) {
    response.status(503).json({ error: "database_unavailable", message: error.message });
  }
});

app.post("/messages", async (request, response) => {
  const author = String((request.body && request.body.author) || "").trim();
  const content = String((request.body && request.body.content) || "").trim();

  if (!author || !content || author.length > 50 || content.length > 500) {
    response.status(400).json({ error: "invalid_input" });
    return;
  }

  try {
    const { rows } = await pool.query(
      "INSERT INTO messages (author, content) VALUES ($1, $2) RETURNING id, author, content, created_at",
      [author, content]
    );
    response.status(201).json({ message: rows[0] });
  } catch (error) {
    response.status(503).json({ error: "database_unavailable", message: error.message });
  }
});

app.get("/stats", async (request, response) => {
  try {
    const [postgres, counts] = await Promise.all([
      pool.query("SELECT version() AS postgres_version, current_database() AS database"),
      pool.query(
        "SELECT (SELECT count FROM visits WHERE id = 1) AS visits_count, (SELECT count(*) FROM messages) AS messages_count"
      ),
    ]);

    response.json({
      postgres_version: postgres.rows[0].postgres_version.split(" ").slice(0, 2).join(" "),
      database: postgres.rows[0].database,
      visits_count: Number(counts.rows[0].visits_count),
      messages_count: Number(counts.rows[0].messages_count),
      node_version: process.version,
    });
  } catch (error) {
    response.status(503).json({ error: "database_unavailable", message: error.message });
  }
});

const port = Number(process.env.PORT || 3000);
app.listen(port, "0.0.0.0", () => {
  console.log(`node-api v${appVersion} listening on port ${port}`);
});
