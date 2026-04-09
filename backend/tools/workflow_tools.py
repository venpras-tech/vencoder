from langchain_core.tools import tool
from pathlib import Path
from config import WORKSPACE_ROOT


@tool
def list_available_skills() -> str:
    """List all available skills that can be triggered. Use to find custom automation skills."""
    from skills import SkillManager
    manager = SkillManager(WORKSPACE_ROOT)
    skills = manager.list_skills()
    
    if not skills:
        return "No skills available."
    
    lines = ["## Available Skills"]
    for skill in skills:
        icon = skill.get("icon", "⚡")
        name = skill.get("name", "")
        desc = skill.get("description", "")
        triggers = skill.get("triggers", [])
        enabled = skill.get("enabled", True)
        
        status = "✅" if enabled else "❌"
        lines.append(f"{icon} {status} **{name}**: {desc}")
        if triggers:
            lines.append(f"   Triggers: {', '.join(triggers[:5])}")
        lines.append("")
    
    return "\n".join(lines)


@tool
def execute_skill(skill_name: str) -> str:
    """Execute a specific skill by name. Use to run custom automation tasks."""
    from skills import SkillManager
    manager = SkillManager(WORKSPACE_ROOT)
    result = manager.execute_skill(skill_name)
    
    if result.success:
        return f"✅ Skill '{result.skill_name}' executed successfully:\n\n{result.output}"
    else:
        return f"❌ Skill '{result.skill_name}' failed:\n\n{result.error}"


@tool
def create_skill(name: str, description: str, command: str, triggers: str) -> str:
    """Create a new custom skill. Use when user wants to add custom automation."""
    from skills import SkillManager, Skill
    manager = SkillManager(WORKSPACE_ROOT)
    
    trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]
    
    skill = Skill(
        name=name,
        description=description,
        command=command,
        triggers=trigger_list,
    )
    
    if manager.save_skill(skill):
        return f"✅ Skill '{name}' created successfully."
    else:
        return f"❌ Failed to create skill '{name}'."


@tool
def delete_skill(skill_name: str) -> str:
    """Delete a custom skill by name."""
    from skills import SkillManager
    manager = SkillManager(WORKSPACE_ROOT)
    
    if manager.delete_skill(skill_name):
        return f"✅ Skill '{skill_name}' deleted."
    else:
        return f"❌ Skill '{skill_name}' not found."


@tool
def list_hooks() -> str:
    """List all registered hooks. Use to see what automation hooks are configured."""
    from hooks import HookManager
    manager = HookManager(WORKSPACE_ROOT)
    hooks = manager.list_hooks()
    
    if not hooks:
        return "No hooks configured."
    
    lines = ["## Available Hooks"]
    for hook in hooks:
        name = hook.get("name", "")
        desc = hook.get("description", "")
        event = hook.get("event", "")
        enabled = hook.get("enabled", True)
        cmd = hook.get("command", "")
        
        status = "✅" if enabled else "❌"
        lines.append(f"{status} **{name}** ({event}): {desc}")
        if cmd:
            lines.append(f"   Command: {cmd[:60]}{'...' if len(cmd) > 60 else ''}")
        lines.append("")
    
    return "\n".join(lines)


@tool
def create_hook(name: str, event: str, command: str, description: str = "") -> str:
    """Create a new automation hook. Use to automate actions on specific events."""
    from hooks import HookManager, Hook
    manager = HookManager(WORKSPACE_ROOT)
    
    hook = Hook(
        name=name,
        event=event,
        command=command,
        description=description,
    )
    
    if manager.register_hook(hook):
        return f"✅ Hook '{name}' created successfully for event '{event}'."
    else:
        return f"❌ Failed to create hook '{name}'."


@tool
def delete_hook(hook_name: str) -> str:
    """Delete a hook by name."""
    from hooks import HookManager
    manager = HookManager(WORKSPACE_ROOT)
    
    if manager.unregister_hook(hook_name):
        return f"✅ Hook '{hook_name}' deleted."
    else:
        return f"❌ Hook '{hook_name}' not found."


@tool
def enable_hook(hook_name: str) -> str:
    """Enable a disabled hook."""
    from hooks import HookManager
    manager = HookManager(WORKSPACE_ROOT)
    
    if manager.enable_hook(hook_name):
        return f"✅ Hook '{hook_name}' enabled."
    else:
        return f"❌ Hook '{hook_name}' not found."


@tool
def disable_hook(hook_name: str) -> str:
    """Disable a hook without deleting it."""
    from hooks import HookManager
    manager = HookManager(WORKSPACE_ROOT)
    
    if manager.disable_hook(hook_name):
        return f"✅ Hook '{hook_name}' disabled."
    else:
        return f"❌ Hook '{hook_name}' not found."


@tool
def get_hook_templates() -> str:
    """Get available hook templates that can be quickly created."""
    from hooks import HookManager
    manager = HookManager(WORKSPACE_ROOT)
    templates = manager.get_available_templates()
    
    lines = ["## Available Hook Templates"]
    lines.append("")
    lines.append("Use `create_hook` with template name to create:")
    lines.append("")
    
    template_descriptions = {
        "pre-commit-lint": "Run linter before commit",
        "pre-commit-test": "Run tests before commit",
        "pre-edit-format": "Format file before editing",
        "post-edit-format": "Format file after editing",
        "post-test-coverage": "Check test coverage after tests",
    }
    
    for template in templates:
        desc = template_descriptions.get(template, "")
        lines.append(f"- **{template}**: {desc}")
    
    return "\n".join(lines)
