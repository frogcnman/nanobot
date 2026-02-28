// nanobot Web Chat - Frontend Logic with Session Persistence

class ChatApp {
    constructor() {
        this.sessionId = null;
        this.isStreaming = false;
        this.currentAssistantMessage = null;
        this.sessions = [];
        
        this.initializeElements();
        this.bindEvents();
        this.checkAuth();
    }
    
    async checkAuth() {
        try {
            const response = await fetch('/api/auth/status');
            const data = await response.json();
            
            if (!data.authenticated) {
                // Not authenticated, redirect to login
                window.location.href = '/login';
                return;
            }
            
            // Authenticated, load app
            this.loadConfig();
            this.loadSessions();
        } catch (error) {
            console.error('Auth check failed:', error);
            window.location.href = '/login';
        }
    }
    
    async logout() {
        try {
            await fetch('/logout', { method: 'POST' });
            window.location.href = '/login';
        } catch (error) {
            console.error('Logout failed:', error);
        }
    }
    
    initializeElements() {
        // Main elements
        this.messagesContainer = document.getElementById('messages');
        this.welcomeMessage = document.getElementById('welcomeMessage');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.statusEl = document.getElementById('status');
        this.modelInfoEl = document.getElementById('modelInfo');
        this.settingsModal = document.getElementById('settingsModal');
        this.renameModal = document.getElementById('renameModal');
        this.chatContainer = document.getElementById('chatContainer');
        
        // Sidebar elements
        this.sidebar = document.getElementById('sidebar');
        this.sessionsList = document.getElementById('sessionsList');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.menuBtn = document.getElementById('menuBtn');
        this.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
        this.sessionTitleEl = document.getElementById('sessionTitle');
    }
    
