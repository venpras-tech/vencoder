#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use base64::Engine;
use std::io::Write;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

const BACKEND_PORT: u16 = 8765;
const BACKEND_HOST: &str = "127.0.0.1";

struct AppState {
    project_path: Mutex<PathBuf>,
    backend_child: Mutex<Option<std::process::Child>>,
    backend_error: Mutex<Option<String>>,
}

#[tauri::command]
fn get_backend_url() -> String {
    format!("http://{}:{}", BACKEND_HOST, BACKEND_PORT)
}

#[tauri::command]
fn get_backend_error(state: tauri::State<AppState>) -> Option<String> {
    state.backend_error.lock().unwrap().clone()
}

#[derive(serde::Serialize)]
struct TreeItem {
    name: String,
    path: String,
    #[serde(rename = "type")]
    item_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    children: Option<Vec<TreeItem>>,
}

fn tree_ignore(rel: &str) -> bool {
    let s = rel.replace('\\', "/");
    let parts: Vec<&str> = s.split('/').collect();
    for p in parts {
        let lower = p.to_lowercase();
        if matches!(
            lower.as_str(),
            ".git" | "node_modules" | "__pycache__" | ".venv" | "venv" | ".env"
                | "dist" | "build" | "chroma_data" | ".codec-agent"
        ) {
            return true;
        }
    }
    false
}

fn build_file_tree(root: &std::path::Path, rel_prefix: &str) -> Vec<TreeItem> {
    let mut items = Vec::new();
    let Ok(entries) = std::fs::read_dir(root) else {
        return items;
    };
    let mut entries: Vec<_> = entries.filter_map(|e| e.ok()).collect();
    entries.sort_by(|a, b| {
        let a_file = a.path().is_file();
        let b_file = b.path().is_file();
        match (a_file, b_file) {
            (true, false) => std::cmp::Ordering::Greater,
            (false, true) => std::cmp::Ordering::Less,
            _ => a.file_name().to_string_lossy().to_lowercase().cmp(&b.file_name().to_string_lossy().to_lowercase()),
        }
    });
    for e in entries {
        let name = e.file_name().to_string_lossy().to_string();
        let rel = if rel_prefix.is_empty() {
            name.clone()
        } else {
            format!("{}/{}", rel_prefix, name)
        };
        if tree_ignore(&rel) {
            continue;
        }
        let path = e.path();
        if path.is_dir() {
            let children = build_file_tree(&path, &rel);
            items.push(TreeItem {
                name,
                path: rel,
                item_type: "folder".to_string(),
                children: Some(children),
            });
        } else if path.is_file() {
            items.push(TreeItem {
                name,
                path: rel,
                item_type: "file".to_string(),
                children: None,
            });
        }
    }
    items
}

#[tauri::command]
fn get_file_tree(state: tauri::State<AppState>) -> serde_json::Value {
    let root = state.project_path.lock().unwrap().clone();
    if !root.exists() || !root.is_dir() {
        return serde_json::json!({ "tree": [] });
    }
    serde_json::json!({ "tree": build_file_tree(&root, "") })
}

const EXT_TO_LANGUAGE: &[(&str, &str)] = &[
    (".py", "python"), (".js", "javascript"), (".ts", "typescript"), (".jsx", "javascript"),
    (".tsx", "typescript"), (".json", "json"), (".md", "markdown"), (".html", "html"),
    (".css", "css"), (".scss", "scss"), (".yaml", "yaml"), (".yml", "yaml"),
    (".sh", "shell"), (".bash", "shell"), (".sql", "sql"), (".xml", "xml"),
    (".go", "go"), (".rs", "rust"), (".java", "java"), (".kt", "kotlin"),
    (".cs", "csharp"), (".cpp", "cpp"), (".c", "c"), (".h", "c"),
];

