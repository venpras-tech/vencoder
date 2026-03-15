# Tauri Setup (alongside Electron)

Tauri is added as an alternative frontend. Electron remains the default/fallback.

## Prerequisites

1. **Rust** – Required for Tauri. Install from https://rustup.rs/
   ```powershell
   winget install Rustlang.Rustup
   ```
   Or: https://www.rust-lang.org/tools/install

2. **WebView2** – On Windows 10/11 it is usually preinstalled. If needed: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

## Scripts

| Script | Description |
|--------|-------------|
| `npm run start` | **Electron** (default) – `electron .` |
| `npm run start:tauri` | **Tauri** – `npx tauri dev` |
| `npm run build:tauri` | Build Tauri app – copies webview, runs `tauri build` |

## Running Tauri

```bash
npm run start:tauri
```

This will:
1. Start a static server on port 1420 serving `electron/`
2. Compile the Rust backend
3. Open the app in a Tauri window

## Building Tauri

```bash
npm run build:tauri
```

Output: `src-tauri/target/release/` (or `target/debug/` for dev builds).

## Structure

- `electron/` – Shared frontend (HTML, JS, CSS) for both Electron and Tauri
- `electron/tauri-bridge.js` – Provides `window.electronAPI` in Tauri (mirrors Electron preload)
- `src-tauri/` – Tauri Rust app (spawns Python backend, exposes commands)
- `dist-webview/` – Build output for Tauri (copied from `electron/`)

## Backend

Both Electron and Tauri spawn the same Python backend (`backend/server.py` via uvicorn). For Tauri:
- **Dev**: Uses `backend/` from project root; Python from PATH or `python-runtime/`
- **Build**: Backend and `python-runtime` are in `bundle.resources` and copied into the app
