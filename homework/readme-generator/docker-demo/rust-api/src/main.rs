use std::time::Instant;

use axum::{routing::get, Json, Router};
use serde_json::{json, Value};

#[tokio::main]
async fn main() {
    let started_at = Instant::now();

    let app = Router::new()
        .route("/health", get(health))
        .route("/info", get(move || info(started_at)));

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080")
        .await
        .expect("failed to bind port 8080");
    println!("rust-api listening on port 8080");

    axum::serve(listener, app).await.expect("server error");
}

async fn health() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "rust-api",
        "version": env!("CARGO_PKG_VERSION"),
    }))
}

async fn info(started_at: Instant) -> Json<Value> {
    Json(json!({
        "service": "rust-api",
        "version": env!("CARGO_PKG_VERSION"),
        "hostname": hostname(),
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "cpu_cores": std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1),
        "uptime_seconds": started_at.elapsed().as_secs(),
    }))
}

fn hostname() -> String {
    std::fs::read_to_string("/etc/hostname")
        .map(|value| value.trim().to_string())
        .unwrap_or_else(|_| "unknown".to_string())
}