#[tauri::command]
fn get_file_content(rel_path: String, state: tauri::State<AppState>) -> Option<serde_json::Value> {
    if rel_path.is_empty() {
        return None;
    }
    let root = state.project_path.lock().unwrap().canonicalize().ok()?;
    let full = root.join(rel_path.replace('/', std::path::MAIN_SEPARATOR_STR));
    let full = full.canonicalize().ok()?;
    if !full.starts_with(&root) {
        return None;
    }
    let meta = std::fs::metadata(&full).ok()?;
    if !meta.is_file() || meta.len() > 1024 * 1024 {
        return None;
    }
    let content = std::fs::read_to_string(&full).ok()?;
    let ext = full.extension().and_then(|e| e.to_str()).unwrap_or("");
    let ext = format!(".{}", ext.to_lowercase());
    let language = EXT_TO_LANGUAGE
        .iter()
        .find(|(e, _)| *e == ext)
        .map(|(_, l)| *l)
        .unwrap_or("plaintext");
    Some(serde_json::json!({ "content": content, "language": language }))
}

#[tauri::command]
fn get_project_path(state: tauri::State<AppState>) -> String {
    state.project_path.lock().unwrap().to_string_lossy().to_string()
}

#[tauri::command]
fn set_project_path(path: String, state: tauri::State<AppState>, app: tauri::AppHandle) {
    let new_path = PathBuf::from(&path);
    {
        let mut p = state.project_path.lock().unwrap();
        if *p != new_path {
            *p = new_path.clone();
            let escaped = path.replace('\\', "\\\\").replace('\'', "\\'");
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.eval(&format!("window.dispatchEvent(new CustomEvent('project-path', {{ detail: '{}' }}))", escaped));
            }
        }
    }
    stop_backend(state.clone());
    start_backend(app, state, PathBuf::from(path));
}

#[tauri::command]
fn get_log_path(app: tauri::AppHandle) -> String {
    let data_dir = app.path().app_data_dir().unwrap_or_else(|_| PathBuf::from("."));
    let _ = std::fs::create_dir_all(&data_dir);
    data_dir.join("app.log").to_string_lossy().to_string()
}

#[tauri::command]
fn get_log_dir(app: tauri::AppHandle) -> Option<String> {
    let cfg = std::fs::read_to_string(app.path().app_data_dir().ok()?.join("app-settings.json")).ok()?;
    let v: serde_json::Value = serde_json::from_str(&cfg).ok()?;
    v.get("logPath")?.as_str().map(String::from)
}

