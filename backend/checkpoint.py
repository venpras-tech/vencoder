import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from contextvars import ContextVar

_active_session_id: ContextVar[Optional[str]] = ContextVar('active_session_id', default=None)

@dataclass
class Checkpoint:
    id: str
    file_path: str
    snapshot_path: str
    created_at: str
    session_id: str
    action: str
    original_hash: str
    restored: bool = False

class CheckpointManager:
    def __init__(self, workspace_root: Path, max_checkpoints: int = 50):
        self.workspace_root = Path(workspace_root)
        self.checkpoint_dir = self.workspace_root / ".vencoder" / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self.index_file = self.checkpoint_dir / "index.json"
        self._checkpoints: Dict[str, List[Checkpoint]] = {}
        self._load_index()
        
    def _load_index(self):
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text())
                for session_id, checkpoints_data in data.items():
                    self._checkpoints[session_id] = [
                        Checkpoint(**cp) for cp in checkpoints_data
                    ]
            except json.JSONDecodeError:
                self._checkpoints = {}
                
    def _save_index(self):
        data = {
            session_id: [asdict(cp) for cp in checkpoints]
            for session_id, checkpoints in self._checkpoints.items()
        }
        self.index_file.write_text(json.dumps(data, indent=2))
        
    def _get_session_id(self) -> str:
        return _active_session_id.get() or "default"
    
    def set_session_id(self, session_id: str):
        _active_session_id.set(session_id)
        
    def _generate_id(self, file_path: Path) -> str:
        timestamp = datetime.now().isoformat()
        content = f"{file_path}:{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _compute_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()
    
    def create_checkpoint(self, file_path: Path, action: str = "edit") -> Optional[Checkpoint]:
        if not file_path.exists():
            return None
            
        try:
            file_path = Path(file_path).resolve()
            relative_path = file_path.relative_to(self.workspace_root)
            session_id = self._get_session_id()
            checkpoint_id = self._generate_id(file_path)
            
            original_content = file_path.read_text(encoding='utf-8', errors='replace')
            original_hash = self._compute_hash(original_content)
            
            snapshot_filename = f"{relative_path.as_posix().replace('/', '_')}_{checkpoint_id}.snap"
            snapshot_path = self.checkpoint_dir / snapshot_filename
            snapshot_path.write_text(original_content, encoding='utf-8')
            
            checkpoint = Checkpoint(
                id=checkpoint_id,
                file_path=str(relative_path),
                snapshot_path=str(snapshot_path.relative_to(self.checkpoint_dir)),
                created_at=datetime.now().isoformat(),
                session_id=session_id,
                action=action,
                original_hash=original_hash
            )
            
            if session_id not in self._checkpoints:
                self._checkpoints[session_id] = []
            self._checkpoints[session_id].append(checkpoint)
            
            self._prune_old_checkpoints(session_id)
            self._save_index()
            
            return checkpoint
        except Exception as e:
            return None
            
    def _prune_old_checkpoints(self, session_id: str):
        if session_id not in self._checkpoints:
            return
            
        checkpoints = self._checkpoints[session_id]
        if len(checkpoints) > self.max_checkpoints:
            to_remove = checkpoints[:-self.max_checkpoints]
            for cp in to_remove:
                snapshot_file = self.checkpoint_dir / cp.snapshot_path
                if snapshot_file.exists():
                    snapshot_file.unlink()
            self._checkpoints[session_id] = checkpoints[-self.max_checkpoints:]
            
    def undo_to_checkpoint(self, checkpoint_id: str) -> bool:
        session_id = self._get_session_id()
        
        if session_id not in self._checkpoints:
            return False
            
        checkpoint = None
        for cp in self._checkpoints[session_id]:
            if cp.id == checkpoint_id:
                checkpoint = cp
                break
                
        if not checkpoint:
            return False
            
        try:
            snapshot_file = self.checkpoint_dir / checkpoint.snapshot_path
            if not snapshot_file.exists():
                return False
                
            target_file = self.workspace_root / checkpoint.file_path
            target_file.write_text(snapshot_file.read_text(encoding='utf-8'), encoding='utf-8')
            
            checkpoint.restored = True
            self._save_index()
            return True
        except Exception:
            return False
            
    def undo_last(self) -> bool:
        session_id = self._get_session_id()
        
        if session_id not in self._checkpoints:
            return False
            
        checkpoints = self._checkpoints[session_id]
        for cp in reversed(checkpoints):
            if not cp.restored:
                return self.undo_to_checkpoint(cp.id)
        return False
        
    def list_checkpoints(self, file_path: Optional[Path] = None) -> List[Checkpoint]:
        session_id = self._get_session_id()
        
        if session_id not in self._checkpoints:
            return []
            
        checkpoints = self._checkpoints[session_id]
        
        if file_path:
            file_path = Path(file_path)
            try:
                relative = file_path.relative_to(self.workspace_root)
                return [cp for cp in checkpoints if cp.file_path == str(relative)]
            except ValueError:
                return []
                
        return sorted(checkpoints, key=lambda x: x.created_at, reverse=True)
        
    def get_checkpoint_info(self, checkpoint_id: str) -> Optional[Checkpoint]:
        session_id = self._get_session_id()
        
        if session_id not in self._checkpoints:
            return None
            
        for cp in self._checkpoints[session_id]:
            if cp.id == checkpoint_id:
                return cp
        return None
        
    def get_checkpoint_diff(self, checkpoint_id: str) -> Optional[Dict]:
        checkpoint = self.get_checkpoint_info(checkpoint_id)
        if not checkpoint:
            return None
            
        try:
            snapshot_file = self.checkpoint_dir / checkpoint.snapshot_path
            current_file = self.workspace_root / checkpoint.file_path
            
            original = snapshot_file.read_text(encoding='utf-8', errors='replace')
            current = current_file.read_text(encoding='utf-8', errors='replace') if current_file.exists() else ""
            
            return {
                "checkpoint_id": checkpoint_id,
                "file_path": checkpoint.file_path,
                "original": original,
                "current": current,
                "created_at": checkpoint.created_at,
                "action": checkpoint.action
            }
        except Exception:
            return None
            
    def clear_session_checkpoints(self, session_id: Optional[str] = None):
        if session_id is None:
            session_id = self._get_session_id()
            
        if session_id not in self._checkpoints:
            return
            
        for cp in self._checkpoints[session_id]:
            snapshot_file = self.checkpoint_dir / cp.snapshot_path
            if snapshot_file.exists():
                snapshot_file.unlink()
                
        del self._checkpoints[session_id]
        self._save_index()
        
    def get_stats(self) -> Dict:
        total_checkpoints = sum(len(cps) for cps in self._checkpoints.values())
        total_size = sum(
            f.stat().st_size 
            for f in self.checkpoint_dir.glob("*.snap")
        )
        
        return {
            "total_checkpoints": total_checkpoints,
            "disk_size_bytes": total_size,
            "sessions": len(self._checkpoints),
            "max_per_session": self.max_checkpoints
        }
