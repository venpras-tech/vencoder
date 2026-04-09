import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import websockets
from websockets.server import WebSocketServerProtocol

from config import WORKSPACE_ROOT


class MessageType(Enum):
    JOIN = "join"
    LEAVE = "leave"
    CHAT = "chat"
    CURSOR = "cursor"
    SELECTION = "selection"
    EDIT = "edit"
    COMMAND = "command"
    TYPING = "typing"
    USER_LIST = "user_list"
    ERROR = "error"
    SYSTEM = "system"


@dataclass
class CollaborationUser:
    id: str
    name: str
    color: str
    joined_at: datetime = field(default_factory=datetime.now)
    cursor_position: Optional[Dict[str, int]] = None
    selection: Optional[Dict[str, Any]] = None
    is_typing: bool = False


@dataclass
class CollaborationMessage:
    type: MessageType
    user_id: Optional[str] = None
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    room_id: Optional[str] = None


@dataclass
class CollaborationRoom:
    id: str
    name: str
    created_at: datetime = field(default_factory=datetime.now)
    owner: str = ""
    users: Dict[str, CollaborationUser] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=lambda: {
        "allow_edits": True,
        "allow_commands": False,
        "max_history": 1000,
    })
    history: List[CollaborationMessage] = field(default_factory=list)