#[tauri::command]
fn set_log_dir(dir: Option<String>, app: tauri::AppHandle) -> bool {
    let path = match app.path().app_data_dir() {
        Ok(p) => p,
        Err(_) => return false,
    };
    let cfg_path = path.join("app-settings.json");
    let mut current: serde_json::Value = std::fs::read_to_string(&cfg_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    current["logPath"] = serde_json::Value::String(dir.unwrap_or_default());
    let _ = std::fs::write(cfg_path, serde_json::to_string_pretty(&current).unwrap_or_default());
    true
}

#[tauri::command]
fn get_theme(app: tauri::AppHandle) -> String {
    let path = app.path().app_data_dir().ok();
    let cfg = path.and_then(|p| std::fs::read_to_string(p.join("app-settings.json")).ok());
    let v: Option<serde_json::Value> = cfg.and_then(|s| serde_json::from_str(&s).ok());
    v.as_ref()
        .and_then(|v| v.get("theme").and_then(|t| t.as_str()).map(String::from))
        .unwrap_or_else(|| "system".to_string())
}

#[tauri::command]
fn set_theme(theme: String, app: tauri::AppHandle) -> bool {
    if !["light", "dark", "system"].contains(&theme.as_str()) {
        return false;
    }
    let path = match app.path().app_data_dir() {
        Ok(p) => p,
        Err(_) => return false,
    };
    let cfg_path = path.join("app-settings.json");
    let mut current: serde_json::Value = std::fs::read_to_string(&cfg_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    current["theme"] = serde_json::Value::String(theme);
    let _ = std::fs::write(cfg_path, serde_json::to_string_pretty(&current).unwrap_or_default());
    true
}

#[tauri::command]
fn read_logs(log_type: String, state: tauri::State<AppState>, app: tauri::AppHandle) -> String {
    let path = if log_type == "backend" || log_type == "agent" {
        state.project_path.lock().unwrap().join("logs").join("server.log")
    } else {
        PathBuf::from(get_log_path(app))
    };
    match std::fs::read_to_string(&path) {
        Ok(s) => {
            const MAX: usize = 2 * 1024 * 1024;
            if s.len() > MAX {
                format!("... (showing last 2MB)\n\n{}", &s[s.len() - MAX..])
            } else {
                s
            }
        }
        Err(_) => String::new(),
    }
}

#[tauri::command]
async fn open_folder(app: tauri::AppHandle) -> Option<String> {
    let path = app.dialog().file().blocking_pick_folder();
    path.and_then(|p| p.into_path().ok()).map(|p| p.to_string_lossy().to_string())
}

#[tauri::command]
async fn open_path(path: String) -> Result<(), String> {
    if path.is_empty() {
        return Err("path is empty".into());
    }
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(&path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn open_file(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = app.dialog().file().blocking_pick_file();
    Ok(path.and_then(|p| p.into_path().ok()).map(|p| p.to_string_lossy().to_string()))
}

#[tauri::command]
async fn open_image(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let path = app.dialog().file().blocking_pick_file();
    Ok(path
        .and_then(|p| p.into_path().ok())
        .and_then(|p| std::fs::read(&p).ok())
        .map(|b| base64::engine::general_purpose::STANDARD.encode(&b)))
}

#[tauri::command]
async fn save_file(app: tauri::AppHandle, _default_name: String, content: String) -> Option<String> {
    let path = app.dialog().file().blocking_save_file();
    path.and_then(|p| p.into_path().ok())
        .and_then(|p| std::fs::write(&p, content).ok().map(|_| p.to_string_lossy().to_string()))
}

#[tauri::command]
fn get_llm_provider(app: tauri::AppHandle) -> String {
    let path = app.path().app_data_dir().ok();
    let cfg = path.and_then(|p| std::fs::read_to_string(p.join("app-settings.json")).ok());
    let v: Option<serde_json::Value> = cfg.and_then(|s| serde_json::from_str(&s).ok());
    v.as_ref()
        .and_then(|v| v.get("llmProvider").and_then(|p| p.as_str()).map(String::from))
        .unwrap_or_else(|| "Built-in".to_string())
}

#[tauri::command]
fn set_llm_provider(provider: String, app: tauri::AppHandle) -> bool {
    let valid = ["Ollama", "LM Studio", "Built-in", "OpenAI", "Anthropic", "Google"];
    if !valid.contains(&provider.as_str()) {
        return false;
    }
    let path = match app.path().app_data_dir() {
        Ok(p) => p,
        Err(_) => return false,
    };
    let cfg_path = path.join("app-settings.json");
    let mut current: serde_json::Value = std::fs::read_to_string(&cfg_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    current["llmProvider"] = serde_json::Value::String(provider);
    let _ = std::fs::write(cfg_path, serde_json::to_string_pretty(&current).unwrap_or_default());
    true
}

#[tauri::command]
fn set_llm_config(cfg: serde_json::Value, app: tauri::AppHandle) -> bool {
    let path = match app.path().app_data_dir() {
        Ok(p) => p,
        Err(_) => return false,
    };
    let cfg_path = path.join("app-settings.json");
    let mut current: serde_json::Value = std::fs::read_to_string(&cfg_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    if let Some(p) = cfg.get("provider").and_then(|v| v.as_str()) {
        current["llmProvider"] = serde_json::Value::String(p.to_string());
    }
    if let Some(m) = cfg.get("model").and_then(|v| v.as_str()) {
        current["llmModel"] = serde_json::Value::String(m.to_string());
    }
    if let Some(b) = cfg.get("baseUrl").and_then(|v| v.as_str()) {
        current["llmBaseUrl"] = serde_json::Value::String(b.to_string());
    }
    if let Some(k) = cfg.get("apiKey").and_then(|v| v.as_str()) {
        current["llmApiKey"] = serde_json::Value::String(k.to_string());
    }
    if cfg.get("numCtx").is_some() {
        current["numCtx"] = cfg["numCtx"].clone();
    }
    if cfg.get("temperature").is_some() {
        current["temperature"] = cfg["temperature"].clone();
    }
    if cfg.get("repeatPenalty").is_some() {
        current["repeatPenalty"] = cfg["repeatPenalty"].clone();
    }
    if cfg.get("numPredict").is_some() {
        current["numPredict"] = cfg["numPredict"].clone();
    }
    let _ = std::fs::write(cfg_path, serde_json::to_string_pretty(&current).unwrap_or_default());
    true
}

#[tauri::command]
fn get_llm_config(app: tauri::AppHandle) -> serde_json::Value {
    let path = app.path().app_data_dir().ok();
    let cfg = path.and_then(|p| std::fs::read_to_string(p.join("app-settings.json")).ok());
    let v: Option<serde_json::Value> = cfg.and_then(|s| serde_json::from_str(&s).ok());
    let provider = v.as_ref()
        .and_then(|v| v.get("llmProvider").and_then(|p| p.as_str()).map(String::from))
        .unwrap_or_else(|| "Built-in".to_string());
    let model = v.as_ref()
        .and_then(|v| v.get("llmModel").and_then(|m| m.as_str()).map(String::from))
        .unwrap_or_default();
    let base_url = v.as_ref()
        .and_then(|v| v.get("llmBaseUrl").and_then(|b| b.as_str()).map(String::from))
        .unwrap_or_default();
    let api_key = v.as_ref()
        .and_then(|v| v.get("llmApiKey").and_then(|k| k.as_str()))
        .filter(|k| !k.is_empty())
        .map(|_| "***")
        .unwrap_or_default();
    let to_str = |v: &serde_json::Value| -> String {
        if v.is_null() { return String::new(); }
        if let Some(n) = v.as_i64() { return n.to_string(); }
        if let Some(n) = v.as_f64() { return n.to_string(); }
        v.as_str().unwrap_or("").to_string()
    };
    let num_ctx = v.as_ref()
        .and_then(|c| c.get("numCtx"))
        .map(to_str)
        .unwrap_or_default();
    let temperature = v.as_ref()
        .and_then(|c| c.get("temperature"))
        .map(to_str)
        .unwrap_or_default();
    let repeat_penalty = v.as_ref()
        .and_then(|c| c.get("repeatPenalty"))
        .map(to_str)
        .unwrap_or_default();
    let num_predict = v.as_ref()
        .and_then(|c| c.get("numPredict"))
        .map(to_str)
        .unwrap_or_default();
    serde_json::json!({
        "provider": provider,
        "model": model,
        "baseUrl": base_url,
        "apiKey": api_key,
        "numCtx": num_ctx,
        "temperature": temperature,
        "repeatPenalty": repeat_penalty,
        "numPredict": num_predict
    })
}

#[tauri::command]
fn retry_backend(state: tauri::State<AppState>, app: tauri::AppHandle) {
    let path = state.project_path.lock().unwrap().clone();
    stop_backend(state.clone());
    start_backend(app, state, path);
}

#[tauri::command]
fn restart_backend(state: tauri::State<AppState>, app: tauri::AppHandle) {
    let path = state.project_path.lock().unwrap().clone();
    stop_backend(state.clone());
    start_backend(app, state, path);
}

fn get_backend_dir(app: &tauri::AppHandle) -> PathBuf {
    if let Ok(resource) = app.path().resource_dir() {
        let backend = resource.join("backend");
        if backend.exists() {
            return backend;
        }
        let backend_up = resource.join("_up_").join("backend");
        if backend_up.exists() {
            return backend_up;
        }
    }
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let backend = cwd.join("backend");
    if backend.exists() {
        return backend;
    }
    let dev_backend = cwd.parent().map(|p| p.join("backend")).unwrap_or_default();
    if dev_backend.exists() {
        return dev_backend;
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(PathBuf::from).unwrap_or_default();
        while dir.pop() {
            let backend = dir.join("backend");
            if backend.exists() {
                return backend;
            }
            let backend_up = dir.join("_up_").join("backend");
            if backend_up.exists() {
                return backend_up;
            }
            let dev_backend = dir.join("..").join("backend").canonicalize().unwrap_or_default();
            if dev_backend.exists() {
                return dev_backend;
            }
        }
    }
    let default = PathBuf::from(".");
    let exe = std::env::current_exe().ok();
    let base = exe.as_ref().and_then(|e| e.parent()).unwrap_or(&default);
    let backend_up = base.join("_up_").join("backend");
    if backend_up.exists() {
        return backend_up;
    }
    base.join("backend")
}

fn get_bundled_python(app: &tauri::AppHandle) -> Option<PathBuf> {
    let resource = app.path().resource_dir().ok()?;
    let py = resource.join("python").join(if std::env::consts::OS == "windows" { "python.exe" } else { "python3" });
    if py.exists() {
        return Some(py);
    }
    let py_up = resource.join("_up_").join("python-runtime").join(if std::env::consts::OS == "windows" { "python.exe" } else { "python3" });
    if py_up.exists() {
        return Some(py_up);
    }
    None
}

fn start_backend(app: tauri::AppHandle, state: tauri::State<AppState>, workspace: PathBuf) {
    let backend_dir = get_backend_dir(&app);
    if !backend_dir.exists() {
        let err = format!("Backend dir not found: {:?}", backend_dir);
        eprintln!("{}", err);
        *state.backend_error.lock().unwrap() = Some(err);
        return;
    }
    *state.backend_error.lock().unwrap() = None;
    let python = get_bundled_python(&app).unwrap_or_else(|| {
        if std::env::consts::OS == "windows" {
            PathBuf::from("python")
        } else {
            PathBuf::from("python3")
        }
    });
    let mut envs: Vec<(String, String)> = vec![
        ("PYTHONPATH".into(), backend_dir.to_string_lossy().to_string()),
        ("WORKSPACE_ROOT".into(), workspace.to_string_lossy().to_string()),
    ];
    if let Ok(data_dir) = app.path().app_data_dir() {
        let models_dir = data_dir.parent().map(|p| p.join("ai-codec").join("models")).unwrap_or_else(|| data_dir.join("models"));
        let _ = std::fs::create_dir_all(&models_dir);
        envs.push(("BUILTIN_MODELS_DIR".into(), models_dir.to_string_lossy().to_string()));
        if let Ok(cfg) = std::fs::read_to_string(data_dir.join("app-settings.json")) {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&cfg) {
                let provider = v.get("llmProvider").and_then(|p| p.as_str()).unwrap_or("Built-in");
                let provider_env = match provider {
                    "Built-in" => "builtin",
                    "LM Studio" => "lmstudio",
                    "OpenAI" => "openai",
                    "Anthropic" => "anthropic",
                    "Google" => "google",
                    _ => "ollama",
                };
                envs.push(("LLM_PROVIDER".into(), provider_env.to_string()));
                if let Some(m) = v.get("llmModel").and_then(|m| m.as_str()).filter(|s| !s.is_empty()) {
                    envs.push(("LLM_MODEL".into(), m.to_string()));
                }
                if provider == "Ollama" {
                    if let Some(b) = v.get("llmBaseUrl").and_then(|b| b.as_str()).filter(|s| !s.is_empty()) {
                        envs.push(("OLLAMA_BASE_URL".into(), b.to_string()));
                    }
                } else if provider == "LM Studio" {
                    if let Some(b) = v.get("llmBaseUrl").and_then(|b| b.as_str()).filter(|s| !s.is_empty()) {
                        envs.push(("LM_STUDIO_BASE_URL".into(), b.to_string()));
                    }
                } else if provider == "OpenAI" {
                    if let Some(b) = v.get("llmBaseUrl").and_then(|b| b.as_str()).filter(|s| !s.is_empty()) {
                        envs.push(("OPENAI_BASE_URL".into(), b.to_string()));
                    }
                    if let Some(k) = v.get("llmApiKey").and_then(|k| k.as_str()).filter(|s| !s.is_empty() && *s != "***") {
                        envs.push(("OPENAI_API_KEY".into(), k.to_string()));
                    }
                } else if provider == "Anthropic" {
                    if let Some(b) = v.get("llmBaseUrl").and_then(|b| b.as_str()).filter(|s| !s.is_empty()) {
                        envs.push(("ANTHROPIC_BASE_URL".into(), b.to_string()));
                    }
                    if let Some(k) = v.get("llmApiKey").and_then(|k| k.as_str()).filter(|s| !s.is_empty() && *s != "***") {
                        envs.push(("ANTHROPIC_API_KEY".into(), k.to_string()));
                    }
                } else if provider == "Google" {
                    if let Some(b) = v.get("llmBaseUrl").and_then(|b| b.as_str()).filter(|s| !s.is_empty()) {
                        envs.push(("GOOGLE_BASE_URL".into(), b.to_string()));
                    }
                    if let Some(k) = v.get("llmApiKey").and_then(|k| k.as_str()).filter(|s| !s.is_empty() && *s != "***") {
                        envs.push(("GOOGLE_API_KEY".into(), k.to_string()));
                    }
                }
                if let Some(n) = v.get("numCtx") {
                    let s = n.as_i64().map(|i| i.to_string())
                        .or_else(|| n.as_str().map(String::from))
                        .filter(|s| !s.is_empty());
                    if let Some(s) = s {
                        envs.push(("NUM_CTX".into(), s));
                    }
                }
                if let Some(t) = v.get("temperature") {
                    let s = t.as_f64().map(|f| f.to_string())
                        .or_else(|| t.as_str().map(String::from))
                        .filter(|s| !s.is_empty());
                    if let Some(s) = s {
                        envs.push(("TEMPERATURE".into(), s));
                    }
                }
                if let Some(r) = v.get("repeatPenalty") {
                    let s = r.as_f64().map(|f| f.to_string())
                        .or_else(|| r.as_str().map(String::from))
                        .filter(|s| !s.is_empty());
                    if let Some(s) = s {
                        envs.push(("REPEAT_PENALTY".into(), s));
                    }
                }
                if let Some(p) = v.get("numPredict") {
                    let s = p.as_i64().map(|i| i.to_string())
                        .or_else(|| p.as_str().map(String::from))
                        .filter(|s| !s.is_empty());
                    if let Some(s) = s {
                        envs.push(("NUM_PREDICT".into(), s));
                    }
                }
            }
        }
    }
    if let Some(py_exe) = get_bundled_python(&app) {
        let py_dir = py_exe.parent().unwrap();
        if let Ok(path) = std::env::var("PATH") {
            envs.push(("PATH".into(), format!("{}{}{}", py_dir.display(), std::path::MAIN_SEPARATOR, path)));
        }
    }
    let mut cmd = std::process::Command::new(python);
    cmd.args(["-m", "uvicorn", "server:app", "--host", BACKEND_HOST, "--port", &BACKEND_PORT.to_string()])
        .current_dir(&backend_dir)
        .envs(envs.into_iter().collect::<std::collections::HashMap<_, _>>())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000);
    match cmd.spawn() {
        Ok(child) => {
            let _ = state.backend_child.lock().unwrap().insert(child);
            *state.backend_error.lock().unwrap() = None;
        }
        Err(e) => {
            let err = format!("Failed to start backend: {}", e);
            eprintln!("{}", err);
            *state.backend_error.lock().unwrap() = Some(err);
        }
    }
}

fn stop_backend(state: tauri::State<AppState>) {
    if let Some(mut child) = state.backend_child.lock().unwrap().take() {
        let pid = child.id();
        if let Ok(mut stream) = std::net::TcpStream::connect(format!("{}:{}", BACKEND_HOST, BACKEND_PORT)) {
            let _ = stream.set_read_timeout(Some(std::time::Duration::from_millis(300)));
            let req = format!(
                "POST /shutdown HTTP/1.1\r\nHost: {}:{}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
                BACKEND_HOST, BACKEND_PORT
            );
            let _ = stream.write_all(req.as_bytes());
        }
        let _ = child.kill();
        #[cfg(target_os = "windows")]
        {
            let _ = std::process::Command::new("taskkill")
                .args(["/pid", &pid.to_string(), "/f", "/t"])
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .status();
        }
    }
}

fn run_app() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            project_path: Mutex::new(PathBuf::from(".")),
            backend_child: Mutex::new(None),
            backend_error: Mutex::new(None),
        })
        .setup(|app| {
            let state = app.state::<AppState>();
            let doc_dir = app.path().document_dir().unwrap_or_else(|_| PathBuf::from("."));
            *state.project_path.lock().unwrap() = doc_dir.clone();
            start_backend(app.handle().clone(), state.clone(), doc_dir);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if window.label() == "main" {
                    if let Some(state) = window.try_state::<AppState>() {
                        stop_backend(state);
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_url,
            get_backend_error,
            get_project_path,
            get_file_tree,
            get_file_content,
            set_project_path,
            get_log_path,
            get_log_dir,
            set_log_dir,
            get_theme,
            set_theme,
            read_logs,
            open_folder,
            open_path,
            open_file,
            open_image,
            save_file,
            get_llm_provider,
            set_llm_provider,
            set_llm_config,
            get_llm_config,
            retry_backend,
            restart_backend,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

pub fn run() {
    run_app();
}
