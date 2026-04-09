# VenCoder VS Code Extension

A VS Code extension that brings VenCoder AI coding assistant directly into your editor.

## Features

- **Chat Interface**: Interactive chat with VenCoder AI assistant
- **Real-time Collaboration**: Work with your team in real-time
- **Code Actions**: Explain, refactor, fix, and generate tests for selected code
- **Code Quality Checks**: Run linters, type checkers, and security scans
- **Git Integration**: View branches, commits, and changes
- **Memory System**: Persistent context across sessions
- **Skills & Hooks**: Automation and customization

## Installation

1. Open VS Code
2. Run `ext install vencoder` or search for "VenCoder" in the Extensions view
3. Restart VS Code

## Configuration

Add these settings to your `.vscode/settings.json`:

```json
{
  "vencoder.serverUrl": "http://localhost:8765",
  "vencoder.model": "codellama:13b",
  "vencoder.mode": "agent",
  "vencoder.collabServer": "ws://localhost:8766"
}
```

## Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `VenCoder: Chat` | `Ctrl+Shift+V` | Open chat interface |
| `VenCoder: Explain Code` | `Ctrl+Shift+E` | Explain selected code |
| `VenCoder: Refactor` | `Ctrl+Shift+R` | Refactor selected code |
| `VenCoder: Fix Problem` | `Ctrl+Shift+F` | Fix selected code |
| `VenCoder: Generate Tests` | `Ctrl+Shift+T` | Generate tests |
| `VenCoder: Run Checks` | | Run all code quality checks |

## Development

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Package for distribution
npm run package
```

## License

MIT
