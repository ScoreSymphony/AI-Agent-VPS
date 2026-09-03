#![forbid(unsafe_code)]

use executor_sidecar::{build_router, SidecarConfig, SidecarState};
use std::{collections::BTreeSet, env, net::SocketAddr, path::PathBuf};

const DEFAULT_ADDR: &str = "127.0.0.1:8787";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr: SocketAddr = env::var("FORGE_EXECUTOR_SIDECAR_ADDR")
        .unwrap_or_else(|_| DEFAULT_ADDR.to_owned())
        .parse()?;
    if !addr.ip().is_loopback() {
        return Err("FORGE_EXECUTOR_SIDECAR_ADDR must bind to a loopback address".into());
    }

    let workspace_root = env::var_os("FORGE_EXECUTOR_WORKSPACE_ROOT")
        .map(PathBuf::from)
        .unwrap_or(env::current_dir()?);
    let logs_root = env::var_os("FORGE_EXECUTOR_LOGS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| workspace_root.join(".forge-executor-sidecar").join("logs"));
    let allowed = env::var("FORGE_EXECUTOR_ALLOWED_TYPES")
        .unwrap_or_else(|_| "null".to_owned())
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .collect::<BTreeSet<_>>();

    if allowed.is_empty() {
        return Err("FORGE_EXECUTOR_ALLOWED_TYPES must contain at least one executor type".into());
    }

    let state = SidecarState::new(SidecarConfig::new(
        workspace_root,
        logs_root,
        allowed.into_iter(),
    ))
    .await?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, build_router(state)).await?;
    Ok(())
}
