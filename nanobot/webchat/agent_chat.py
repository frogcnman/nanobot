"""Agent-powered chat for webchat - provides full tool capabilities (same as CLI)"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request, Response, session

logger = logging.getLogger(__name__)
agent_bp = Blueprint('agent', __name__)

# Import security module
from .security import audit_log, agent_mode_authorized, rate_limit

# Avoid circular import - import app functions at runtime
# from .app import save_session, load_session, SYSTEM_PROMPT

# Global agent loop instance
_agent_loop = None


def get_agent_loop():
    """Get or create the global agent loop with full tools (same as CLI)"""
    global _agent_loop
    
    if _agent_loop is not None:
        return _agent_loop
    
    import os
    os.environ['PYTHONPATH'] = '/tmp/nanobot_project'
    
    # Import here to avoid circular imports
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus import MessageBus
    from nanobot.config.loader import load_config
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.registry import find_by_name
    from nanobot.agent.tools.registry import ToolRegistry
    from nanobot.agent.tools.filesystem import ReadFileTool, ListDirTool, WriteFileTool, EditFileTool
    from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
    from nanobot.agent.tools.shell import ExecTool
    from nanobot.agent.tools.message import MessageTool
    from nanobot.agent.tools.spawn import SpawnTool
    
    # Load config
    config_path = Path.home() / ".nanobot" / "config.json"
    config = load_config(config_path)
    
    # Get model and provider from config
    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    
    # Create provider
    if provider_name == "custom":
        from nanobot.providers.custom_provider import CustomProvider
        provider = CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )
    else:
        spec = find_by_name(provider_name)
        provider = LiteLLMProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(model),
            default_model=model,
            extra_headers=p.extra_headers if p else None,
            provider_name=provider_name,
        )
    
    # Create bus and workspace
    bus = MessageBus()
    workspace = Path.home() / ".nanobot" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Create agent with full tools (no restrict_to_workspace)
    _agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        max_iterations=40,
        temperature=0.1,
        restrict_to_workspace=False,  # Full access like CLI
    )
    
    # Re-register tools with full permissions (allowed_dir=None)
    _agent_loop.tools = ToolRegistry()
    
    # Filesystem tools - full access (no restrict_to_workspace)
    _agent_loop.tools.register(ListDirTool(workspace=workspace, allowed_dir=None))
    _agent_loop.tools.register(ReadFileTool(workspace=workspace, allowed_dir=None))
    _agent_loop.tools.register(WriteFileTool(workspace=workspace, allowed_dir=None))
    _agent_loop.tools.register(EditFileTool(workspace=workspace, allowed_dir=None))
    
    # Shell execution tool - full access
    _agent_loop.tools.register(ExecTool(
        working_dir=str(workspace),
        timeout=60,
        restrict_to_workspace=False,
    ))
    
    # Web tools
    _agent_loop.tools.register(WebSearchTool(api_key=None))
    _agent_loop.tools.register(WebFetchTool())
    
    # Message tool
    _agent_loop.tools.register(MessageTool(send_callback=lambda c, c2, m: None))
    
    # Spawn tool for subagents
    _agent_loop.tools.register(SpawnTool(manager=_agent_loop.subagents))
    
    logger.info(f"Agent loop created with full tools: {list(_agent_loop.tools._tools.keys())}")
    
    return _agent_loop


async def process_message_with_agent(message: str, session_id: str, webchat_history: list = None) -> dict:
    """Process a message through the agent loop with tools
    
    Args:
        message: User message
        session_id: Session identifier
        webchat_history: History from webchat session storage (optional)
    """
    from nanobot.agent.context import ContextBuilder
    
    loop = get_agent_loop()
    
    # Set tool context for this session
    loop._set_tool_context('webchat', session_id)
    
    # Get or create agent session (for agent's internal memory)
    agent_session = loop.sessions.get_or_create(f"webchat:{session_id}")
    
    # Build context and messages using webchat history if provided
    context = ContextBuilder(loop.workspace)
    
    if webchat_history:
        # Use webchat history, convert to agent format
        # Remove timestamps for agent processing
        clean_history = [{"role": m["role"], "content": m["content"]} for m in webchat_history]
        messages = context.build_messages(
            history=clean_history,
            current_message=message,
            channel='webchat',
            chat_id=session_id,
        )
    else:
        # Fallback to agent's internal session history
        history = agent_session.get_history(max_messages=loop.memory_window)
        messages = context.build_messages(
            history=history,
            current_message=message,
            channel='webchat',
            chat_id=session_id,
        )
    
    # Run the agent loop
    final_content, tools_used, all_msgs = await loop._run_agent_loop(messages)
    
    # Save to agent's internal session (for context continuity)
    loop._save_turn(agent_session, all_msgs, 1 + len(webchat_history or []))
    loop.sessions.save(agent_session)
    
    return {
        'content': final_content,
        'tools_used': tools_used,
        'messages': all_msgs,
    }


@agent_bp.route('/api/agent/chat', methods=['POST'])
@agent_mode_authorized
@rate_limit(max_requests=30, window_seconds=60)
def agent_chat():
    """Chat with agent that has tool capabilities (requires agent mode authorization)"""
    # Import at runtime to avoid circular import
    from .app import save_session, load_session
    
    data = request.json or {}
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400
    
    username = getattr(request, 'webchat_username', 'anonymous')
    audit_log('agent_chat', username=username, details={'session_id': session_id, 'message_length': len(user_message)})
    
    # Load existing history from webchat session storage
    history = load_session(session_id)
    
    # Add user message to history
    history.append({"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()})
    
    # Run async function in sync context
    result = asyncio.run(process_message_with_agent(user_message, session_id, history))
    
    # Save to webchat session storage
    if result.get('content'):
        history.append({"role": "assistant", "content": result['content'], "timestamp": datetime.now().isoformat()})
        save_session(session_id, history)
    
    return jsonify({
        'response': result['content'],
        'tools_used': result['tools_used'],
        'timestamp': datetime.now().isoformat()
    })


@agent_bp.route('/api/agent/capabilities', methods=['GET'])
def agent_capabilities():
    """Return agent capabilities (available tools)"""
    loop = get_agent_loop()
    tools = loop.tools.get_definitions()
    tool_names = [t['function']['name'] for t in tools]
    
    return jsonify({
        'tools': tool_names,
        'count': len(tool_names),
        'timestamp': datetime.now().isoformat()
    })