    bindEvents() {
        // Send button
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // Enter to send, Shift+Enter for new line
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 150) + 'px';
        });
        
        // Clear conversation
        this.clearBtn.addEventListener('click', () => this.clearConversation());
        
        // New chat
        this.newChatBtn.addEventListener('click', () => this.createNewSession());
        
        // Sidebar toggle
        this.menuBtn.addEventListener('click', () => this.toggleSidebar(true));
        this.toggleSidebarBtn.addEventListener('click', () => this.toggleSidebar(false));
        
        // Settings modal
        this.settingsBtn.addEventListener('click', () => this.openSettings());
        document.getElementById('closeSettings').addEventListener('click', () => this.closeSettings());
        document.getElementById('cancelSettings').addEventListener('click', () => this.closeSettings());
        document.getElementById('saveSettings').addEventListener('click', () => this.saveSettings());
        
        // Rename modal
        document.getElementById('closeRename').addEventListener('click', () => this.closeRenameModal());
        document.getElementById('cancelRename').addEventListener('click', () => this.closeRenameModal());
        document.getElementById('confirmRename').addEventListener('click', () => this.confirmRename());
        
        // Close modals on outside click
        this.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.settingsModal) this.closeSettings();
        });
        this.renameModal.addEventListener('click', (e) => {
            if (e.target === this.renameModal) this.closeRenameModal();
        });
        
        // Create overlay for mobile
        this.createOverlay();
    }
    
    createOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.id = 'sidebarOverlay';
        document.body.appendChild(overlay);
        
        overlay.addEventListener('click', () => this.toggleSidebar(false));
    }
    
    toggleSidebar(open) {
        const overlay = document.getElementById('sidebarOverlay');
        
        if (open) {
            this.sidebar.classList.add('open');
            this.sidebar.classList.remove('collapsed');
            overlay.classList.add('active');
        } else {
            this.sidebar.classList.remove('open');
            this.sidebar.classList.add('collapsed');
            overlay.classList.remove('active');
        }
    }
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();
            
            if (config.model) {
                this.modelInfoEl.textContent = `Model: ${config.model}`;
            }
            
            if (!config.api_configured) {
                this.showStatus('请配置 API Key', 'error');
            }
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }
    
    async loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            const data = await response.json();
            this.sessions = data.sessions || [];
            this.renderSessionsList();
            
            // Load the most recent session or create new one
            if (this.sessions.length > 0) {
                await this.loadSession(this.sessions[0].id);
            } else {
                await this.createNewSession();
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            await this.createNewSession();
        }
    }
    
    renderSessionsList() {
        if (this.sessions.length === 0) {
            this.sessionsList.innerHTML = `
                <div class="empty-sessions">
                    暂无对话记录<br>点击上方按钮开始新对话
                </div>
            `;
            return;
        }
        
        this.sessionsList.innerHTML = this.sessions.map(session => `
            <div class="session-item ${session.id === this.sessionId ? 'active' : ''}" 
                 data-session-id="${session.id}">
                <div class="session-item-content" onclick="chatApp.loadSession('${session.id}')">
                    <div class="session-item-title">${this.escapeHtml(session.title)}</div>
                    <div class="session-item-meta">
                        ${session.message_count} 条消息 · ${this.formatTime(session.updated_at)}
                    </div>
                </div>
                <div class="session-item-actions">
                    <button class="session-action-btn" onclick="chatApp.openRenameModal('${session.id}', '${this.escapeHtml(session.title)}')" title="重命名">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="session-action-btn delete" onclick="chatApp.deleteSession('${session.id}')" title="删除">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    async createNewSession() {
        try {
            const response = await fetch('/api/sessions', { method: 'POST' });
            const data = await response.json();
            
            this.sessionId = data.session_id;
            this.messagesContainer.innerHTML = '';
            
            if (this.welcomeMessage) {
                this.welcomeMessage.style.display = 'flex';
            }
            
            this.sessionTitleEl.textContent = '';
            
            // Reload sessions list
            await this.loadSessions();
            
            // Close sidebar on mobile
            if (window.innerWidth <= 768) {
                this.toggleSidebar(false);
            }
        } catch (error) {
            console.error('Failed to create session:', error);
            this.showStatus('创建会话失败', 'error');
        }
    }
    
    async loadSession(sessionId) {
        if (this.isStreaming) return;
        
        this.sessionId = sessionId;
        
        try {
            const response = await fetch(`/api/history?session_id=${sessionId}`);
            const data = await response.json();
            
            // Update UI
            this.messagesContainer.innerHTML = '';
            
            const history = data.history || [];
            
            if (history.length === 0) {
                if (this.welcomeMessage) {
                    this.welcomeMessage.style.display = 'flex';
                }
            } else {
                if (this.welcomeMessage) {
                    this.welcomeMessage.style.display = 'none';
                }
                
                history.forEach(msg => {
                    if (msg.role !== 'system') {
                        this.addMessage(msg.role, msg.content);
                    }
                });
            }
            
            // Update session title
            if (data.session) {
                this.sessionTitleEl.textContent = data.session.title;
            }
            
            // Update active state in list
            this.renderSessionsList();
            
            // Close sidebar on mobile
            if (window.innerWidth <= 768) {
                this.toggleSidebar(false);
            }
            
        } catch (error) {
            console.error('Failed to load session:', error);
            this.showStatus('加载会话失败', 'error');
        }
    }
    
    async deleteSession(sessionId) {
        if (!confirm('确定要删除这个对话吗？')) return;
        
        try {
            await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
            
            // If deleted current session, load another or create new
            if (sessionId === this.sessionId) {
                this.sessions = this.sessions.filter(s => s.id !== sessionId);
                
                if (this.sessions.length > 0) {
                    await this.loadSession(this.sessions[0].id);
                } else {
                    await this.createNewSession();
                }
            } else {
                await this.loadSessions();
            }
        } catch (error) {
            console.error('Failed to delete session:', error);
            this.showStatus('删除失败', 'error');
        }
    }
    
    openRenameModal(sessionId, currentTitle) {
        this.renameSessionId = sessionId;
        document.getElementById('renameInput').value = currentTitle;
        this.renameModal.classList.add('active');
    }
    
    closeRenameModal() {
        this.renameModal.classList.remove('active');
        this.renameSessionId = null;
    }
    
    async confirmRename() {
        const newTitle = document.getElementById('renameInput').value.trim();
        if (!newTitle || !this.renameSessionId) return;
        
        try {
            await fetch(`/api/sessions/${this.renameSessionId}/rename`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle })
            });
            
            await this.loadSessions();
            this.closeRenameModal();
        } catch (error) {
            console.error('Failed to rename session:', error);
            this.showStatus('重命名失败', 'error');
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isStreaming) return;
        
        // Hide welcome message
        if (this.welcomeMessage) {
            this.welcomeMessage.style.display = 'none';
        }
        
        // Add user message to UI
        this.addMessage('user', message);
        
        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        
        // Disable send button
        this.sendBtn.disabled = true;
        this.isStreaming = true;
        
        // Show typing indicator
        const typingEl = this.addTypingIndicator();
        
        try {
            // Create assistant message container
            this.currentAssistantMessage = this.createMessageElement('assistant', '');
            this.messagesContainer.appendChild(this.currentAssistantMessage);
            
            // Remove typing indicator
            typingEl.remove();
            
            // Send message with streaming
            await this.streamMessage(message);
            
            // Reload sessions to update title and time
            await this.loadSessions();
            
        } catch (error) {
            typingEl.remove();
            this.showStatus(`错误: ${error.message}`, 'error');
            if (this.currentAssistantMessage) {
                this.currentAssistantMessage.querySelector('.message-content').textContent = '抱歉，发生了错误。请稍后重试。';
            }
        } finally {
            this.sendBtn.disabled = false;
            this.isStreaming = false;
            this.currentAssistantMessage = null;
        }
    }
    
    async streamMessage(message) {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: this.sessionId,
                stream: true
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        break;
                    }
                    
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.content) {
                            fullContent += parsed.content;
                            this.updateMessageContent(this.currentAssistantMessage, fullContent);
                            this.scrollToBottom();
                        } else if (parsed.error) {
                            throw new Error(parsed.error);
                        }
                    } catch (e) {
                        if (e.message !== 'Unexpected end of JSON input') {
                            console.error('Parse error:', e);
                        }
                    }
                }
            }
        }
        
        this.showStatus('在线', 'success');
    }
    
    addMessage(role, content) {
        const messageEl = this.createMessageElement(role, content);
        this.messagesContainer.appendChild(messageEl);
        this.scrollToBottom();
        return messageEl;
    }
    
    createMessageElement(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? '👤' : '🐈';
        
        const contentEl = document.createElement('div');
        contentEl.className = 'message-content';
        contentEl.innerHTML = this.formatContent(content);
        
        div.appendChild(avatar);
        div.appendChild(contentEl);
        
        return div;
    }
    
    updateMessageContent(messageEl, content) {
        const contentEl = messageEl.querySelector('.message-content');
        contentEl.innerHTML = this.formatContent(content);
    }
    
    formatContent(content) {
        // Simple markdown-like formatting
        let formatted = content
            // Escape HTML
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Code blocks
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Bold
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            // Line breaks
            .replace(/\n/g, '<br>');
        
        return formatted;
    }
    
    addTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.innerHTML = `
            <div class="message-avatar">🐈</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
        return div;
    }
    
    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }
    
    showStatus(message, type = '') {
        this.statusEl.textContent = message;
        this.statusEl.className = `status ${type}`;
    }
    
    async clearConversation() {
        if (!confirm('确定要清除当前对话记录吗？')) return;
        
        try {
            await fetch('/api/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
            
            // Clear UI
            this.messagesContainer.innerHTML = '';
            if (this.welcomeMessage) {
                this.welcomeMessage.style.display = 'flex';
            }
            
            this.sessionTitleEl.textContent = '';
            
            // Reload sessions
            await this.loadSessions();
            
            this.showStatus('对话已清除', 'success');
        } catch (error) {
            this.showStatus('清除失败', 'error');
        }
    }
    
    openSettings() {
        this.settingsModal.classList.add('active');
        
        // Load current settings from localStorage
        document.getElementById('apiBaseUrl').value = localStorage.getItem('apiBaseUrl') || '';
        document.getElementById('apiKey').value = localStorage.getItem('apiKey') || '';
        document.getElementById('modelName').value = localStorage.getItem('modelName') || '';
        document.getElementById('systemPrompt').value = localStorage.getItem('systemPrompt') || '';
    }
    
    closeSettings() {
        this.settingsModal.classList.remove('active');
    }
    
    async saveSettings() {
        const settings = {
            apiBaseUrl: document.getElementById('apiBaseUrl').value,
            apiKey: document.getElementById('apiKey').value,
            modelName: document.getElementById('modelName').value,
            systemPrompt: document.getElementById('systemPrompt').value
        };
        
        // Save to localStorage
        Object.entries(settings).forEach(([key, value]) => {
            if (value) {
                localStorage.setItem(key, value);
            }
        });
        
        // Send to server (would need additional endpoint)
        this.showStatus('设置已保存（需要重启服务生效）', 'success');
        this.closeSettings();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    formatTime(isoString) {
        if (!isoString) return '';
        
        const date = new Date(isoString);
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 minute
        if (diff < 60000) {
            return '刚刚';
        }
        
        // Less than 1 hour
        if (diff < 3600000) {
            return `${Math.floor(diff / 60000)} 分钟前`;
        }
        
        // Less than 24 hours
        if (diff < 86400000) {
            return `${Math.floor(diff / 3600000)} 小时前`;
        }
        
        // Less than 7 days
        if (diff < 604800000) {
            return `${Math.floor(diff / 86400000)} 天前`;
        }
        
        // Format as date
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});