class CollaborationServer:
    def __init__(self, workspace_root: Path = None, host: str = "localhost", port: int = 8766):
        self.workspace_root = workspace_root or WORKSPACE_ROOT.resolve()
        self.host = host
        self.port = port
        self.rooms: Dict[str, CollaborationRoom] = {}
        self.user_rooms: Dict[str, str] = {}
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        self.user_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
            "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
            "#BB8FCE", "#85C1E2", "#F8B500", "#00CED1",
        ]
        self._server = None
    
    async def start(self):
        self._server = await websockets.serve(self._handle_client, self.host, self.port)
        print(f"Collaboration server started on ws://{self.host}:{self.port}")
    
    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            print("Collaboration server stopped")
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        user_id = str(uuid.uuid4())[:8]
        self.connections[user_id] = websocket
        
        try:
            async for message in websocket:
                await self._process_message(user_id, websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self._handle_disconnect(user_id)
    
    async def _process_message(self, user_id: str, websocket: WebSocketServerProtocol, raw_message: str):
        try:
            msg_data = json.loads(raw_message)
            msg_type = MessageType(msg_data.get("type", "system"))
            data = msg_data.get("data", {})
            room_id = msg_data.get("room_id")
            
            if msg_type == MessageType.JOIN:
                await self._handle_join(user_id, websocket, data)
            elif msg_type == MessageType.CHAT:
                await self._handle_chat(user_id, room_id, data)
            elif msg_type == MessageType.CURSOR:
                await self._handle_cursor(user_id, room_id, data)
            elif msg_type == MessageType.SELECTION:
                await self._handle_selection(user_id, room_id, data)
            elif msg_type == MessageType.EDIT:
                await self._handle_edit(user_id, room_id, data)
            elif msg_type == MessageType.COMMAND:
                await self._handle_command(user_id, room_id, data)
            elif msg_type == MessageType.TYPING:
                await self._handle_typing(user_id, room_id, data)
            elif msg_type == MessageType.LEAVE:
                await self._handle_leave(user_id)
            else:
                await self._broadcast_to_room(user_id, room_id, MessageType.SYSTEM, {"message": "Unknown message type"})
        except json.JSONDecodeError:
            await self._send_error(user_id, "Invalid JSON message")
        except Exception as e:
            await self._send_error(user_id, str(e))
    
    async def _handle_join(self, user_id: str, websocket: WebSocketServerProtocol, data: Dict):
        room_id = data.get("room_id")
        user_name = data.get("name", f"User_{user_id}")
        
        if room_id not in self.rooms:
            self.rooms[room_id] = CollaborationRoom(
                id=room_id,
                name=data.get("room_name", f"Room_{room_id}"),
                owner=user_id,
            )
        
        room = self.rooms[room_id]
        color_index = len(room.users) % len(self.user_colors)
        
        user = CollaborationUser(
            id=user_id,
            name=user_name,
            color=self.user_colors[color_index],
        )
        
        room.users[user_id] = user
        self.user_rooms[user_id] = room_id
        self.connections[user_id] = websocket
        
        await self._send(user_id, MessageType.JOIN, {
            "user_id": user_id,
            "room_id": room_id,
            "history": [
                {"type": m.type.value, "data": m.data, "timestamp": m.timestamp.isoformat()}
                for m in room.history[-100:]
            ],
        })
        
        await self._broadcast_to_room(user_id, room_id, MessageType.USER_LIST, {
            "users": [
                {
                    "id": u.id,
                    "name": u.name,
                    "color": u.color,
                    "cursor_position": u.cursor_position,
                    "is_typing": u.is_typing,
                }
                for u in room.users.values()
            ]
        })
        
        await self._broadcast_to_room(None, room_id, MessageType.SYSTEM, {
            "message": f"{user_name} joined the room"
        })
    
    async def _handle_chat(self, user_id: str, room_id: Optional[str], data: Dict):
        if not room_id or room_id not in self.rooms:
            await self._send_error(user_id, "Not in a room")
            return
        
        room = self.rooms[room_id]
        message = CollaborationMessage(
            type=MessageType.CHAT,
            user_id=user_id,
            data=data,
            room_id=room_id,
        )
        
        room.history.append(message)
        if len(room.history) > room.settings["max_history"]:
            room.history = room.history[-room.settings["max_history"]:]
        
        await self._broadcast_to_room(user_id, room_id, MessageType.CHAT, {
            "user_id": user_id,
            "user_name": room.users[user_id].name,
            "user_color": room.users[user_id].color,
            "message": data.get("message", ""),
            "timestamp": message.timestamp.isoformat(),
        })
    
    async def _handle_cursor(self, user_id: str, room_id: Optional[str], data: Dict):
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        if user_id in room.users:
            room.users[user_id].cursor_position = data.get("position")
            await self._broadcast_to_room(user_id, room_id, MessageType.CURSOR, {
                "user_id": user_id,
                "user_name": room.users[user_id].name,
                "user_color": room.users[user_id].color,
                "position": data.get("position"),
            })
    
    async def _handle_selection(self, user_id: str, room_id: Optional[str], data: Dict):
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        if user_id in room.users:
            room.users[user_id].selection = data.get("selection")
            await self._broadcast_to_room(user_id, room_id, MessageType.SELECTION, {
                "user_id": user_id,
                "selection": data.get("selection"),
            })
    
    async def _handle_edit(self, user_id: str, room_id: Optional[str], data: Dict):
        if not room_id or room_id not in self.rooms:
            await self._send_error(user_id, "Not in a room")
            return
        
        room = self.rooms[room_id]
        if not room.settings["allow_edits"]:
            await self._send_error(user_id, "Edits not allowed in this room")
            return
        
        message = CollaborationMessage(
            type=MessageType.EDIT,
            user_id=user_id,
            data=data,
            room_id=room_id,
        )
        
        room.history.append(message)
        
        await self._broadcast_to_room(user_id, room_id, MessageType.EDIT, {
            "user_id": user_id,
            "user_name": room.users[user_id].name,
            "file_path": data.get("file_path"),
            "old_content": data.get("old_content"),
            "new_content": data.get("new_content"),
            "timestamp": message.timestamp.isoformat(),
        })
    
    async def _handle_command(self, user_id: str, room_id: Optional[str], data: Dict):
        if not room_id or room_id not in self.rooms:
            await self._send_error(user_id, "Not in a room")
            return
        
        room = self.rooms[room_id]
        if not room.settings["allow_commands"]:
            await self._send_error(user_id, "Commands not allowed in this room")
            return
        
        await self._broadcast_to_room(user_id, room_id, MessageType.COMMAND, {
            "user_id": user_id,
            "user_name": room.users[user_id].name,
            "command": data.get("command", ""),
            "timestamp": datetime.now().isoformat(),
        })
    
    async def _handle_typing(self, user_id: str, room_id: Optional[str], data: Dict):
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        if user_id in room.users:
            room.users[user_id].is_typing = data.get("is_typing", False)
            await self._broadcast_to_room(user_id, room_id, MessageType.TYPING, {
                "user_id": user_id,
                "is_typing": room.users[user_id].is_typing,
            }, exclude_sender=False)
    
    async def _handle_leave(self, user_id: str):
        await self._handle_disconnect(user_id)
    
    async def _handle_disconnect(self, user_id: str):
        room_id = self.user_rooms.get(user_id)
        
        if room_id and room_id in self.rooms:
            room = self.rooms[room_id]
            
            if user_id in room.users:
                user_name = room.users[user_id].name
                del room.users[user_id]
                
                await self._broadcast_to_room(None, room_id, MessageType.SYSTEM, {
                    "message": f"{user_name} left the room"
                })
                
                await self._broadcast_to_room(None, room_id, MessageType.USER_LIST, {
                    "users": [
                        {
                            "id": u.id,
                            "name": u.name,
                            "color": u.color,
                        }
                        for u in room.users.values()
                    ]
                })
            
            if len(room.users) == 0:
                del self.rooms[room_id]
        
        if user_id in self.user_rooms:
            del self.user_rooms[user_id]
        
        if user_id in self.connections:
            del self.connections[user_id]
    
    async def _send(self, user_id: str, msg_type: MessageType, data: Any):
        if user_id in self.connections:
            try:
                await self.connections[user_id].send(json.dumps({
                    "type": msg_type.value,
                    "data": data,
                }))
            except Exception:
                pass
    
    async def _broadcast_to_room(self, sender_id: Optional[str], room_id: Optional[str], msg_type: MessageType, data: Any, exclude_sender: bool = True):
        if not room_id or room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        message = json.dumps({
            "type": msg_type.value,
            "data": data,
        })
        
        for uid, user in room.users.items():
            if exclude_sender and uid == sender_id:
                continue
            
            if uid in self.connections:
                try:
                    await self.connections[uid].send(message)
                except Exception:
                    pass
    
    async def _send_error(self, user_id: str, error: str):
        await self._send(user_id, MessageType.ERROR, {"message": error})
    
    def create_room(self, name: str, owner: str, settings: Dict[str, Any] = None) -> str:
        room_id = str(uuid.uuid4())[:8]
        
        room = CollaborationRoom(
            id=room_id,
            name=name,
            owner=owner,
            settings=settings or {},
        )
        
        self.rooms[room_id] = room
        return room_id
    
    def delete_room(self, room_id: str, user_id: str) -> bool:
        if room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        if room.owner != user_id:
            return False
        
        del self.rooms[room_id]
        return True
    
    def list_rooms(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": r.id,
                "name": r.name,
                "owner": r.owner,
                "user_count": len(r.users),
                "created_at": r.created_at.isoformat(),
            }
            for r in self.rooms.values()
        ]
    
    def get_room(self, room_id: str) -> Optional[CollaborationRoom]:
        return self.rooms.get(room_id)


