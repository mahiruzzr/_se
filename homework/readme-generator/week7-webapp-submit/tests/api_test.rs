use reqwest::StatusCode;
use serde_json::{json, Value};
use week7_task_board::create_app;

async fn spawn_app() -> String {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("failed to bind test server");

    let address = listener.local_addr().expect("failed to read address");

    tokio::spawn(async move {
        axum::serve(listener, create_app())
            .await
            .expect("test server failed");
    });

    format!("http://{address}")
}

async fn post_task(client: &reqwest::Client, base: &str, title: &str) -> reqwest::Response {
    client
        .post(format!("{base}/api/tasks"))
        .json(&json!({ "title": title }))
        .send()
        .await
        .expect("failed to POST task")
}

async fn create_task(client: &reqwest::Client, base: &str, title: &str) -> Value {
    let response = post_task(client, base, title).await;
    assert_eq!(response.status(), StatusCode::CREATED);
    response.json().await.expect("failed to decode task")
}

async fn list_tasks(client: &reqwest::Client, base: &str) -> Vec<Value> {
    let response = client
        .get(format!("{base}/api/tasks"))
        .send()
        .await
        .expect("failed to GET tasks");

    assert_eq!(response.status(), StatusCode::OK);
    response.json().await.expect("failed to decode task list")
}

#[tokio::test]
async fn health_endpoint_reports_ok() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let response = client
        .get(format!("{base}/api/health"))
        .send()
        .await
        .expect("failed to GET health");

    assert_eq!(response.status(), StatusCode::OK);
    let body: Value = response.json().await.expect("failed to decode health");
    assert_eq!(body, json!({ "status": "ok" }));
}

#[tokio::test]
async fn creates_tasks_and_returns_them_in_order() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let first = create_task(&client, &base, "  買牛奶  ").await;
    let second = create_task(&client, &base, "寫週報").await;

    assert_eq!(first["id"], 1);
    assert_eq!(first["title"], "買牛奶");
    assert_eq!(first["completed"], false);
    assert_eq!(second["id"], 2);

    let tasks = list_tasks(&client, &base).await;
    assert_eq!(tasks.len(), 2);
    assert_eq!(tasks[0]["title"], "買牛奶");
    assert_eq!(tasks[1]["title"], "寫週報");
}

#[tokio::test]
async fn rejects_blank_title_with_bad_request() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let response = post_task(&client, &base, " \t　 ").await;

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let body: Value = response.json().await.expect("failed to decode error");
    assert_eq!(body["error"], "empty_title");
    assert_eq!(body["message"], "任務名稱不能為空");
    assert!(list_tasks(&client, &base).await.is_empty());
}

#[tokio::test]
async fn rejects_title_over_120_characters() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();
    let title = "好".repeat(121);

    let response = post_task(&client, &base, &title).await;

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    let body: Value = response.json().await.expect("failed to decode error");
    assert_eq!(body["error"], "title_too_long");
    assert!(list_tasks(&client, &base).await.is_empty());
}

#[tokio::test]
async fn accepts_title_with_exactly_120_characters() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();
    let title = "好".repeat(120);

    let task = create_task(&client, &base, &title).await;

    assert_eq!(task["title"].as_str().unwrap().chars().count(), 120);
}

#[tokio::test]
async fn toggles_completion_through_the_api() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();
    let task = create_task(&client, &base, "重構 API").await;
    let id = task["id"].as_u64().expect("task id");

    let response = client
        .patch(format!("{base}/api/tasks/{id}/toggle"))
        .send()
        .await
        .expect("failed to PATCH toggle");

    assert_eq!(response.status(), StatusCode::OK);
    let completed: Value = response.json().await.expect("failed to decode task");
    assert_eq!(completed["completed"], true);

    let tasks = list_tasks(&client, &base).await;
    assert_eq!(tasks[0]["completed"], true);

    let response = client
        .patch(format!("{base}/api/tasks/{id}/toggle"))
        .send()
        .await
        .expect("failed to PATCH toggle again");

    let reopened: Value = response.json().await.expect("failed to decode task");
    assert_eq!(reopened["completed"], false);
}

#[tokio::test]
async fn returns_not_found_for_unknown_task() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let toggle_response = client
        .patch(format!("{base}/api/tasks/999/toggle"))
        .send()
        .await
        .expect("failed to PATCH unknown task");

    assert_eq!(toggle_response.status(), StatusCode::NOT_FOUND);
    let body: Value = toggle_response
        .json()
        .await
        .expect("failed to decode error");
    assert_eq!(body["error"], "not_found");

    let delete_response = client
        .delete(format!("{base}/api/tasks/999"))
        .send()
        .await
        .expect("failed to DELETE unknown task");

    assert_eq!(delete_response.status(), StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn deletes_only_the_requested_task() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();
    let first = create_task(&client, &base, "任務 A").await;
    let second = create_task(&client, &base, "任務 B").await;
    let first_id = first["id"].as_u64().expect("task id");

    let response = client
        .delete(format!("{base}/api/tasks/{first_id}"))
        .send()
        .await
        .expect("failed to DELETE task");

    assert_eq!(response.status(), StatusCode::NO_CONTENT);

    let tasks = list_tasks(&client, &base).await;
    assert_eq!(tasks.len(), 1);
    assert_eq!(tasks[0]["id"], second["id"]);

    let response = client
        .delete(format!("{base}/api/tasks/{first_id}"))
        .send()
        .await
        .expect("failed to DELETE task again");

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn separate_servers_have_isolated_state() {
    let first_base = spawn_app().await;
    let second_base = spawn_app().await;
    let client = reqwest::Client::new();

    create_task(&client, &first_base, "只存在第一台伺服器").await;

    assert_eq!(list_tasks(&client, &first_base).await.len(), 1);
    assert!(list_tasks(&client, &second_base).await.is_empty());
}
