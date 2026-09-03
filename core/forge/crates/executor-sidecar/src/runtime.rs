use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use cli_adapters::{default_registry, NullAdapter};
use executors::{
    AvailabilityStatus, ExecutionContext, ExecutionFailureClass, ExecutionOutcome,
    ExecutionResult, ExecutorError, FallbackExecutor, LogEntry, LogKind, LogReader, TaskExecutor,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::{BTreeSet, HashMap},
    io,
    path::{Path as FsPath, PathBuf},
    sync::Arc,
    time::Duration,
};
use tokio::sync::RwLock;
use uuid::Uuid;

pub const PROTOCOL_VERSION: &str = "forge-executor-sidecar/v1";
const DEFAULT_HEARTBEAT_SECONDS: u64 = 30;
const DEFAULT_LOG_PAGE_LIMIT: usize = 500;
const MAX_LOG_PAGE_LIMIT: usize = 2_000;
const SNAPSHOT_LOG_LIMIT: usize = 4_096;
const STATE_FILE_NAME: &str = "jobs.json";

#[derive(Debug, Clone)]
pub struct SidecarConfig {
    pub workspace_root: PathBuf,
    pub logs_root: PathBuf,
    pub allowed_executor_types: BTreeSet<String>,
}

impl SidecarConfig {
    pub fn new(
        workspace_root: impl Into<PathBuf>,
        logs_root: impl Into<PathBuf>,
        allowed_executor_types: impl IntoIterator<Item = String>,
    ) -> Self {
        Self {
            workspace_root: workspace_root.into(),
            logs_root: logs_root.into(),
            allowed_executor_types: allowed_executor_types.into_iter().collect(),
        }
    }
}

#[derive(Clone)]
pub struct SidecarState {
    executor: Arc<dyn TaskExecutor>,
    jobs: Arc<RwLock<JobStore>>,
    workspace_root: PathBuf,
    logs_root: PathBuf,
    state_path: PathBuf,
    allowed_executor_types: BTreeSet<String>,
    availability: Vec<ExecutorAvailability>,
}

