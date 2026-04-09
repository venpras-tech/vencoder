import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from config import WORKSPACE_ROOT


@dataclass
class Skill:
    name: str
    description: str
    command: str
    triggers: List[str] = field(default_factory=list)
    working_dir: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    timeout: int = 60
    enabled: bool = True
    category: str = "custom"
    icon: str = "⚡"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Skill':
        return cls(**data)

    def matches_trigger(self, message: str) -> bool:
        message_lower = message.lower()
        for trigger in self.triggers:
            if trigger.lower() in message_lower:
                return True
            if re.search(trigger, message, re.IGNORECASE):
                return True
        return False


@dataclass
class SkillResult:
    success: bool
    output: str
    error: Optional[str] = None
    skill_name: str = ""
    execution_time: float = 0


class SkillManager:
    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT
        self.skills_dir = self.workspace_root / ".vencoder" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills_cache: Dict[str, Skill] = {}
        self._load_builtin_skills()

    def _load_builtin_skills(self):
        builtin_skills_path = Path(__file__).parent / "builtin_skills.json"
        if builtin_skills_path.exists():
            try:
                data = json.loads(builtin_skills_path.read_text())
                for skill_data in data.get("skills", []):
                    skill = Skill.from_dict(skill_data)
                    self._skills_cache[skill.name] = skill
            except Exception:
                pass

    def load_user_skills(self) -> Dict[str, Skill]:
        user_skills = {}
        for skill_file in self.skills_dir.glob("*.yaml"):
            try:
                skill = self._load_yaml_skill(skill_file)
                if skill:
                    user_skills[skill.name] = skill
            except Exception:
                pass

        for skill_file in self.skills_dir.glob("*.json"):
            try:
                skill = self._load_json_skill(skill_file)
                if skill:
                    user_skills[skill.name] = skill
            except Exception:
                pass

        return user_skills

    def get_all_skills(self) -> Dict[str, Skill]:
        all_skills = self._skills_cache.copy()
        all_skills.update(self.load_user_skills())
        return all_skills

    def get_skill(self, name: str) -> Optional[Skill]:
        all_skills = self.get_all_skills()
        return all_skills.get(name)

    def get_enabled_skills(self) -> List[Skill]:
        return [s for s in self.get_all_skills().values() if s.enabled]

    def find_matching_skills(self, message: str) -> List[Skill]:
        matches = []
        for skill in self.get_enabled_skills():
            if skill.matches_trigger(message):
                matches.append(skill)
        return matches

    def execute_skill(self, skill_name: str, context: Optional[Dict] = None) -> SkillResult:
        import time
        start_time = time.time()

        skill = self.get_skill(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                output="",
                error=f"Skill '{skill_name}' not found",
                skill_name=skill_name,
            )

        if not skill.enabled:
            return SkillResult(
                success=False,
                output="",
                error=f"Skill '{skill_name}' is disabled",
                skill_name=skill_name,
            )

        context = context or {}
        command = self._interpolate_command(skill.command, context)

        env = os.environ.copy()
        env.update(skill.env)
        for key, value in context.items():
            env[f"SKILL_{key.upper()}"] = str(value)

        cwd = self.workspace_root
        if skill.working_dir:
            cwd = self.workspace_root / skill.working_dir
            if not cwd.exists():
                cwd = self.workspace_root

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=skill.timeout,
                env=env,
            )
            execution_time = time.time() - start_time

            if result.returncode == 0:
                return SkillResult(
                    success=True,
                    output=result.stdout.strip() or "(no output)",
                    skill_name=skill_name,
                    execution_time=execution_time,
                )
            else:
                return SkillResult(
                    success=False,
                    output=result.stdout.strip(),
                    error=result.stderr.strip() or f"Command exited with code {result.returncode}",
                    skill_name=skill_name,
                    execution_time=execution_time,
                )
        except subprocess.TimeoutExpired:
            return SkillResult(
                success=False,
                output="",
                error=f"Skill '{skill_name}' timed out after {skill.timeout}s",
                skill_name=skill_name,
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return SkillResult(
                success=False,
                output="",
                error=str(e),
                skill_name=skill_name,
                execution_time=time.time() - start_time,
            )

    def execute_matched_skills(self, message: str, context: Optional[Dict] = None) -> List[SkillResult]:
        results = []
        matched_skills = self.find_matching_skills(message)

        for skill in matched_skills:
            result = self.execute_skill(skill.name, context)
            results.append(result)

        return results

    def save_skill(self, skill: Skill) -> bool:
        try:
            skill_file = self.skills_dir / f"{skill.name}.json"
            skill_file.write_text(json.dumps(skill.to_dict(), indent=2))
            return True
        except Exception:
            return False

    def delete_skill(self, skill_name: str) -> bool:
        for ext in [".yaml", ".json"]:
            skill_file = self.skills_dir / f"{skill_name}{ext}"
            if skill_file.exists():
                try:
                    skill_file.unlink()
                    return True
                except Exception:
                    pass
        return False

    def enable_skill(self, skill_name: str) -> bool:
        skill = self.get_skill(skill_name)
        if skill:
            skill.enabled = True
            return self.save_skill(skill)
        return False

    def disable_skill(self, skill_name: str) -> bool:
        skill = self.get_skill(skill_name)
        if skill:
            skill.enabled = False
            return self.save_skill(skill)
        return False

    def _load_yaml_skill(self, skill_file: Path) -> Optional[Skill]:
        try:
            import yaml
            data = yaml.safe_load(skill_file.read_text())
            if data:
                return Skill.from_dict(data)
        except ImportError:
            pass
        return None

    def _load_json_skill(self, skill_file: Path) -> Optional[Skill]:
        try:
            data = json.loads(skill_file.read_text())
            return Skill.from_dict(data)
        except json.JSONDecodeError:
            return None

    def _interpolate_command(self, command: str, context: Dict) -> str:
        result = command
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        for key, value in os.environ.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        return result

    def list_skills(self) -> List[Dict]:
        skills = []
        for name, skill in self.get_all_skills().items():
            skills.append({
                "name": skill.name,
                "description": skill.description,
                "command": skill.command[:50] + "..." if len(skill.command) > 50 else skill.command,
                "triggers": skill.triggers,
                "enabled": skill.enabled,
                "category": skill.category,
                "icon": skill.icon,
            })
        return skills

    def get_skills_by_category(self) -> Dict[str, List[Skill]]:
        by_category = {}
        for skill in self.get_all_skills().values():
            if skill.category not in by_category:
                by_category[skill.category] = []
            by_category[skill.category].append(skill)
        return by_category


def execute_skill(skill_name: str, context: Optional[Dict] = None) -> SkillResult:
    manager = SkillManager()
    return manager.execute_skill(skill_name, context)


def find_and_execute_skills(message: str, context: Optional[Dict] = None) -> List[SkillResult]:
    manager = SkillManager()
    return manager.execute_matched_skills(message, context)


if __name__ == "__main__":
    manager = SkillManager()
    print("=== Available Skills ===")
    for skill in manager.get_all_skills().values():
        print(f"  {skill.icon} {skill.name}: {skill.description}")
        print(f"     Command: {skill.command}")
        print(f"     Triggers: {', '.join(skill.triggers)}")
        print()
