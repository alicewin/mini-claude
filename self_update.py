#!/usr/bin/env python3
"""
Self-Update Mechanism for Mini-Claude
Allows Mini-Claude to safely update its own helper scripts with approval and rollback
"""

import os
import sys
import json
import shutil
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess
import tempfile

class UpdateManager:
    """Manages self-updates with safety guardrails"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "backups"
        self.update_log = self.project_root / "update_log.json"
        self.pending_updates = self.project_root / "pending_updates.json"
        
        # Files that can be self-updated
        self.updatable_files = {
            "prompt_templates": self.project_root / "prompt_templates",
            "task_queue.py": self.project_root / "task_queue.py",
            "config.json": self.project_root / "config.json"
        }
        
        # Core files that require human approval
        self.protected_files = {
            "mini_claude.py",
            "self_update.py"
        }
        
        self._ensure_directories()
        self._setup_logging()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        self.backup_dir.mkdir(exist_ok=True)
    
    def _setup_logging(self):
        """Setup update logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.project_root / "self_update.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        if not file_path.exists():
            return ""
        
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def _create_backup(self, file_path: Path) -> Path:
        """Create backup of a file before updating"""
        if not file_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        self.logger.info(f"Created backup: {backup_path}")
        
        return backup_path
    
    def _log_update(self, file_path: str, action: str, status: str, details: Dict[str, Any]):
        """Log update action"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "file_path": file_path,
            "action": action,
            "status": status,
            "details": details
        }
        
        # Load existing log
        update_log = []
        if self.update_log.exists():
            with open(self.update_log, 'r') as f:
                update_log = json.load(f)
        
        # Add new entry
        update_log.append(log_entry)
        
        # Keep only last 100 entries
        update_log = update_log[-100:]
        
        # Save log
        with open(self.update_log, 'w') as f:
            json.dump(update_log, f, indent=2)
    
    def propose_update(self, file_path: str, new_content: str, reason: str, 
                      requires_approval: bool = True) -> str:
        """Propose an update to a file"""
        file_path = Path(file_path)
        
        # Security check - only allow updates to approved files
        if file_path.name in self.protected_files:
            if not requires_approval:
                raise PermissionError(f"File {file_path.name} requires human approval")
        
        # Generate update ID
        update_id = hashlib.md5(f"{file_path}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        
        # Calculate current file hash
        current_hash = self._calculate_file_hash(file_path)
        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        
        # Prepare update proposal
        proposal = {
            "id": update_id,
            "file_path": str(file_path),
            "reason": reason,
            "current_hash": current_hash,
            "new_hash": new_hash,
            "new_content": new_content,
            "requires_approval": requires_approval,
            "proposed_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Save pending update
        pending_updates = self._load_pending_updates()
        pending_updates[update_id] = proposal
        self._save_pending_updates(pending_updates)
        
        self.logger.info(f"Proposed update {update_id} for {file_path}: {reason}")
        
        if not requires_approval:
            # Auto-apply for non-protected files
            return self.apply_update(update_id)
        
        return update_id
    
    def list_pending_updates(self) -> List[Dict[str, Any]]:
        """List all pending updates"""
        pending_updates = self._load_pending_updates()
        return [
            {
                "id": update_id,
                "file_path": update["file_path"],
                "reason": update["reason"],
                "proposed_at": update["proposed_at"],
                "requires_approval": update["requires_approval"]
            }
            for update_id, update in pending_updates.items()
            if update["status"] == "pending"
        ]
    
    def approve_update(self, update_id: str) -> str:
        """Approve a pending update"""
        pending_updates = self._load_pending_updates()
        
        if update_id not in pending_updates:
            raise ValueError(f"Update {update_id} not found")
        
        update = pending_updates[update_id]
        update["approved_at"] = datetime.now().isoformat()
        update["status"] = "approved"
        
        self._save_pending_updates(pending_updates)
        self.logger.info(f"Approved update {update_id}")
        
        return self.apply_update(update_id)
    
    def reject_update(self, update_id: str, reason: str = "") -> bool:
        """Reject a pending update"""
        pending_updates = self._load_pending_updates()
        
        if update_id not in pending_updates:
            raise ValueError(f"Update {update_id} not found")
        
        update = pending_updates[update_id]
        update["status"] = "rejected"
        update["rejected_at"] = datetime.now().isoformat()
        update["rejection_reason"] = reason
        
        self._save_pending_updates(pending_updates)
        
        self._log_update(
            update["file_path"],
            "reject",
            "success",
            {"update_id": update_id, "reason": reason}
        )
        
        self.logger.info(f"Rejected update {update_id}: {reason}")
        return True
    
    def apply_update(self, update_id: str) -> str:
        """Apply an approved update"""
        pending_updates = self._load_pending_updates()
        
        if update_id not in pending_updates:
            raise ValueError(f"Update {update_id} not found")
        
        update = pending_updates[update_id]
        file_path = Path(update["file_path"])
        
        # Verify file hasn't changed since proposal
        current_hash = self._calculate_file_hash(file_path)
        if current_hash and current_hash != update["current_hash"]:
            raise ValueError(f"File {file_path} has been modified since update proposal")
        
        try:
            # Create backup
            backup_path = self._create_backup(file_path)
            
            # Apply update
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(update["new_content"])
            
            # Verify update
            new_hash = self._calculate_file_hash(file_path)
            if new_hash != update["new_hash"]:
                raise ValueError("Update verification failed - hash mismatch")
            
            # Mark as applied
            update["status"] = "applied"
            update["applied_at"] = datetime.now().isoformat()
            update["backup_path"] = str(backup_path) if backup_path else None
            
            self._save_pending_updates(pending_updates)
            
            self._log_update(
                str(file_path),
                "apply",
                "success",
                {
                    "update_id": update_id,
                    "backup_path": str(backup_path) if backup_path else None
                }
            )
            
            self.logger.info(f"Applied update {update_id} to {file_path}")
            return f"Update {update_id} applied successfully"
            
        except Exception as e:
            # Rollback on error
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
                self.logger.info(f"Rolled back {file_path} due to error")
            
            self._log_update(
                str(file_path),
                "apply",
                "failed",
                {"update_id": update_id, "error": str(e)}
            )
            
            raise Exception(f"Update failed: {e}")
    
    def rollback_update(self, update_id: str) -> str:
        """Rollback a previously applied update"""
        pending_updates = self._load_pending_updates()
        
        if update_id not in pending_updates:
            raise ValueError(f"Update {update_id} not found")
        
        update = pending_updates[update_id]
        
        if update["status"] != "applied":
            raise ValueError(f"Update {update_id} was not applied")
        
        backup_path = update.get("backup_path")
        if not backup_path or not Path(backup_path).exists():
            raise ValueError(f"Backup not found for update {update_id}")
        
        file_path = Path(update["file_path"])
        
        try:
            # Restore from backup
            shutil.copy2(backup_path, file_path)
            
            # Mark as rolled back
            update["status"] = "rolled_back"
            update["rolled_back_at"] = datetime.now().isoformat()
            
            self._save_pending_updates(pending_updates)
            
            self._log_update(
                str(file_path),
                "rollback",
                "success",
                {"update_id": update_id}
            )
            
            self.logger.info(f"Rolled back update {update_id}")
            return f"Update {update_id} rolled back successfully"
            
        except Exception as e:
            self._log_update(
                str(file_path),
                "rollback",
                "failed",
                {"update_id": update_id, "error": str(e)}
            )
            raise Exception(f"Rollback failed: {e}")
    
    def _load_pending_updates(self) -> Dict[str, Any]:
        """Load pending updates from file"""
        if not self.pending_updates.exists():
            return {}
        
        with open(self.pending_updates, 'r') as f:
            return json.load(f)
    
    def _save_pending_updates(self, updates: Dict[str, Any]):
        """Save pending updates to file"""
        with open(self.pending_updates, 'w') as f:
            json.dump(updates, f, indent=2)
    
    def cleanup_old_backups(self, days: int = 30):
        """Clean up old backup files"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for backup_file in self.backup_dir.glob("*.backup"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                self.logger.info(f"Cleaned up old backup: {backup_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Mini-Claude Self-Update Manager")
    parser.add_argument("--list", action="store_true", help="List pending updates")
    parser.add_argument("--approve", help="Approve update by ID")
    parser.add_argument("--reject", help="Reject update by ID")
    parser.add_argument("--rollback", help="Rollback update by ID")
    parser.add_argument("--cleanup", type=int, help="Cleanup backups older than N days")
    
    args = parser.parse_args()
    
    update_manager = UpdateManager()
    
    if args.list:
        updates = update_manager.list_pending_updates()
        if updates:
            print("Pending updates:")
            for update in updates:
                print(f"  {update['id']}: {update['file_path']} - {update['reason']}")
        else:
            print("No pending updates")
    
    elif args.approve:
        try:
            result = update_manager.approve_update(args.approve)
            print(result)
        except Exception as e:
            print(f"Error: {e}")
    
    elif args.reject:
        reason = input("Rejection reason (optional): ")
        try:
            update_manager.reject_update(args.reject, reason)
            print(f"Update {args.reject} rejected")
        except Exception as e:
            print(f"Error: {e}")
    
    elif args.rollback:
        try:
            result = update_manager.rollback_update(args.rollback)
            print(result)
        except Exception as e:
            print(f"Error: {e}")
    
    elif args.cleanup:
        update_manager.cleanup_old_backups(args.cleanup)
        print(f"Cleaned up backups older than {args.cleanup} days")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()