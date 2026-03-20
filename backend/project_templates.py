PROJECT_TEMPLATES = {
    "python": """# Python Project

## Tech stack
- Python 3.10+
- See requirements.txt for dependencies

## Conventions
- Use type hints
- Prefer pathlib over os.path
- Use pytest for tests
""",
    "react": """# React Project

## Tech stack
- React 18+
- TypeScript
- Vite or Create React App

## Conventions
- Functional components with hooks
- Use .tsx for components
- Prefer named exports
""",
    "node": """# Node.js Project

## Tech stack
- Node.js 18+
- See package.json for dependencies

## Conventions
- Use ES modules
- Prefer async/await over callbacks
""",
    "rust": """# Rust Project

## Tech stack
- Rust (edition 2021)
- Cargo for build

## Conventions
- Prefer Result over panic
- Use thiserror/anyhow for error handling
""",
}


def get_template(name: str) -> str | None:
    return PROJECT_TEMPLATES.get(name.lower())


def list_templates() -> list[str]:
    return list(PROJECT_TEMPLATES.keys())
