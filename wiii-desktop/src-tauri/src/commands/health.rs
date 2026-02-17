use tokio::net::TcpStream;

/// Quick TCP connectivity check to verify the server is reachable.
/// Faster than a full HTTP request — used during settings configuration.
#[tauri::command]
pub async fn check_server_reachable(host: String, port: u16) -> Result<bool, String> {
    let addr = format!("{}:{}", host, port);
    match tokio::time::timeout(
        std::time::Duration::from_secs(3),
        TcpStream::connect(&addr),
    )
    .await
    {
        Ok(Ok(_)) => Ok(true),
        Ok(Err(e)) => Err(format!("Connection failed: {}", e)),
        Err(_) => Err("Connection timed out (3s)".to_string()),
    }
}
