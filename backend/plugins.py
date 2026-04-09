import asyncio
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
import inspect

from config import WORKSPACE_ROOT

CODEC_DIR = ".vencoder"
PLUGINS_DIR = CODEC_DIR + "/plugins"


class PluginHook(Enum):
    ON_START = "on_start"
    ON_STOP = "on_stop"
    ON_MESSAGE = "on_message"
    ON_TOOL_CALL = "on_tool_call"
    ON_TOOL_RESULT = "on_tool_result"
    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    ON_ERROR = "on_error"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"
    ON_FILE_EDIT = "on_file_edit"
    ON_SHELL_COMMAND = "on_shell_command"
    CUSTOM = "custom"


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    hooks: List[PluginHook]
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    path: Optional[Path] = None


@dataclass
class PluginContext:
    workspace_root: Path
    session_id: Optional[int]
    mode: str
    config: Dict[str, Any]


@dataclass
class HookResult:
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    continue_execution: bool = True


class Plugin:
    name: str = "base_plugin"
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    hooks: List[PluginHook] = []
    
    def __init__(self, context: PluginContext):
        self.context = context
        self.config = {}
    
    def setup(self) -> None:
        pass
    
    def teardown(self) -> None:
        pass
    
    async def on_start(self) -> HookResult:
        return HookResult()
    
    async def on_stop(self) -> HookResult:
        return HookResult()
    
    async def on_message(self, message: str) -> HookResult:
        return HookResult()
    
    async def pre_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> HookResult:
        return HookResult()
    
    async def post_tool_call(self, tool_name: str, tool_args: Dict[str, Any], result: Any) -> HookResult:
        return HookResult()
    
    async def on_tool_call(self, tool_name: str, tool_args: Dict[str, Any], result: Any) -> HookResult:
        return HookResult()
    
    async def on_error(self, error: Exception, context: Dict[str, Any]) -> HookResult:
        return HookResult()
    
    async def on_session_start(self, session_id: int) -> HookResult:
        return HookResult()
    
    async def on_session_end(self, session_id: int) -> HookResult:
        return HookResult()
    
    async def on_file_edit(self, file_path: str, old_content: str, new_content: str) -> HookResult:
        return HookResult()
    
    async def on_shell_command(self, command: str) -> HookResult:
        return HookResult()
    
    async def custom(self, event: str, data: Any) -> HookResult:
        return HookResult()


