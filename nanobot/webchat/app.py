#!/usr/bin/env python3
"""
Web Chat System for nanobot
A web-based chat interface accessible via LAN on port 8081
With persistent chat history support
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import requests
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import threading
import uuid

# Get the directory where this module is located
MODULE_DIR = Path(__file__).parent

# Add parent directory to path for imports
sys.path.insert(0, str(MODULE_DIR.parent.parent))

app = Flask(__name__, 
            template_folder=str(MODULE_DIR / 'templates'),
            static_folder=str(MODULE_DIR / 'static'))
CORS(app)

# Data directory for persistent storage (use ~/.nanobot/webchat-data for persistence)
DATA_DIR = Path.home() / ".nanobot" / "webchat-data"
SESSIONS_DIR = DATA_DIR / "sessions"
DATA_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

# Lock for thread-safe file operations
file_lock = threading.Lock()

# Provider configurations
PROVIDER_CONFIGS = {
    'zhipu': {
        'api_base': 'https://open.bigmodel.cn/api/paas/v4',
        'default_model': 'glm-4-flash'
    },
    'openai': {
        'api_base': 'https://api.openai.com/v1',
        'default_model': 'gpt-4o-mini'
    },
    'deepseek': {
        'api_base': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat'
    },
    'anthropic': {
        'api_base': 'https://api.anthropic.com/v1',
        'default_model': 'claude-3-haiku-20240307'
    },
    'moonshot': {
        'api_base': 'https://api.moonshot.cn/v1',
        'default_model': 'moonshot-v1-8k'
    },
    'groq': {
        'api_base': 'https://api.groq.com/openai/v1',
        'default_model': 'llama-3.1-8b-instant'
    },
    'openrouter': {
        'api_base': 'https://openrouter.ai/api/v1',
        'default_model': 'openai/gpt-4o-mini'
    },
    'siliconflow': {
        'api_base': 'https://api.siliconflow.cn/v1',
        'default_model': 'Qwen/Qwen2.5-7B-Instruct'
    },
    'custom': {
        'api_base': None,
        'default_model': 'default'
    }
}

def load_nanobot_config():
    """Load configuration from nanobot config file"""
    config_path = Path.home() / ".nanobot" / "config.json"
    
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    return {}

def get_provider_config():
    """Get the first available provider with API key"""
    config = load_nanobot_config()
    providers = config.get('providers', {})
    
    # Priority order for providers
    priority = ['zhipu', 'openai', 'deepseek', 'anthropic', 'moonshot', 'groq', 'openrouter', 'siliconflow', 'custom']
    
    for provider in priority:
        if provider in providers:
            provider_cfg = providers[provider]
            api_key = provider_cfg.get('apiKey', '')
            api_base = provider_cfg.get('apiBase')
            
            if api_key:
                # Get default API base if not specified
                if not api_base and provider in PROVIDER_CONFIGS:
                    api_base = PROVIDER_CONFIGS[provider]['api_base']
                
                default_model = PROVIDER_CONFIGS.get(provider, {}).get('default_model', 'default')
                
                return {
                    'provider': provider,
                    'api_key': api_key,
                    'api_base': api_base,
                    'default_model': default_model
                }
    
    return None

# Initialize configuration
provider_config = get_provider_config()

# Configuration - can be overridden via environment variables
if provider_config:
    API_BASE_URL = os.environ.get('API_BASE_URL', provider_config['api_base'])
    API_KEY = os.environ.get('API_KEY', provider_config['api_key'])
    DEFAULT_MODEL = provider_config['default_model']
    PROVIDER_NAME = provider_config['provider']
else:
    API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.openai.com/v1')
    API_KEY = os.environ.get('API_KEY', '')
    DEFAULT_MODEL = 'gpt-4o-mini'
    PROVIDER_NAME = 'none'

# Get model from config or use default
config = load_nanobot_config()
agent_defaults = config.get('agents', {}).get('defaults', {})
MODEL = os.environ.get('MODEL', agent_defaults.get('model', DEFAULT_MODEL))

SYSTEM_PROMPT = os.environ.get('SYSTEM_PROMPT', '你是 nanobot 🐈，一个友好、乐于助人的AI助手。请用简洁、准确的方式回答问题。')

# ============ Persistence Functions ============

def get_session_file(session_id):
    """Get the file path for a session"""
    return SESSIONS_DIR / f"{session_id}.json"

def save_session(session_id, history, title=None):
    """Save session to file"""
    session_file = get_session_file(session_id)
    
    # Get existing session data to preserve title
    existing_data = {}
    if session_file.exists():
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except:
            pass
    
    # Generate title from first user message if not provided
    if not title and len(history) > 1:
        for msg in history[1:]:  # Skip system prompt
            if msg.get('role') == 'user':
                title = msg.get('content', '')[:50]
                if len(msg.get('content', '')) > 50:
                    title += '...'
                break
    
    session_data = {
        'id': session_id,
        'title': title or existing_data.get('title', '新对话'),
        'created_at': existing_data.get('created_at', datetime.now().isoformat()),
        'updated_at': datetime.now().isoformat(),
        'messages': history
    }
    
    with file_lock:
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

def load_session(session_id):
    """Load session from file"""
    session_file = get_session_file(session_id)
    
    if session_file.exists():
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('messages', [{"role": "system", "content": SYSTEM_PROMPT}])
        except:
            pass
    
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def get_session_metadata(session_id):
    """Get session metadata without messages"""
    session_file = get_session_file(session_id)
    
    if session_file.exists():
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'id': data.get('id', session_id),
                    'title': data.get('title', '新对话'),
                    'created_at': data.get('created_at'),
                    'updated_at': data.get('updated_at'),
                    'message_count': len(data.get('messages', [])) - 1  # Exclude system prompt
                }
        except:
            pass
    
    return None

def list_sessions():
    """List all sessions sorted by update time"""
    sessions = []
    
    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sessions.append({
                    'id': data.get('id', session_file.stem),
                    'title': data.get('title', '新对话'),
                    'created_at': data.get('created_at'),
                    'updated_at': data.get('updated_at'),
                    'message_count': len(data.get('messages', [])) - 1
                })
        except:
            continue
    
    # Sort by updated_at descending
    sessions.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
    return sessions

def delete_session(session_id):
    """Delete a session file"""
    session_file = get_session_file(session_id)
    
    with file_lock:
        if session_file.exists():
            session_file.unlink()
            return True
    return False

def get_session_history(session_id):
    """Get or create conversation history for a session"""
    return load_session(session_id)

# ============ API Routes ============

@app.route('/')
def index():
    """Serve the main chat page"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    stream = data.get('stream', False)
    
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400
    
    # Get conversation history
    history = get_session_history(session_id)
    
    # Add user message to history
    history.append({"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()})
    
    if stream:
        # Streaming response
        def generate():
            response = call_ai_api(history, stream=True)
            if isinstance(response, str):
                yield f"data: {json.dumps({'error': response})}\n\n"
                return
            
            assistant_message = ""
            try:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data_str)
                                if chunk.get('choices') and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        assistant_message += content
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
                
                # Add assistant message to history
                history.append({"role": "assistant", "content": assistant_message, "timestamp": datetime.now().isoformat()})
                
                # Save session
                save_session(session_id, history)
                
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    else:
        # Non-streaming response
        result = call_ai_api(history, stream=False)
        
        if isinstance(result, str):
            return jsonify({'error': result}), 500
        
        try:
            assistant_message = result['choices'][0]['message']['content']
            history.append({"role": "assistant", "content": assistant_message, "timestamp": datetime.now().isoformat()})
            
            # Save session
            save_session(session_id, history)
            
            return jsonify({
                'response': assistant_message,
                'timestamp': datetime.now().isoformat()
            })
        except (KeyError, IndexError) as e:
            return jsonify({'error': f'解析响应失败: {str(e)}'}), 500

@app.route('/api/sessions', methods=['GET'])
def api_list_sessions():
    """List all chat sessions"""
    sessions = list_sessions()
    return jsonify({'sessions': sessions})

@app.route('/api/sessions', methods=['POST'])
def api_create_session():
    """Create a new session"""
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Create empty session
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_session(session_id, history, title='新对话')
    
    return jsonify({
        'session_id': session_id,
        'title': '新对话'
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get conversation history for a session"""
    session_id = request.args.get('session_id', 'default')
    history = get_session_history(session_id)
    
    # Get session metadata
    metadata = get_session_metadata(session_id)
    
    return jsonify({
        'history': history[1:],  # Exclude system prompt
        'session': metadata
    })

@app.route('/api/clear', methods=['POST'])
def clear_history():
    """Clear conversation history for a session"""
    data = request.json or {}
    session_id = data.get('session_id', 'default')
    
    # Reset history
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    save_session(session_id, history, title='新对话')
    
    return jsonify({'success': True, 'message': '对话历史已清除'})

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    """Delete a session"""
    if delete_session(session_id):
        return jsonify({'success': True, 'message': '会话已删除'})
    return jsonify({'error': '会话不存在'}), 404

@app.route('/api/sessions/<session_id>/rename', methods=['POST'])
def api_rename_session(session_id):
    """Rename a session"""
    data = request.json or {}
    new_title = data.get('title', '')
    
    if not new_title:
        return jsonify({'error': '标题不能为空'}), 400
    
    history = load_session(session_id)
    save_session(session_id, history, title=new_title)
    
    return jsonify({'success': True, 'title': new_title})

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration (without sensitive data)"""
    return jsonify({
        'model': MODEL,
        'provider': PROVIDER_NAME,
        'api_configured': bool(API_KEY),
        'system_prompt': SYSTEM_PROMPT[:100] + '...' if len(SYSTEM_PROMPT) > 100 else SYSTEM_PROMPT
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

def call_ai_api(messages, stream=False):
    """Call the AI API with the conversation history"""
    if not API_KEY:
        return "错误：未配置 API Key。请检查 ~/.nanobot/config.json 中的 providers 配置"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Clean messages for API (remove timestamp)
    clean_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
    
    payload = {
        "model": MODEL,
        "messages": clean_messages,
        "stream": stream,
        "temperature": 0.7,
        "max_tokens": 4096
    }
    
    try:
        if stream:
            response = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=60
            )
            return response
        else:
            response = requests.post(
                f"{API_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
    except requests.exceptions.RequestException as e:
        return f"API 调用错误: {str(e)}"

def main():
    """Entry point for nanobot-webchat command"""
    # Ensure data directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 50)
    print("nanobot Web Chat System")
    print("=" * 50)
    print(f"Provider: {PROVIDER_NAME}")
    print(f"Model: {MODEL}")
    print(f"API configured: {'Yes' if API_KEY else 'No'}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Access URL: http://0.0.0.0:8081")
    print("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=8081,
        debug=False,
        threaded=True
    )


if __name__ == '__main__':
    main()
