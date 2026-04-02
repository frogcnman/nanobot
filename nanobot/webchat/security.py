"""Enhanced security features for webchat"""
import os
import json
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import request, jsonify, g
from typing import Optional, Dict, List
import threading

# Security config file
SECURITY_CONFIG_FILE = Path.home() / ".nanobot" / "webchat-security.json"

# Rate limiting storage (in memory)
_rate_limit_storage: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()

# Audit log file
AUDIT_LOG_FILE = Path.home() / ".nanobot" / "webchat-audit.log"

# IP whitelist (None = disabled, empty list = allow all)
_ip_whitelist: Optional[List[str]] = None


def load_security_config() -> dict:
    """Load security configuration"""
    if SECURITY_CONFIG_FILE.exists():
        try:
            with open(SECURITY_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_security_config(config: dict):
    """Save security configuration"""
    SECURITY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SECURITY_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_client_ip() -> str:
    """Get client IP address (handle proxy headers)"""
    # Check X-Forwarded-For header (for reverse proxy)
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    return request.remote_addr or 'unknown'


def audit_log(action: str, username: str = None, details: dict = None, level: str = 'INFO'):
    """Write audit log entry"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'action': action,
        'username': username or getattr(g, 'webchat_username', 'anonymous'),
        'ip': get_client_ip(),
        'details': details or {},
        'user_agent': request.headers.get('User-Agent', '')[:200],
        'path': request.path,
        'method': request.method,
    }
    
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ============ IP Whitelist ============

def load_ip_whitelist() -> Optional[List[str]]:
    """Load IP whitelist from config"""
    global _ip_whitelist
    config = load_security_config()
    whitelist = config.get('ip_whitelist')
    
    if whitelist is None:
        _ip_whitelist = None  # Disabled
    else:
        _ip_whitelist = [ip.strip() for ip in whitelist if ip.strip()]
    
    return _ip_whitelist


def is_ip_allowed(ip: str) -> bool:
    """Check if IP is allowed"""
    if _ip_whitelist is None:
        return True  # Whitelist disabled, allow all
    
    if not _ip_whitelist:
        return True  # Empty whitelist = allow all
    
    # Check exact match
    if ip in _ip_whitelist:
        return True
    
    # Check CIDR notation (simple prefix match for now)
    for allowed in _ip_whitelist:
        if '/' in allowed:
            # CIDR notation - simplified check
            prefix = allowed.split('/')[0]
            if ip.startswith(prefix.rsplit('.', 1)[0]):
                return True
        if allowed.endswith('*') and ip.startswith(allowed[:-1]):
            return True
    
    return False


def set_ip_whitelist(ips: List[str] = None):
    """Set IP whitelist (None to disable)"""
    global _ip_whitelist
    _ip_whitelist = ips
    config = load_security_config()
    config['ip_whitelist'] = ips
    save_security_config(config)


# ============ Rate Limiting ============

def check_rate_limit(key: str, max_requests: int = 60, window_seconds: int = 60) -> tuple:
    """
    Check rate limit for a key
    Returns: (allowed: bool, remaining: int, reset_time: int)
    """
    now = time.time()
    window_start = now - window_seconds
    
    with _rate_limit_lock:
        # Get or create request list
        if key not in _rate_limit_storage:
            _rate_limit_storage[key] = []
        
        # Clean old requests
        _rate_limit_storage[key] = [t for t in _rate_limit_storage[key] if t > window_start]
        
        current_count = len(_rate_limit_storage[key])
        remaining = max(0, max_requests - current_count)
        reset_time = int(window_start + window_seconds)
        
        if current_count >= max_requests:
            return False, 0, reset_time
        
        # Add current request
        _rate_limit_storage[key].append(now)
        return True, remaining - 1, reset_time


def rate_limit(max_requests: int = 60, window_seconds: int = 60, key_func=None):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Generate key
            if key_func:
                key = key_func()
            else:
                ip = get_client_ip()
                username = getattr(g, 'webchat_username', 'anonymous')
                key = f"rate:{ip}:{username}"
            
            allowed, remaining, reset_time = check_rate_limit(key, max_requests, window_seconds)
            
            if not allowed:
                audit_log('rate_limit_exceeded', level='WARNING', details={'key': key})
                return jsonify({
                    'error': '请求过于频繁，请稍后再试',
                    'retry_after': reset_time - int(time.time())
                }), 429
            
            # Add rate limit headers
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(reset_time)
            
            return response
        return decorated
    return decorator


# ============ API Token ============

def generate_api_token(username: str, expires_days: int = 30) -> str:
    """Generate a new API token for a user"""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    config = load_security_config()
    if 'api_tokens' not in config:
        config['api_tokens'] = {}
    
    config['api_tokens'][token_hash] = {
        'username': username,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(days=expires_days)).isoformat(),
        'last_used': None,
    }
    
    save_security_config(config)
    audit_log('api_token_created', username=username)
    
    return token


def validate_api_token(token: str) -> Optional[str]:
    """Validate API token, return username if valid"""
    if not token:
        return None
    
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    config = load_security_config()
    tokens = config.get('api_tokens', {})
    
    if token_hash not in tokens:
        return None
    
    token_info = tokens[token_hash]
    
    # Check expiration
    expires_at = datetime.fromisoformat(token_info['expires_at'])
    if datetime.now() > expires_at:
        return None
    
    # Update last used
    token_info['last_used'] = datetime.now().isoformat()
    save_security_config(config)
    
    return token_info['username']


def revoke_api_token(token: str) -> bool:
    """Revoke an API token"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    config = load_security_config()
    tokens = config.get('api_tokens', {})
    
    if token_hash in tokens:
        username = tokens[token_hash]['username']
        del tokens[token_hash]
        save_security_config(config)
        audit_log('api_token_revoked', username=username)
        return True
    
    return False


def list_api_tokens(username: str = None) -> List[dict]:
    """List API tokens (optionally filtered by username)"""
    config = load_security_config()
    tokens = config.get('api_tokens', {})
    
    result = []
    for token_hash, info in tokens.items():
        if username and info['username'] != username:
            continue
        
        result.append({
            'token_hash': token_hash[:16] + '...',
            'username': info['username'],
            'created_at': info['created_at'],
            'expires_at': info['expires_at'],
            'last_used': info['last_used'],
        })
    
    return result


# ============ Dangerous Operation Confirmation ============

_pending_operations: Dict[str, dict] = {}
_pending_lock = threading.Lock()


def request_operation_confirmation(operation: str, details: dict, username: str, expires_seconds: int = 60) -> str:
    """
    Request confirmation for a dangerous operation
    Returns a confirmation ID
    """
    confirm_id = secrets.token_urlsafe(16)
    
    with _pending_lock:
        _pending_operations[confirm_id] = {
            'operation': operation,
            'details': details,
            'username': username,
            'created_at': time.time(),
            'expires_at': time.time() + expires_seconds,
        }
    
    audit_log('operation_confirmation_requested', username=username, 
              details={'operation': operation, 'confirm_id': confirm_id})
    
    return confirm_id


def confirm_operation(confirm_id: str, username: str) -> tuple:
    """
    Confirm a pending operation
    Returns: (success: bool, operation: dict or error_message: str)
    """
    with _pending_lock:
        if confirm_id not in _pending_operations:
            return False, "确认ID无效或已过期"
        
        op = _pending_operations[confirm_id]
        
        # Check expiration
        if time.time() > op['expires_at']:
            del _pending_operations[confirm_id]
            return False, "确认已过期，请重新操作"
        
        # Check username
        if op['username'] != username:
            audit_log('operation_confirmation_failed', username=username,
                     details={'confirm_id': confirm_id, 'reason': 'wrong_user'}, level='WARNING')
            return False, "无权确认此操作"
        
        # Remove and return
        del _pending_operations[confirm_id]
        
        audit_log('operation_confirmed', username=username,
                 details={'operation': op['operation']})
        
        return True, op


# ============ Security Decorators ============

def ip_whitelist_required(f):
    """Decorator to check IP whitelist"""
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = get_client_ip()
        
        if not is_ip_allowed(ip):
            audit_log('ip_blocked', level='WARNING', details={'ip': ip})
            return jsonify({'error': '访问被拒绝'}), 403
        
        return f(*args, **kwargs)
    return decorated


def agent_mode_authorized(f):
    """Decorator to check if user is authorized for agent mode (dangerous tools)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Import here to avoid circular import
        from .app import validate_session
        from flask import request
        
        # First check if already set by login_required
        username = getattr(request, 'webchat_username', None)
        
        # If not, check session cookie
        if not username:
            session_token = request.cookies.get('webchat_session')
            username = validate_session(session_token)
            
            # Also check API token
            if not username:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header[7:]
                    username = validate_api_token(token)
        
        if not username:
            return jsonify({'error': '请先登录'}), 401
        
        # Set username for later use
        request.webchat_username = username
        g.webchat_username = username
        
        # Check if user has agent mode permission
        config = load_security_config()
        agent_users = config.get('agent_mode_users', [])
        
        # If list is empty, all authenticated users can use agent mode
        if agent_users and username not in agent_users:
            audit_log('agent_mode_denied', username=username, level='WARNING')
            return jsonify({'error': '您没有使用Agent模式的权限'}), 403
        
        return f(*args, **kwargs)
    return decorated


def dangerous_operation(f):
    """Decorator for dangerous operations that need confirmation"""
    @wraps(f)
    def decorated(*args, **kwargs):
        data = request.json or {}
        confirm_id = data.get('confirm_id')
        username = getattr(request, 'webchat_username', 'anonymous')
        
        # If no confirm_id, return confirmation request
        if not confirm_id:
            operation = f.__name__
            details = {k: v for k, v in data.items() if k not in ['confirm_id']}
            new_confirm_id = request_operation_confirmation(operation, details, username)
            
            return jsonify({
                'requires_confirmation': True,
                'confirm_id': new_confirm_id,
                'message': '此操作需要确认，请再次执行并附带 confirm_id',
                'operation': operation,
            })
        
        # Validate confirmation
        success, result = confirm_operation(confirm_id, username)
        if not success:
            return jsonify({'error': result}), 400
        
        # Proceed with operation
        return f(*args, **kwargs)
    return decorated


# Initialize on module load
load_ip_whitelist()