class PluginManager:
    def __init__(self, workspace_root: Path = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT.resolve()
        self.plugins_dir = self.workspace_root / PLUGINS_DIR
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._hook_handlers: Dict[PluginHook, List[Callable]] = {}
        self._load_plugins()
    
    def _load_plugins(self):
        config_file = self.plugins_dir / "plugins.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                    for plugin_data in data.get("plugins", []):
                        if plugin_data.get("enabled", True):
                            self._register_plugin_info(plugin_data)
            except Exception:
                pass
        
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
                self._load_plugin_from_dir(plugin_dir)
            elif plugin_dir.suffix == ".py" and plugin_dir.stem != "plugins":
                self._load_plugin_from_file(plugin_dir)
    
    def _register_plugin_info(self, data: Dict[str, Any]):
        info = PluginInfo(
            name=data.get("name", "unknown"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            hooks=[PluginHook(h) for h in data.get("hooks", [])],
            config=data.get("config", {}),
            enabled=data.get("enabled", True),
            path=Path(data.get("path", "")) if data.get("path") else None,
        )
        self._plugin_info[info.name] = info
    
    def _load_plugin_from_dir(self, plugin_dir: Path):
        plugin_name = plugin_dir.name
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"vencoder.plugins.{plugin_name}",
                plugin_dir / "__init__.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"vencoder.plugins.{plugin_name}"] = module
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                        context = PluginContext(
                            workspace_root=self.workspace_root,
                            session_id=None,
                            mode="agent",
                            config=self._plugin_info.get(plugin_name, PluginInfo(
                                name=plugin_name,
                                version="1.0.0",
                                description="",
                                author="",
                                hooks=[],
                            )).config,
                        )
                        plugin_instance = obj(context)
                        self._plugins[plugin_name] = plugin_instance
                        self._register_hook_handlers(plugin_instance)
        except Exception as e:
            print(f"Failed to load plugin {plugin_name}: {e}")
    
    def _load_plugin_from_file(self, plugin_file: Path):
        plugin_name = plugin_file.stem
        
        try:
            spec = importlib.util.spec_from_file_location(
                f"vencoder.plugins.{plugin_name}",
                plugin_file
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"vencoder.plugins.{plugin_name}"] = module
                spec.loader.exec_module(module)
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                        context = PluginContext(
                            workspace_root=self.workspace_root,
                            session_id=None,
                            mode="agent",
                            config=self._plugin_info.get(plugin_name, PluginInfo(
                                name=plugin_name,
                                version="1.0.0",
                                description="",
                                author="",
                                hooks=[],
                            )).config,
                        )
                        plugin_instance = obj(context)
                        self._plugins[plugin_name] = plugin_instance
                        self._register_hook_handlers(plugin_instance)
        except Exception as e:
            print(f"Failed to load plugin {plugin_name}: {e}")
    
    def _register_hook_handlers(self, plugin: Plugin):
        for hook in plugin.hooks:
            if hook not in self._hook_handlers:
                self._hook_handlers[hook] = []
            self._hook_handlers[hook].append(plugin)
    
    async def call_hook(self, hook: PluginHook, **kwargs) -> List[HookResult]:
        results = []
        handlers = self._hook_handlers.get(hook, [])
        
        for plugin in handlers:
            try:
                result = await self._execute_hook(plugin, hook, kwargs)
                results.append(result)
                if not result.continue_execution:
                    break
            except Exception as e:
                results.append(HookResult(success=False, error=str(e)))
        
        return results
    
    async def _execute_hook(self, plugin: Plugin, hook: PluginHook, kwargs: Dict) -> HookResult:
        if hook == PluginHook.ON_START:
            return await plugin.on_start()
        elif hook == PluginHook.ON_STOP:
            return await plugin.on_stop()
        elif hook == PluginHook.ON_MESSAGE:
            return await plugin.on_message(kwargs.get("message", ""))
        elif hook == PluginHook.PRE_TOOL_CALL:
            return await plugin.pre_tool_call(
                kwargs.get("tool_name", ""),
                kwargs.get("tool_args", {})
            )
        elif hook == PluginHook.POST_TOOL_CALL:
            return await plugin.post_tool_call(
                kwargs.get("tool_name", ""),
                kwargs.get("tool_args", {}),
                kwargs.get("result")
            )
        elif hook == PluginHook.ON_TOOL_CALL:
            return await plugin.on_tool_call(
                kwargs.get("tool_name", ""),
                kwargs.get("tool_args", {}),
                kwargs.get("result")
            )
        elif hook == PluginHook.ON_ERROR:
            return await plugin.on_error(
                kwargs.get("error"),
                kwargs.get("context", {})
            )
        elif hook == PluginHook.ON_SESSION_START:
            return await plugin.on_session_start(kwargs.get("session_id", 0))
        elif hook == PluginHook.ON_SESSION_END:
            return await plugin.on_session_end(kwargs.get("session_id", 0))
        elif hook == PluginHook.ON_FILE_EDIT:
            return await plugin.on_file_edit(
                kwargs.get("file_path", ""),
                kwargs.get("old_content", ""),
                kwargs.get("new_content", "")
            )
        elif hook == PluginHook.ON_SHELL_COMMAND:
            return await plugin.on_shell_command(kwargs.get("command", ""))
        elif hook == PluginHook.CUSTOM:
            return await plugin.custom(
                kwargs.get("event", ""),
                kwargs.get("data")
            )
        return HookResult()
    
    async def on_start(self) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_START)
    
    async def on_stop(self) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_STOP)
    
    async def on_message(self, message: str) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_MESSAGE, message=message)
    
    async def pre_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> List[HookResult]:
        return await self.call_hook(PluginHook.PRE_TOOL_CALL, tool_name=tool_name, tool_args=tool_args)
    
    async def post_tool_call(self, tool_name: str, tool_args: Dict[str, Any], result: Any) -> List[HookResult]:
        return await self.call_hook(PluginHook.POST_TOOL_CALL, tool_name=tool_name, tool_args=tool_args, result=result)
    
    async def on_tool_call(self, tool_name: str, tool_args: Dict[str, Any], result: Any) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_TOOL_CALL, tool_name=tool_name, tool_args=tool_args, result=result)
    
    async def on_error(self, error: Exception, context: Dict[str, Any] = None) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_ERROR, error=error, context=context or {})
    
    async def on_session_start(self, session_id: int) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_SESSION_START, session_id=session_id)
    
    async def on_session_end(self, session_id: int) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_SESSION_END, session_id=session_id)
    
    async def on_file_edit(self, file_path: str, old_content: str, new_content: str) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_FILE_EDIT, file_path=file_path, old_content=old_content, new_content=new_content)
    
    async def on_shell_command(self, command: str) -> List[HookResult]:
        return await self.call_hook(PluginHook.ON_SHELL_COMMAND, command=command)
    
    async def emit(self, event: str, data: Any = None) -> List[HookResult]:
        return await self.call_hook(PluginHook.CUSTOM, event=event, data=data)
    
    def list_plugins(self) -> List[PluginInfo]:
        return list(self._plugin_info.values())
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)
    
    def enable_plugin(self, name: str) -> bool:
        if name in self._plugin_info:
            self._plugin_info[name].enabled = True
            self._save_config()
            return True
        return False
    
    def disable_plugin(self, name: str) -> bool:
        if name in self._plugin_info:
            self._plugin_info[name].enabled = False
            self._save_config()
            return True
        return False
    
    def _save_config(self):
        config_file = self.plugins_dir / "plugins.json"
        data = {
            "plugins": [
                {
                    "name": info.name,
                    "version": info.version,
                    "description": info.description,
                    "author": info.author,
                    "hooks": [h.value for h in info.hooks],
                    "config": info.config,
                    "enabled": info.enabled,
                    "path": str(info.path) if info.path else None,
                }
                for info in self._plugin_info.values()
            ]
        }
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2)


