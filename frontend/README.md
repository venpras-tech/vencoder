# React Frontend for AI Dev

This is the React-based frontend for AI Dev application.

## Setup

```bash
cd frontend
npm install
```

## Development

### Web Development (Hot Reload)
```bash
npm run dev
```
Then open http://localhost:5173

### Tauri Development
```bash
npm run tauri:dev
```

## Build

### Web Build
```bash
npm run build
```
Output is in `frontend/dist/`

### Tauri Build
```bash
npm run tauri:build
```

## Project Structure

```
frontend/
├── src/
│   ├── components/     # React components
│   ├── pages/          # Page components
│   ├── context/        # React context (AppContext)
│   ├── hooks/         # Custom hooks
│   ├── styles/         # Global CSS
│   ├── utils/          # API utilities
│   │   ├── electronAPI.js   # Electron IPC bridge
│   │   └── tauriAPI.js     # Tauri IPC bridge
│   ├── App.jsx        # Main app with routing
│   └── main.jsx       # Entry point
├── index.html
├── package.json
└── vite.config.js
```

## API Bridge

The frontend uses a unified API interface (`window.electronAPI`) that works with both Electron and Tauri:

- **Electron**: Uses IPC via `contextBridge`
- **Tauri**: Uses `@tauri-apps/api` via `invoke()`

The `main.jsx` automatically detects the runtime and sets up the appropriate API bridge.
