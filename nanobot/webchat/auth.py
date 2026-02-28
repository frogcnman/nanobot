"""
WebChat Authentication Module
Simple username/password authentication with secure password hashing
"""

import hashlib
import secrets
import json
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

# Auth config file
AUTH_CONFIG_FILE = Path.home() / ".nanobot" / "webchat-auth.json"
SESSION_TIMEOUT_HOURS = 24

def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    """Hash password with salt using SHA-256"""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return key.hex(), salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password against hash"""
    key, _ = hash_password(password, salt)
    return key == hashed

def load_auth_config() -> dict:
    """Load authentication configuration"""
    if AUTH_CONFIG_FILE.exists():
        with open(AUTH_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "sessions": {}}

def save_auth_config(config: dict):
    """Save authentication configuration"""
    AUTH_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Restrict file permissions (owner only)
    with open(AUTH_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    AUTH_CONFIG_FILE.chmod(0o600)

def create_session(username: str) -> str:
    """Create a new session and return session token"""
    config = load_auth_config()
    session_token = secrets.token_urlsafe(32)
    config["sessions"][session_token] = {
        "username": username,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=SESSION_TIMEOUT_HOURS)).isoformat()
    }
    save_auth_config(config)
    return session_token

def validate_session(session_token: str) -> Optional[str]:
    """Validate session and return username if valid, None otherwise"""
    if not session_token:
        return None
    
    config = load_auth_config()
    session = config.get("sessions", {}).get(session_token)
    
    if not session:
        return None
    
    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.now() > expires_at:
        # Clean up expired session
        del config["sessions"][session_token]
        save_auth_config(config)
        return None
    
    return session.get("username")

def destroy_session(session_token: str):
    """Destroy a session"""
    config = load_auth_config()
    if session_token in config.get("sessions", {}):
        del config["sessions"][session_token]
        save_auth_config(config)

def cleanup_expired_sessions():
    """Remove expired sessions"""
    config = load_auth_config()
    sessions = config.get("sessions", {})
    now = datetime.now()
    
    expired = [token for token, sess in sessions.items() 
               if datetime.fromisoformat(sess["expires_at"]) < now]
    
    for token in expired:
        del sessions[token]
    
    if expired:
        save_auth_config(config)

def add_user(username: str, password: str) -> bool:
    """Add a new user"""
    if not username or not password:
        return False
    
    config = load_auth_config()
    
    if username in config.get("users", {}):
        return False  # User already exists
    
    hashed, salt = hash_password(password)
    
    if "users" not in config:
        config["users"] = {}
    
    config["users"][username] = {
        "hash": hashed,
        "salt": salt,
        "created_at": datetime.now().isoformat()
    }
    
    save_auth_config(config)
    return True

def verify_user(username: str, password: str) -> bool:
    """Verify username and password"""
    config = load_auth_config()
    user = config.get("users", {}).get(username)
    
    if not user:
        return False
    
    return verify_password(password, user["hash"], user["salt"])

def list_users() -> list:
    """List all usernames"""
    config = load_auth_config()
    return list(config.get("users", {}).keys())

def remove_user(username: str) -> bool:
    """Remove a user"""
    config = load_auth_config()
    if username in config.get("users", {}):
        del config["users"][username]
        save_auth_config(config)
        return True
    return False

def is_auth_enabled() -> bool:
    """Check if authentication is enabled"""
    config = load_auth_config()
    return len(config.get("users", {})) > 0

def get_default_credentials() -> Tuple[str, str]:
    """Get default credentials for first-time setup"""
    # Generate default credentials
    default_user = "admin"
    default_pass = secrets.token_hex(4)  # 8 character random password
    return default_user, default_pass
