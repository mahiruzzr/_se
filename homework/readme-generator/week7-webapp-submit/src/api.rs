use std::sync::{Arc, Mutex};

use axum::{
    extract::{Path, State},
    http::{header, StatusCode},
    response::{Html, IntoResponse, Response},
    routing::{delete, get, patch},
    Json, Router,
};
use serde::{Deserialize, Serialize};

use crate::domain::{Store, Task, ValidationError};

type SharedStore = Arc<Mutex<Store>>;

#[derive(Serialize)]
struct Health {
    status: &'static str,
}

#[derive(Deserialize)]
struct CreateTaskRequest {
    title: String,
}

#[derive(Serialize)]
struct ErrorBody {
    error: &'static str,
    message: &'static str,
}

pub fn create_app() -> Router {
    Router::new()
        .route("/", get(index))
        .route("/app.js", get(app_js))
        .route("/styles.css", get(styles_css))
        .route("/favicon.ico", get(favicon))
        .route("/api/health", get(health))
        .route("/api/tasks", get(list_tasks).post(create_task))
        .route("/api/tasks/{id}/toggle", patch(toggle_task))
        .route("/api/tasks/{id}", delete(delete_task))
        .with_state(Arc::new(Mutex::new(Store::new())))
}

async fn health() -> Json<Health> {
    Json(Health { status: "ok" })
}

async fn list_tasks(State(store): State<SharedStore>) -> Json<Vec<Task>> {
    let tasks = store.lock().unwrap().list();
    Json(tasks)
}

async fn create_task(
    State(store): State<SharedStore>,
    Json(payload): Json<CreateTaskRequest>,
) -> Result<(StatusCode, Json<Task>), (StatusCode, Json<ErrorBody>)> {
    store
        .lock()
        .unwrap()
        .create(&payload.title)
        .map(|task| (StatusCode::CREATED, Json(task)))
        .map_err(validation_error)
}

async fn toggle_task(
    State(store): State<SharedStore>,
    Path(id): Path<u64>,
) -> Result<Json<Task>, (StatusCode, Json<ErrorBody>)> {
    store
        .lock()
        .unwrap()
        .toggle(id)
        .map(Json)
        .ok_or_else(not_found)
}

async fn delete_task(
    State(store): State<SharedStore>,
    Path(id): Path<u64>,
) -> Result<StatusCode, (StatusCode, Json<ErrorBody>)> {
    if store.lock().unwrap().delete(id) {
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(not_found())
    }
}

fn validation_error(error: ValidationError) -> (StatusCode, Json<ErrorBody>) {
    (
        StatusCode::BAD_REQUEST,
        Json(ErrorBody {
            error: error.code(),
            message: error.message(),
        }),
    )
}

fn not_found() -> (StatusCode, Json<ErrorBody>) {
    (
        StatusCode::NOT_FOUND,
        Json(ErrorBody {
            error: "not_found",
            message: "找不到這個任務",
        }),
    )
}

async fn index() -> Html<&'static str> {
    Html(include_str!("../static/index.html"))
}

async fn app_js() -> Response {
    (
        [(header::CONTENT_TYPE, "text/javascript; charset=utf-8")],
        include_str!("../static/app.js"),
    )
        .into_response()
}

async fn styles_css() -> Response {
    (
        [(header::CONTENT_TYPE, "text/css; charset=utf-8")],
        include_str!("../static/styles.css"),
    )
        .into_response()
}

async fn favicon() -> StatusCode {
    StatusCode::NO_CONTENT
}