impl SidecarState {
    pub async fn new(config: SidecarConfig) -> io::Result<Self> {
        tokio::fs::create_dir_all(&config.workspace_root).await?;
        tokio::fs::create_dir_all(&config.logs_root).await?;
        let workspace_root = tokio::fs::canonicalize(&config.workspace_root).await?;
        let logs_root = tokio::fs::canonicalize(&config.logs_root).await?;
        let state_path = logs_root.join(STATE_FILE_NAME);

        let mut jobs = load_job_store(&state_path).await?;
        jobs.rebuild_request_index();
        let mut recovered_interrupted = false;
        for record in jobs.by_execution.values_mut() {
            if record.status == SidecarExecutionStatus::Running {
                record.status = SidecarExecutionStatus::Failed;
                record.result_code = Some(1);
                record.error_code = Some("interrupted".to_owned());
                record.error_message = Some(
                    "executor sidecar restarted while the backend execution was running".to_owned(),
                );
                record.retryable = false;
                merge_metadata(
                    &mut record.metadata,
                    "recovery_required",
                    Value::Bool(true),
                );
                recovered_interrupted = true;
            }
        }
        if recovered_interrupted {
            persist_job_store(&state_path, &jobs).await?;
        }

        let mut registry = default_registry();
        registry.register(Box::new(NullAdapter::new()));

        let mut availability = registry
            .kinds()
            .into_iter()
            .map(|kind| {
                let status = registry
                    .get(&kind)
                    .map(|adapter| availability_name(&adapter.check_availability().status))
                    .unwrap_or("not_found");
                ExecutorAvailability {
                    executor_type: kind.to_string(),
                    status: status.to_owned(),
                }
            })
            .collect::<Vec<_>>();
        availability.sort_by(|left, right| left.executor_type.cmp(&right.executor_type));

        Ok(Self {
            executor: Arc::new(FallbackExecutor::new(Arc::new(registry))),
            jobs: Arc::new(RwLock::new(jobs)),
            workspace_root,
            logs_root,
            state_path,
            allowed_executor_types: config.allowed_executor_types,
            availability,
        })
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct JobStore {
    by_execution: HashMap<String, JobRecord>,
    by_request: HashMap<String, String>,
}

impl JobStore {
    fn rebuild_request_index(&mut self) {
        self.by_request.clear();
        for (execution_id, record) in &self.by_execution {
            self.by_request
                .insert(record.request_ref.clone(), execution_id.clone());
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct JobRecord {
    request_ref: String,
    execution_id: String,
    task_id: String,
    run_id: String,
    step_id: Option<String>,
    correlation_id: String,
    status: SidecarExecutionStatus,
    result_code: Option<i32>,
    output: Value,
    error_code: Option<String>,
    error_message: Option<String>,
    retryable: bool,
    retry_after_seconds: Option<f64>,
    metadata: Value,
    logs_path: PathBuf,
}

impl JobRecord {
    fn snapshot(&self, stdout: String, stderr: String, logs_has_more: bool) -> ExecutionSnapshot {
        let mut metadata = self.metadata.clone();
        merge_metadata(&mut metadata, "logs_has_more", Value::Bool(logs_has_more));
        ExecutionSnapshot {
            protocol_version: PROTOCOL_VERSION.to_owned(),
            request_ref: self.request_ref.clone(),
            execution_id: self.execution_id.clone(),
            task_id: self.task_id.clone(),
            run_id: self.run_id.clone(),
            step_id: self.step_id.clone(),
            correlation_id: self.correlation_id.clone(),
            status: self.status,
            result_code: self.result_code,
            output: self.output.clone(),
            stdout,
            stderr,
            artifacts: Vec::new(),
            error_code: self.error_code.clone(),
            error_message: self.error_message.clone(),
            retryable: self.retryable,
            retry_after_seconds: self.retry_after_seconds,
            metadata,
        }
    }

    fn matches_request(&self, request: &SubmitExecutionRequest) -> bool {
        self.request_ref == request.request_ref
            && self.task_id == request.task_id
            && self.run_id == request.run_id
            && self.step_id == request.step_id
            && self.correlation_id == request.correlation_id
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SidecarExecutionStatus {
    Running,
    Succeeded,
    Failed,
    Cancelled,
    TimedOut,
}

impl SidecarExecutionStatus {
    fn is_terminal(self) -> bool {
        !matches!(self, Self::Running)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubmitExecutionRequest {
    pub request_ref: String,
    pub task_id: String,
    pub run_id: String,
    pub step_id: Option<String>,
    pub correlation_id: String,
    pub workspace_path: String,
    pub description: String,
    pub executor_type: String,
    #[serde(default = "empty_object")]
    pub config: Value,
    pub timeout_seconds: Option<f64>,
    pub max_turns: Option<u32>,
    pub heartbeat_interval_seconds: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionSnapshot {
    pub protocol_version: String,
    pub request_ref: String,
    pub execution_id: String,
    pub task_id: String,
    pub run_id: String,
    pub step_id: Option<String>,
    pub correlation_id: String,
    pub status: SidecarExecutionStatus,
    pub result_code: Option<i32>,
    pub output: Value,
    pub stdout: String,
    pub stderr: String,
    pub artifacts: Vec<ArtifactSnapshot>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub retryable: bool,
    pub retry_after_seconds: Option<f64>,
    pub metadata: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArtifactSnapshot {
    pub relative_path: String,
    pub media_type: String,
    pub size_bytes: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutorAvailability {
    pub executor_type: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub healthy: bool,
    pub protocol_version: String,
    pub allowed_executor_types: Vec<String>,
    pub executors: Vec<ExecutorAvailability>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogPage {
    pub entries: Vec<LogEntry>,
    pub has_more: bool,
    pub next_sequence: Option<u64>,
}

#[derive(Debug, Deserialize)]
pub struct LogQuery {
    pub from_sequence: Option<u64>,
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize)]
struct ErrorBody {
    error: String,
}

#[derive(Debug)]
struct ApiError {
    status: StatusCode,
    message: String,
}

impl ApiError {
    fn bad_request(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::BAD_REQUEST,
            message: message.into(),
        }
    }

    fn conflict(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::CONFLICT,
            message: message.into(),
        }
    }

    fn not_found(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::NOT_FOUND,
            message: message.into(),
        }
    }

    fn internal(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            message: message.into(),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (
            self.status,
            Json(ErrorBody {
                error: self.message,
            }),
        )
            .into_response()
    }
}

pub fn build_router(state: SidecarState) -> Router {
    Router::new()
        .route("/healthz", get(health))
        .route("/v1/executions", post(submit_execution))
        .route("/v1/executions/{execution_id}", get(get_execution))
        .route(
            "/v1/executions/{execution_id}/cancel",
            post(cancel_execution),
        )
        .route("/v1/executions/{execution_id}/logs", get(get_logs))
        .route("/v1/requests/{request_ref}", get(get_by_request))
        .with_state(state)
}

async fn health(State(state): State<SidecarState>) -> Json<HealthResponse> {
    Json(HealthResponse {
        healthy: true,
        protocol_version: PROTOCOL_VERSION.to_owned(),
        allowed_executor_types: state.allowed_executor_types.iter().cloned().collect(),
        executors: state.availability.clone(),
    })
}

async fn submit_execution(
    State(state): State<SidecarState>,
    Json(request): Json<SubmitExecutionRequest>,
) -> Result<(StatusCode, Json<ExecutionSnapshot>), ApiError> {
    validate_request(&state, &request)?;
    let workspace = validate_workspace(&state.workspace_root, &request.workspace_path).await?;

    if let Some(existing) = lookup_by_request(&state, &request.request_ref).await {
        if !existing.matches_request(&request) {
            return Err(ApiError::conflict(
                "request_ref is already bound to different canonical execution identity",
            ));
        }
        return Ok((StatusCode::OK, Json(snapshot_with_logs(&existing).await?)));
    }

    let execution_id = format!("forge_exec_{}", Uuid::new_v4());
    let logs_path = state.logs_root.join(format!("{execution_id}.jsonl"));
    let record = JobRecord {
        request_ref: request.request_ref.clone(),
        execution_id: execution_id.clone(),
        task_id: request.task_id.clone(),
        run_id: request.run_id.clone(),
        step_id: request.step_id.clone(),
        correlation_id: request.correlation_id.clone(),
        status: SidecarExecutionStatus::Running,
        result_code: None,
        output: json!({}),
        error_code: None,
        error_message: None,
        retryable: false,
        retry_after_seconds: None,
        metadata: json!({"executor_type": request.executor_type}),
        logs_path: logs_path.clone(),
    };

    let persisted = {
        let mut jobs = state.jobs.write().await;
        if let Some(existing_id) = jobs.by_request.get(&request.request_ref).cloned() {
            let existing = jobs.by_execution.get(&existing_id).cloned();
            if let Some(existing) = existing {
                if !existing.matches_request(&request) {
                    return Err(ApiError::conflict(
                        "request_ref is already bound to different canonical execution identity",
                    ));
                }
                drop(jobs);
                return Ok((StatusCode::OK, Json(snapshot_with_logs(&existing).await?)));
            }
        }
        jobs.by_request
            .insert(request.request_ref.clone(), execution_id.clone());
        jobs.by_execution
            .insert(execution_id.clone(), record.clone());
        jobs.clone()
    };

    if let Err(error) = persist_job_store(&state.state_path, &persisted).await {
        let mut jobs = state.jobs.write().await;
        jobs.by_request.remove(&request.request_ref);
        jobs.by_execution.remove(&execution_id);
        return Err(ApiError::internal(format!(
            "failed to persist execution registration: {error}"
        )));
    }

    let ctx = ExecutionContext {
        task_id: request.task_id,
        execution_id: execution_id.clone(),
        worktree_path: workspace.to_string_lossy().into_owned(),
        description: request.description,
        agent_config: json!({
            "executor_type": request.executor_type,
            "config": request.config,
        }),
        logs_path: logs_path.to_string_lossy().into_owned(),
        heartbeat_interval_seconds: request
            .heartbeat_interval_seconds
            .unwrap_or(DEFAULT_HEARTBEAT_SECONDS)
            .max(1),
        max_turns: request.max_turns,
        log_sender: None,
    };

    spawn_execution(
        state.executor.clone(),
        state.jobs.clone(),
        state.state_path.clone(),
        execution_id,
        ctx,
        request.timeout_seconds,
    );

    Ok((
        StatusCode::ACCEPTED,
        Json(record.snapshot(String::new(), String::new(), false)),
    ))
}

async fn get_execution(
    State(state): State<SidecarState>,
    Path(execution_id): Path<String>,
) -> Result<Json<ExecutionSnapshot>, ApiError> {
    let record = lookup_execution(&state, &execution_id)
        .await
        .ok_or_else(|| ApiError::not_found(format!("execution not found: {execution_id}")))?;
    Ok(Json(snapshot_with_logs(&record).await?))
}

async fn get_by_request(
    State(state): State<SidecarState>,
    Path(request_ref): Path<String>,
) -> Result<Json<ExecutionSnapshot>, ApiError> {
    let record = lookup_by_request(&state, &request_ref)
        .await
        .ok_or_else(|| ApiError::not_found(format!("request not found: {request_ref}")))?;
    Ok(Json(snapshot_with_logs(&record).await?))
}

async fn cancel_execution(
    State(state): State<SidecarState>,
    Path(execution_id): Path<String>,
) -> Result<Json<ExecutionSnapshot>, ApiError> {
    let record = lookup_execution(&state, &execution_id)
        .await
        .ok_or_else(|| ApiError::not_found(format!("execution not found: {execution_id}")))?;
    if record.status.is_terminal() {
        return Ok(Json(snapshot_with_logs(&record).await?));
    }

    state
        .executor
        .cancel(&execution_id)
        .await
        .map_err(|error| ApiError::internal(format!("executor cancellation failed: {error}")))?;

    let (updated, persisted) = {
        let mut jobs = state.jobs.write().await;
        let record = jobs
            .by_execution
            .get_mut(&execution_id)
            .ok_or_else(|| ApiError::not_found(format!("execution not found: {execution_id}")))?;
        if !record.status.is_terminal() {
            record.status = SidecarExecutionStatus::Cancelled;
            record.result_code = None;
            record.error_code = Some("cancelled".to_owned());
            record.error_message = Some("execution cancellation requested".to_owned());
            record.retryable = false;
        }
        let updated = record.clone();
        (updated, jobs.clone())
    };
    persist_job_store(&state.state_path, &persisted)
        .await
        .map_err(|error| ApiError::internal(format!("failed to persist cancellation: {error}")))?;
    Ok(Json(snapshot_with_logs(&updated).await?))
}

async fn get_logs(
    State(state): State<SidecarState>,
    Path(execution_id): Path<String>,
    Query(query): Query<LogQuery>,
) -> Result<Json<LogPage>, ApiError> {
    let record = lookup_execution(&state, &execution_id)
        .await
        .ok_or_else(|| ApiError::not_found(format!("execution not found: {execution_id}")))?;
    let limit = query
        .limit
        .unwrap_or(DEFAULT_LOG_PAGE_LIMIT)
        .clamp(1, MAX_LOG_PAGE_LIMIT);
    match LogReader::read(
        &record.logs_path,
        query.from_sequence.unwrap_or(0),
        limit,
    )
    .await
    {
        Ok(result) => Ok(Json(LogPage {
            entries: result.entries,
            has_more: result.has_more,
            next_sequence: result.next_sequence,
        })),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(Json(LogPage {
            entries: Vec::new(),
            has_more: false,
            next_sequence: Some(query.from_sequence.unwrap_or(0)),
        })),
        Err(error) => Err(ApiError::internal(format!("log read failed: {error}"))),
    }
}

fn spawn_execution(
    executor: Arc<dyn TaskExecutor>,
    jobs: Arc<RwLock<JobStore>>,
    state_path: PathBuf,
    execution_id: String,
    ctx: ExecutionContext,
    timeout_seconds: Option<f64>,
) {
    tokio::spawn(async move {
        let result = if let Some(seconds) = timeout_seconds {
            match tokio::time::timeout(Duration::from_secs_f64(seconds), executor.execute(ctx)).await {
                Ok(result) => result.map(ExecutionCompletion::Result),
                Err(_) => {
                    let _ = executor.cancel(&execution_id).await;
                    Ok(ExecutionCompletion::TimedOut)
                }
            }
        } else {
            executor.execute(ctx).await.map(ExecutionCompletion::Result)
        };

        let persisted = {
            let mut jobs = jobs.write().await;
            let Some(record) = jobs.by_execution.get_mut(&execution_id) else {
                return;
            };
            if record.status.is_terminal() {
                return;
            }
            match result {
                Ok(ExecutionCompletion::Result(result)) => apply_result(record, &result),
                Ok(ExecutionCompletion::TimedOut) => {
                    record.status = SidecarExecutionStatus::TimedOut;
                    record.error_code = Some("timeout".to_owned());
                    record.error_message = Some("execution timed out".to_owned());
                    record.retryable = false;
                }
                Err(error) => apply_error(record, &error),
            }
            jobs.clone()
        };
        let _ = persist_job_store(&state_path, &persisted).await;
    });
}

enum ExecutionCompletion {
    Result(ExecutionResult),
    TimedOut,
}

fn apply_result(record: &mut JobRecord, result: &ExecutionResult) {
    record.status = match result.status {
        ExecutionOutcome::Completed => SidecarExecutionStatus::Succeeded,
        ExecutionOutcome::Failed => SidecarExecutionStatus::Failed,
        ExecutionOutcome::Cancelled => SidecarExecutionStatus::Cancelled,
    };
    record.result_code = match record.status {
        SidecarExecutionStatus::Succeeded => Some(0),
        SidecarExecutionStatus::Failed => Some(1),
        SidecarExecutionStatus::Cancelled
        | SidecarExecutionStatus::TimedOut
        | SidecarExecutionStatus::Running => None,
    };
    record.output = json!({
        "summary": result.summary,
        "assistant_output": result.assistant_output,
        "after_sha": result.after_sha,
        "usage": result.usage.as_ref().map(|usage| json!({
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_write_tokens": usage.cache_write_tokens,
            "cost_usd": usage.cost_usd,
            "model": usage.model,
        })),
    });
    record.error_message = result.error.clone();
    record.retry_after_seconds = result.retry_after.map(|duration| duration.as_secs_f64());
    record.retryable = matches!(
        result.failure_class,
        Some(ExecutionFailureClass::ExecutorUnavailable)
    );
    record.error_code = match result.status {
        ExecutionOutcome::Completed => None,
        ExecutionOutcome::Cancelled => Some("cancelled".to_owned()),
        ExecutionOutcome::Failed => Some(
            match result.failure_class {
                Some(ExecutionFailureClass::ExecutorUnavailable) => "unavailable",
                _ => "execution_failed",
            }
            .to_owned(),
        ),
    };

    let resolved = result.resolved_candidate.as_ref().map(|candidate| {
        json!({
            "candidate_key": candidate.candidate_key,
            "executor_type": candidate.executor_type.to_string(),
        })
    });
    record.metadata = json!({
        "resolved_candidate": resolved,
        "route_attempt_count": result.route_attempts.len(),
    });
}

fn apply_error(record: &mut JobRecord, error: &ExecutorError) {
    record.status = SidecarExecutionStatus::Failed;
    record.result_code = Some(1);
    record.error_message = Some(error.to_string());
    match error {
        ExecutorError::UsageExhausted { retry_after, .. } => {
            record.error_code = Some("usage_exhausted".to_owned());
            record.retryable = true;
            record.retry_after_seconds = retry_after.map(|duration| duration.as_secs_f64());
        }
        ExecutorError::Unavailable(_) => {
            record.error_code = Some("unavailable".to_owned());
            record.retryable = true;
        }
        ExecutorError::Io(_) | ExecutorError::Other(_) => {
            record.error_code = Some("internal".to_owned());
            record.retryable = false;
        }
    }
}

fn validate_request(state: &SidecarState, request: &SubmitExecutionRequest) -> Result<(), ApiError> {
    for (name, value) in [
        ("request_ref", request.request_ref.as_str()),
        ("task_id", request.task_id.as_str()),
        ("run_id", request.run_id.as_str()),
        ("correlation_id", request.correlation_id.as_str()),
        ("workspace_path", request.workspace_path.as_str()),
        ("description", request.description.as_str()),
        ("executor_type", request.executor_type.as_str()),
    ] {
        if value.trim().is_empty() {
            return Err(ApiError::bad_request(format!("{name} must not be blank")));
        }
    }
    if !request.config.is_object() {
        return Err(ApiError::bad_request("config must be a JSON object"));
    }
    if request.timeout_seconds.is_some_and(|seconds| seconds <= 0.0) {
        return Err(ApiError::bad_request(
            "timeout_seconds must be greater than zero",
        ));
    }
    if !state.allowed_executor_types.contains(&request.executor_type) {
        return Err(ApiError::bad_request(format!(
            "executor type is not allowed: {}",
            request.executor_type
        )));
    }
    Ok(())
}

async fn validate_workspace(root: &FsPath, requested: &str) -> Result<PathBuf, ApiError> {
    let path = tokio::fs::canonicalize(requested)
        .await
        .map_err(|_| ApiError::bad_request("workspace is missing or unavailable"))?;
    let metadata = tokio::fs::metadata(&path)
        .await
        .map_err(|_| ApiError::bad_request("workspace is missing or unavailable"))?;
    if !metadata.is_dir() {
        return Err(ApiError::bad_request("workspace must be a directory"));
    }
    if path != root && !path.starts_with(root) {
        return Err(ApiError::bad_request(
            "workspace escapes configured workspace root",
        ));
    }
    Ok(path)
}

async fn lookup_execution(state: &SidecarState, execution_id: &str) -> Option<JobRecord> {
    state.jobs.read().await.by_execution.get(execution_id).cloned()
}

async fn lookup_by_request(state: &SidecarState, request_ref: &str) -> Option<JobRecord> {
    let jobs = state.jobs.read().await;
    let execution_id = jobs.by_request.get(request_ref)?;
    jobs.by_execution.get(execution_id).cloned()
}

async fn snapshot_with_logs(record: &JobRecord) -> Result<ExecutionSnapshot, ApiError> {
    match collect_streams(&record.logs_path).await {
        Ok((stdout, stderr, has_more)) => Ok(record.snapshot(stdout, stderr, has_more)),
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            Ok(record.snapshot(String::new(), String::new(), false))
        }
        Err(error) => Err(ApiError::internal(format!("log read failed: {error}"))),
    }
}

async fn collect_streams(path: &FsPath) -> io::Result<(String, String, bool)> {
    let result = LogReader::read(path, 0, SNAPSHOT_LOG_LIMIT).await?;
    let mut stdout = Vec::new();
    let mut stderr = Vec::new();
    for entry in result.entries {
        let Some(line) = entry.payload.get("line").and_then(Value::as_str) else {
            continue;
        };
        match entry.kind {
            LogKind::Stdout => stdout.push(line.to_owned()),
            LogKind::Stderr => stderr.push(line.to_owned()),
            _ => {}
        }
    }
    Ok((stdout.join("\n"), stderr.join("\n"), result.has_more))
}

async fn load_job_store(path: &FsPath) -> io::Result<JobStore> {
    match tokio::fs::read(path).await {
        Ok(bytes) => serde_json::from_slice(&bytes).map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                format!("invalid executor sidecar state: {error}"),
            )
        }),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(JobStore::default()),
        Err(error) => Err(error),
    }
}

async fn persist_job_store(path: &FsPath, jobs: &JobStore) -> io::Result<()> {
    let bytes = serde_json::to_vec_pretty(jobs).map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!("failed to serialize executor sidecar state: {error}"),
        )
    })?;
    let tmp = path.with_extension(format!("tmp-{}", Uuid::new_v4()));
    tokio::fs::write(&tmp, bytes).await?;
    match tokio::fs::rename(&tmp, path).await {
        Ok(()) => Ok(()),
        Err(first_error) => {
            if tokio::fs::try_exists(path).await.unwrap_or(false) {
                tokio::fs::remove_file(path).await?;
                tokio::fs::rename(&tmp, path).await
            } else {
                let _ = tokio::fs::remove_file(&tmp).await;
                Err(first_error)
            }
        }
    }
}

fn merge_metadata(metadata: &mut Value, key: &str, value: Value) {
    if !metadata.is_object() {
        *metadata = json!({});
    }
    if let Some(object) = metadata.as_object_mut() {
        object.insert(key.to_owned(), value);
    }
}

fn availability_name(status: &AvailabilityStatus) -> &'static str {
    match status {
        AvailabilityStatus::Authenticated => "authenticated",
        AvailabilityStatus::Installed => "installed",
        AvailabilityStatus::NotFound => "not_found",
    }
}

fn empty_object() -> Value {
    json!({})
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{
        body::{to_bytes, Body},
        http::Request,
    };
    use tower::ServiceExt;

    async fn test_state() -> (tempfile::TempDir, SidecarState, PathBuf) {
        let dir = tempfile::tempdir().expect("tempdir");
        let workspace = dir.path().join("workspaces").join("task-1");
        tokio::fs::create_dir_all(&workspace)
            .await
            .expect("workspace");
        let state = SidecarState::new(SidecarConfig::new(
            dir.path().join("workspaces"),
            dir.path().join("logs"),
            ["null".to_owned()],
        ))
        .await
        .expect("state");
        (dir, state, workspace)
    }

    fn submit_body(workspace: &FsPath, delay_seconds: u64) -> Value {
        json!({
            "request_ref": "run-1",
            "task_id": "task-1",
            "run_id": "run-1",
            "step_id": null,
            "correlation_id": "task-1",
            "workspace_path": workspace,
            "description": "deterministic sidecar smoke test",
            "executor_type": "null",
            "config": {"delay_seconds": delay_seconds},
            "timeout_seconds": 5.0,
            "max_turns": null,
            "heartbeat_interval_seconds": 1
        })
    }

    async fn response_json(response: Response) -> Value {
        let bytes = to_bytes(response.into_body(), 1024 * 1024)
            .await
            .expect("response body");
        serde_json::from_slice(&bytes).expect("json response")
    }

    #[tokio::test]
    async fn submit_is_idempotent_and_null_execution_completes() {
        let (_dir, state, workspace) = test_state().await;
        let app = build_router(state);
        let body = submit_body(&workspace, 0);

        let first = app
            .clone()
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(first.status(), StatusCode::ACCEPTED);
        let first_json = response_json(first).await;
        let execution_id = first_json["execution_id"]
            .as_str()
            .expect("execution id")
            .to_owned();

        let second = app
            .clone()
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let second_json = response_json(second).await;
        assert_eq!(second_json["execution_id"], execution_id);

        tokio::time::sleep(Duration::from_millis(25)).await;
        let get = app
            .oneshot(
                Request::get(format!("/v1/executions/{execution_id}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        let get_json = response_json(get).await;
        assert_eq!(get_json["status"], "succeeded");
        assert_eq!(
            get_json["output"]["summary"],
            "Null executor completed successfully."
        );
    }

    #[tokio::test]
    async fn terminal_job_idempotency_survives_sidecar_restart() {
        let (dir, state, workspace) = test_state().await;
        let app = build_router(state);
        let body = submit_body(&workspace, 0);
        let first = app
            .clone()
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let first_json = response_json(first).await;
        let execution_id = first_json["execution_id"].as_str().unwrap().to_owned();
        tokio::time::sleep(Duration::from_millis(25)).await;

        let restarted = SidecarState::new(SidecarConfig::new(
            dir.path().join("workspaces"),
            dir.path().join("logs"),
            ["null".to_owned()],
        ))
        .await
        .expect("restart state");
        let response = build_router(restarted)
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
        let json = response_json(response).await;
        assert_eq!(json["execution_id"], execution_id);
        assert_eq!(json["status"], "succeeded");
    }

    #[tokio::test]
    async fn persisted_running_job_is_marked_interrupted_on_restart() {
        let dir = tempfile::tempdir().unwrap();
        let workspace_root = dir.path().join("workspaces");
        let workspace = workspace_root.join("task-1");
        let logs_root = dir.path().join("logs");
        tokio::fs::create_dir_all(&workspace).await.unwrap();
        tokio::fs::create_dir_all(&logs_root).await.unwrap();
        let state_path = logs_root.join(STATE_FILE_NAME);
        let record = JobRecord {
            request_ref: "run-1".to_owned(),
            execution_id: "forge_exec_stale".to_owned(),
            task_id: "task-1".to_owned(),
            run_id: "run-1".to_owned(),
            step_id: None,
            correlation_id: "task-1".to_owned(),
            status: SidecarExecutionStatus::Running,
            result_code: None,
            output: json!({}),
            error_code: None,
            error_message: None,
            retryable: false,
            retry_after_seconds: None,
            metadata: json!({"executor_type": "null"}),
            logs_path: logs_root.join("forge_exec_stale.jsonl"),
        };
        let mut store = JobStore::default();
        store
            .by_request
            .insert("run-1".to_owned(), "forge_exec_stale".to_owned());
        store
            .by_execution
            .insert("forge_exec_stale".to_owned(), record);
        persist_job_store(&state_path, &store).await.unwrap();

        let restarted = SidecarState::new(SidecarConfig::new(
            workspace_root,
            logs_root,
            ["null".to_owned()],
        ))
        .await
        .unwrap();
        let recovered = lookup_by_request(&restarted, "run-1").await.unwrap();
        assert_eq!(recovered.status, SidecarExecutionStatus::Failed);
        assert_eq!(recovered.error_code.as_deref(), Some("interrupted"));
        assert_eq!(recovered.metadata["recovery_required"], true);
    }

    #[tokio::test]
    async fn reused_request_ref_with_different_identity_is_rejected() {
        let (_dir, state, workspace) = test_state().await;
        let app = build_router(state);
        let body = submit_body(&workspace, 0);
        let _ = app
            .clone()
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let mut conflict = body;
        conflict["task_id"] = Value::String("task-2".to_owned());
        let response = app
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(conflict.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::CONFLICT);
    }

    #[tokio::test]
    async fn executor_allowlist_rejects_shell_by_default() {
        let (_dir, state, workspace) = test_state().await;
        let app = build_router(state);
        let mut body = submit_body(&workspace, 0);
        body["executor_type"] = Value::String("shell".to_owned());
        body["config"] = json!({"command": "echo", "args": ["unsafe"]});

        let response = app
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn workspace_escape_is_rejected() {
        let (dir, state, _workspace) = test_state().await;
        let outside = dir.path().join("outside");
        tokio::fs::create_dir_all(&outside).await.unwrap();
        let app = build_router(state);
        let body = submit_body(&outside, 0);

        let response = app
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn cancellation_remains_terminal_after_executor_finishes() {
        let (_dir, state, workspace) = test_state().await;
        let app = build_router(state);
        let body = submit_body(&workspace, 1);

        let submit = app
            .clone()
            .oneshot(
                Request::post("/v1/executions")
                    .header("content-type", "application/json")
                    .body(Body::from(body.to_string()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let submit_json = response_json(submit).await;
        let execution_id = submit_json["execution_id"].as_str().unwrap().to_owned();

        let cancel = app
            .clone()
            .oneshot(
                Request::post(format!("/v1/executions/{execution_id}/cancel"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        let cancel_json = response_json(cancel).await;
        assert_eq!(cancel_json["status"], "cancelled");

        tokio::time::sleep(Duration::from_millis(1_050)).await;
        let get = app
            .oneshot(
                Request::get(format!("/v1/executions/{execution_id}"))
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();
        let get_json = response_json(get).await;
        assert_eq!(get_json["status"], "cancelled");
    }
}