class BuiltinPlugins:
    @staticmethod
    def create_logger_plugin() -> Type[Plugin]:
        class LoggerPlugin(Plugin):
            name = "logger"
            version = "1.0.0"
            description = "Logs all events to file"
            author = "VenCoder"
            hooks = [PluginHook.ON_MESSAGE, PluginHook.ON_TOOL_CALL]
            
            def setup(self):
                self.log_file = self.context.workspace_root / ".vencoder" / "logs" / "plugin.log"
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            async def on_message(self, message: str) -> HookResult:
                with open(self.log_file, "a") as f:
                    f.write(f"[MESSAGE] {message}\n")
                return HookResult()
            
            async def on_tool_call(self, tool_name: str, tool_args: Dict, result: Any) -> HookResult:
                with open(self.log_file, "a") as f:
                    f.write(f"[TOOL] {tool_name}({tool_args}) -> {result}\n")
                return HookResult()
        
        return LoggerPlugin
    
    @staticmethod
    def create_metrics_plugin() -> Type[Plugin]:
        class MetricsPlugin(Plugin):
            name = "metrics"
            version = "1.0.0"
            description = "Collects usage metrics"
            author = "VenCoder"
            hooks = [PluginHook.ON_SESSION_START, PluginHook.ON_SESSION_END, PluginHook.ON_TOOL_CALL]
            
            def setup(self):
                self.metrics = {
                    "sessions": 0,
                    "tool_calls": {},
                    "total_messages": 0,
                }
                self.metrics_file = self.context.workspace_root / ".vencoder" / "metrics.json"
                self._load_metrics()
            
            def _load_metrics(self):
                if self.metrics_file.exists():
                    try:
                        with open(self.metrics_file) as f:
                            self.metrics = json.load(f)
                    except Exception:
                        pass
            
            def _save_metrics(self):
                with open(self.metrics_file, "w") as f:
                    json.dump(self.metrics, f, indent=2)
            
            async def on_session_start(self, session_id: int) -> HookResult:
                self.metrics["sessions"] += 1
                self._save_metrics()
                return HookResult()
            
            async def on_tool_call(self, tool_name: str, tool_args: Dict, result: Any) -> HookResult:
                if tool_name not in self.metrics["tool_calls"]:
                    self.metrics["tool_calls"][tool_name] = 0
                self.metrics["tool_calls"][tool_name] += 1
                self._save_metrics()
                return HookResult()
        
        return MetricsPlugin
    
    @staticmethod
    def create_auto_backup_plugin() -> Type[Plugin]:
        class AutoBackupPlugin(Plugin):
            name = "auto_backup"
            version = "1.0.0"
            description = "Automatically backs up files before editing"
            author = "VenCoder"
            hooks = [PluginHook.PRE_TOOL_CALL]
            
            async def pre_tool_call(self, tool_name: str, tool_args: Dict) -> HookResult:
                if tool_name in ["edit_file", "write_file", "delete_file"]:
                    file_path = tool_args.get("path", "")
                    if file_path:
                        backup_dir = self.context.workspace_root / ".vencoder" / "backups"
                        backup_dir.mkdir(parents=True, exist_ok=True)
                return HookResult()
        
        return AutoBackupPlugin


def create_example_plugin() -> str:
    return '''"""Example VenCoder Plugin"""

from vencoder.plugins import Plugin, PluginHook, HookResult, PluginContext
from typing import Dict, Any

class MyPlugin(Plugin):
    """My custom VenCoder plugin."""
    
    name = "my_plugin"
    version = "1.0.0"
    description = "Description of what my plugin does"
    author = "Your Name"
    hooks = [
        PluginHook.ON_MESSAGE,
        PluginHook.ON_TOOL_CALL,
        PluginHook.ON_ERROR,
    ]
    
    def setup(self):
        """Called when plugin is loaded."""
        self.some_setting = self.config.get("some_setting", "default")
    
    async def on_message(self, message: str) -> HookResult:
        """Called when user sends a message."""
        # Process message, optionally modify it
        # Return HookResult(continue_execution=False) to stop processing
        return HookResult()
    
    async def pre_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> HookResult:
        """Called before a tool is executed."""
        # Can modify tool_args or block the call
        return HookResult()
    
    async def post_tool_call(self, tool_name: str, tool_args: Dict[str, Any], result: Any) -> HookResult:
        """Called after a tool is executed."""
        return HookResult()
    
    async def on_error(self, error: Exception, context: Dict[str, Any]) -> HookResult:
        """Called when an error occurs."""
        return HookResult()


def get_plugin_class():
    return MyPlugin
'''
