use week7_task_board::create_app;

#[tokio::main]
async fn main() {
    let port = std::env::var("PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3000);

    let address = format!("127.0.0.1:{port}");
    let listener = tokio::net::TcpListener::bind(&address)
        .await
        .expect("failed to bind address");

    println!("Task Board running at http://{address}");

    axum::serve(listener, create_app())
        .await
        .expect("server failed");
}
