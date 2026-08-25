use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

static PYTHON_CHILD: Mutex<Option<Child>> = Mutex::new(None);

fn spawn_python_backend(app: &tauri::App) {
    let resource_path = app
        .path()
        .resource_dir()
        .expect("failed to get resource dir");

    // In dev mode, use the trading-client python from the project
    // In production, use the bundled python
    let (python_exe, working_dir) = if cfg!(debug_assertions) {
        // Dev: current_dir is src-tauri, parent=desktop, parent=trading-client
        let working_dir = std::env::current_dir()
            .expect("failed to get cwd")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .to_path_buf();
        ("python".to_string(), working_dir)
    } else {
        // Production: use bundled python
        (
            resource_path.join("python").join("python.exe").to_string_lossy().to_string(),
            resource_path.join("app"),
        )
    };

    let child = Command::new(&python_exe)
        .arg("-m")
        .arg("uvicorn")
        .arg("app.api.app:app")
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg("18652")
        .current_dir(&working_dir)
        .spawn();

    match child {
        Ok(c) => {
            println!("Python backend started (PID: {})", c.id());
            *PYTHON_CHILD.lock().unwrap() = Some(c);
        }
        Err(e) => {
            eprintln!("Failed to start Python backend: {}", e);
        }
    }
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            spawn_python_backend(app);
            Ok(())
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut guard) = PYTHON_CHILD.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                        println!("Python backend stopped");
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
