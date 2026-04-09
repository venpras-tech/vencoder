import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
import hashlib
import hmac
import secrets

from config import WORKSPACE_ROOT


class APIAuthType(Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    HMAC = "hmac"


@dataclass
class APIEndpoint:
    name: str
    path: str
    method: str
    handler: Callable
    auth_type: APIAuthType = APIAuthType.NONE
    description: str = ""
    tags: List[str] = field(default_factory=list)
    rate_limit: int = 100
    rate_window: int = 60


@dataclass
class APIKey:
    key_id: str
    key_hash: str
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    permissions: List[str] = field(default_factory=list)
    rate_limit: int = 100


@dataclass
class APIRequest:
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[Dict[str, Any]] = None
    auth: Optional[str] = None


@dataclass
class APIResponse:
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    error: Optional[str] = None


@dataclass
class RateLimitEntry:
    count: int = 0
    window_start: datetime = field(default_factory=datetime.now)


class ExternalAPI:
    def __init__(self, workspace_root: Path = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT.resolve()
        self.api_dir = self.workspace_root / ".vencoder" / "api"
        self.api_dir.mkdir(parents=True, exist_ok=True)
        
        self.endpoints: Dict[str, APIEndpoint] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.rate_limits: Dict[str, RateLimitEntry] = {}
        
        self._load_keys()
        self._register_default_endpoints()
    
    def _load_keys(self):
        keys_file = self.api_dir / "keys.json"
        if keys_file.exists():
            try:
                with open(keys_file) as f:
                    data = json.load(f)
                    for key_data in data.get("keys", []):
                        self.api_keys[key_data["key_id"]] = APIKey(
                            key_id=key_data["key_id"],
                            key_hash=key_data["key_hash"],
                            name=key_data["name"],
                            created_at=datetime.fromisoformat(key_data["created_at"]),
                            last_used=datetime.fromisoformat(key_data["last_used"]) if key_data.get("last_used") else None,
                            permissions=key_data.get("permissions", []),
                            rate_limit=key_data.get("rate_limit", 100),
                        )
            except Exception:
                pass
    
    def _save_keys(self):
        keys_file = self.api_dir / "keys.json"
        data = {
            "keys": [
                {
                    "key_id": k.key_id,
                    "key_hash": k.key_hash,
                    "name": k.name,
                    "created_at": k.created_at.isoformat(),
                    "last_used": k.last_used.isoformat() if k.last_used else None,
                    "permissions": k.permissions,
                    "rate_limit": k.rate_limit,
                }
                for k in self.api_keys.values()
            ]
        }
        with open(keys_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def _register_default_endpoints(self):
        self.register_endpoint(APIEndpoint(
            name="health",
            path="/health",
            method="GET",
            handler=self._health_handler,
            description="Health check endpoint",
        ))
        
        self.register_endpoint(APIEndpoint(
            name="status",
            path="/status",
            method="GET",
            handler=self._status_handler,
            description="Get API status",
        ))
        
        self.register_endpoint(APIEndpoint(
            name="execute",
            path="/execute",
            method="POST",
            handler=self._execute_handler,
            auth_type=APIAuthType.API_KEY,
            description="Execute a command",
            tags=["execution"],
        ))
        
        self.register_endpoint(APIEndpoint(
            name="query",
            path="/query",
            method="POST",
            handler=self._query_handler,
            auth_type=APIAuthType.API_KEY,
            description="Query the agent",
            tags=["chat"],
        ))
    
    def _health_handler(self, request: APIRequest) -> APIResponse:
        return APIResponse(status=200, body={"status": "healthy", "timestamp": datetime.now().isoformat()})
    
    def _status_handler(self, request: APIRequest) -> APIResponse:
        return APIResponse(status=200, body={
            "status": "running",
            "version": "1.0.0",
            "endpoints": len(self.endpoints),
            "active_keys": len(self.api_keys),
        })
    
    async def _execute_handler(self, request: APIRequest) -> APIResponse:
        if not request.body:
            return APIResponse(status=400, error="Missing request body")
        
        command = request.body.get("command")
        if not command:
            return APIResponse(status=400, error="Missing 'command' field")
        
        return APIResponse(status=200, body={"executed": True, "command": command})
    
    async def _query_handler(self, request: APIRequest) -> APIResponse:
        if not request.body:
            return APIResponse(status=400, error="Missing request body")
        
        message = request.body.get("message")
        if not message:
            return APIResponse(status=400, error="Missing 'message' field")
        
        return APIResponse(status=200, body={"message": message, "response": "Query received"})
    
    def register_endpoint(self, endpoint: APIEndpoint):
        key = f"{endpoint.method}:{endpoint.path}"
        self.endpoints[key] = endpoint
    
    def unregister_endpoint(self, method: str, path: str):
        key = f"{method}:{path}"
        if key in self.endpoints:
            del self.endpoints[key]
    
    def create_api_key(self, name: str, permissions: List[str] = None) -> tuple[str, str]:
        key_id = secrets.token_hex(8)
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            created_at=datetime.now(),
            permissions=permissions or [],
        )
        
        self.api_keys[key_id] = api_key
        self._save_keys()
        
        return key_id, raw_key
    
    def revoke_api_key(self, key_id: str) -> bool:
        if key_id in self.api_keys:
            del self.api_keys[key_id]
            self._save_keys()
            return True
        return False
    
    def list_api_keys(self) -> List[Dict[str, Any]]:
        return [
            {
                "key_id": k.key_id,
                "name": k.name,
                "created_at": k.created_at.isoformat(),
                "last_used": k.last_used.isoformat() if k.last_used else None,
                "permissions": k.permissions,
                "rate_limit": k.rate_limit,
            }
            for k in self.api_keys.values()
        ]
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        for key in self.api_keys.values():
            if hmac.compare_digest(key.key_hash, key_hash):
                key.last_used = datetime.now()
                self._save_keys()
                return key
        
        return None
    
    def check_rate_limit(self, key_id: str, limit: int = 100, window: int = 60) -> bool:
        now = datetime.now()
        
        if key_id not in self.rate_limits:
            self.rate_limits[key_id] = RateLimitEntry()
        
        entry = self.rate_limits[key_id]
        
        if (now - entry.window_start).total_seconds() > window:
            entry.count = 0
            entry.window_start = now
        
        if entry.count >= limit:
            return False
        
        entry.count += 1
        return True
    
    async def handle_request(self, request: APIRequest) -> APIResponse:
        key = f"{request.method}:{request.path}"
        
        if key not in self.endpoints:
            return APIResponse(status=404, error=f"Endpoint not found: {request.method} {request.path}")
        
        endpoint = self.endpoints[key]
        
        if endpoint.auth_type == APIAuthType.API_KEY:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return APIResponse(status=401, error="Missing or invalid Authorization header")
            
            raw_key = auth_header[7:]
            api_key = self.validate_api_key(raw_key)
            
            if not api_key:
                return APIResponse(status=401, error="Invalid API key")
            
            if api_key.permissions and endpoint.name not in api_key.permissions:
                return APIResponse(status=403, error="Insufficient permissions")
            
            if not self.check_rate_limit(api_key.key_id, api_key.rate_limit, endpoint.rate_window):
                return APIResponse(status=429, error="Rate limit exceeded")
        
        handler = endpoint.handler
        
        if asyncio.iscoroutinefunction(handler):
            return await handler(request)
        else:
            return handler(request)
    
    def get_openapi_spec(self) -> Dict[str, Any]:
        paths = {}
        for endpoint in self.endpoints.values():
            if endpoint.path not in paths:
                paths[endpoint.path] = {}
            
            path_item = paths[endpoint.path]
            path_item[endpoint.method.lower()] = {
                "summary": endpoint.name,
                "description": endpoint.description,
                "tags": endpoint.tags,
                "responses": {
                    "200": {"description": "Success"},
                    "400": {"description": "Bad Request"},
                    "401": {"description": "Unauthorized"},
                    "403": {"description": "Forbidden"},
                    "404": {"description": "Not Found"},
                    "429": {"description": "Rate Limit Exceeded"},
                },
            }
        
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "VenCoder External API",
                "version": "1.0.0",
                "description": "External API for VenCoder integration",
            },
            "paths": paths,
        }