class CollaborationClient:
    def __init__(self, server_url: str = "ws://localhost:8766"):
        self.server_url = server_url
        self.websocket = None
        self.user_id = None
        self.room_id = None
        self.handlers: Dict[MessageType, List[Callable]] = {
            mt: [] for mt in MessageType
        }
    
    async def connect(self, room_id: str, name: str):
        self.websocket = await websockets.connect(self.server_url)
        
        await self.send(MessageType.JOIN, {
            "room_id": room_id,
            "name": name,
        })
        
        self.room_id = room_id
    
    async def disconnect(self):
        if self.websocket:
            await self.send(MessageType.LEAVE, {})
            await self.websocket.close()
    
    async def send(self, msg_type: MessageType, data: Any):
        if self.websocket:
            await self.websocket.send(json.dumps({
                "type": msg_type.value,
                "data": data,
                "room_id": self.room_id,
            }))
    
    async def chat(self, message: str):
        await self.send(MessageType.CHAT, {"message": message})
    
    async def move_cursor(self, position: Dict[str, int]):
        await self.send(MessageType.CURSOR, {"position": position})
    
    async def update_selection(self, selection: Dict[str, Any]):
        await self.send(MessageType.SELECTION, {"selection": selection})
    
    async def edit_file(self, file_path: str, old_content: str, new_content: str):
        await self.send(MessageType.EDIT, {
            "file_path": file_path,
            "old_content": old_content,
            "new_content": new_content,
        })
    
    async def run_command(self, command: str):
        await self.send(MessageType.COMMAND, {"command": command})
    
    async def set_typing(self, is_typing: bool):
        await self.send(MessageType.TYPING, {"is_typing": is_typing})
    
    def on(self, msg_type: MessageType, handler: Callable):
        self.handlers[msg_type].append(handler)
    
    async def listen(self):
        async for message in self.websocket:
            msg_data = json.loads(message)
            msg_type = MessageType(msg_data.get("type", "system"))
            data = msg_data.get("data", {})
            
            for handler in self.handlers.get(msg_type, []):
                await handler(data)