class MCPServer:
    def __init__(self, workspace_root: Path = None):
        self.workspace_root = workspace_root or WORKSPACE_ROOT.resolve()
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, Any]] = {}
        
        self.mcp_dir = self.workspace_root / ".vencoder" / "mcp"
        self.mcp_dir.mkdir(parents=True, exist_ok=True)
    
    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable):
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }
    
    def register_resource(self, uri: str, name: str, description: str, mime_type: str = "text/plain"):
        self.resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "mimeType": mime_type,
        }
    
    def register_prompt(self, name: str, description: str, arguments: List[Dict], template: str):
        self.prompts[name] = {
            "name": name,
            "description": description,
            "arguments": arguments,
            "template": template,
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {k: v for k, v in t.items() if k != "handler"}
            for t in self.tools.values()
        ]
    
    def list_resources(self) -> List[Dict[str, Any]]:
        return list(self.resources.values())
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        return [
            {k: v for k, v in p.items() if k != "template"}
            for p in self.prompts.values()
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self.tools:
            return {"error": f"Tool not found: {name}"}
        
        tool = self.tools[name]
        handler = tool["handler"]
        
        try:
            result = await handler(**arguments) if asyncio.iscoroutinefunction(handler) else handler(**arguments)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    def get_mcp_manifest(self) -> Dict[str, Any]:
        return {
            "name": "VenCoder MCP",
            "version": "1.0.0",
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": len(self.tools) > 0,
                "resources": len(self.resources) > 0,
                "prompts": len(self.prompts) > 0,
            },
            "tools": self.list_tools(),
            "resources": self.list_resources(),
            "prompts": self.list_prompts(),
        }
