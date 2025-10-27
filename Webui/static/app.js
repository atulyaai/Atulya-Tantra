/**
 * Atulya Tantra AGI - JARVIS Interface JavaScript
 * Modern, responsive chat interface with real-time capabilities
 */

class JARVISInterface {
    constructor() {
        this.currentConversationId = null;
        this.isStreaming = false;
        this.isVoiceEnabled = false;
        this.recognition = null;
        this.websocket = null;
        this.settings = this.loadSettings();
        
        this.initializeElements();
        this.attachEventListeners();
        this.initializeVoiceRecognition();
        this.loadConversations();
        this.applyTheme();
        
        // Auto-save settings
        setInterval(() => this.saveSettings(), 30000);
    }
    
    initializeElements() {
        // Main elements
        this.sidebar = document.getElementById('sidebar');
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.conversationsList = document.getElementById('conversationsList');
        this.chatTitle = document.getElementById('chatTitle');
        this.chatStatus = document.getElementById('chatStatus');
        
        // Action buttons
        this.voiceBtn = document.getElementById('voiceBtn');
        this.attachBtn = document.getElementById('attachBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.fileInput = document.getElementById('fileInput');
        
        // Settings modal
        this.settingsModal = document.getElementById('settingsModal');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.closeSettingsBtn = document.getElementById('closeSettingsBtn');
        this.saveSettingsBtn = document.getElementById('saveSettingsBtn');
        this.cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
        
        // Loading overlay
        this.loadingOverlay = document.getElementById('loadingOverlay');
        
        // Toast container
        this.toastContainer = document.getElementById('toastContainer');
        
        // Character count
        this.charCount = document.getElementById('charCount');
        this.modelInfo = document.getElementById('modelInfo');
    }
    
    attachEventListeners() {
        // Message input
        this.messageInput.addEventListener('input', () => this.handleInputChange());
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Send button
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // New chat
        this.newChatBtn.addEventListener('click', () => this.startNewChat());
        
        // Action buttons
        this.voiceBtn.addEventListener('click', () => this.toggleVoiceInput());
        this.attachBtn.addEventListener('click', () => this.fileInput.click());
        this.clearBtn.addEventListener('click', () => this.clearChat());
        
        // File input
        this.fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        
        // Settings
        this.settingsBtn.addEventListener('click', () => this.showSettings());
        this.closeSettingsBtn.addEventListener('click', () => this.hideSettings());
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        this.cancelSettingsBtn.addEventListener('click', () => this.hideSettings());
        
        // Quick actions
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-action-btn')) {
                this.messageInput.value = e.target.dataset.message;
                this.handleInputChange();
                this.sendMessage();
            }
        });
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        
        // Settings change handlers
        document.getElementById('temperature').addEventListener('input', (e) => {
            document.getElementById('temperatureValue').textContent = e.target.value;
        });
        
        // Theme change
        document.getElementById('theme').addEventListener('change', (e) => {
            this.applyTheme(e.target.value);
        });
    }
    
    initializeVoiceRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';
            
            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                this.messageInput.value = transcript;
                this.handleInputChange();
            };
            
            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.showToast('Voice recognition error: ' + event.error, 'error');
            };
            
            this.recognition.onend = () => {
                this.isVoiceEnabled = false;
                this.updateVoiceButton();
            };
        }
    }
    
    handleInputChange() {
        const message = this.messageInput.value.trim();
        this.sendBtn.disabled = !message || this.isStreaming;
        this.charCount.textContent = `${this.messageInput.value.length}/10000`;
        
        // Auto-resize textarea
        this.autoResizeTextarea();
    }
    
    handleKeyDown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!this.sendBtn.disabled) {
                this.sendMessage();
            }
        }
    }
    
    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isStreaming) return;
        
        // Clear input
        this.messageInput.value = '';
        this.handleInputChange();
        
        // Hide welcome message
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
        
        // Add user message
        this.addMessage('user', message);
        
        // Show loading
        this.showLoading();
        this.isStreaming = true;
        this.updateStatus('Processing...', 'processing');
        
        try {
            // Send message to API
            const response = await this.sendToAPI(message);
            
            if (response.stream) {
                // Handle streaming response
                await this.handleStreamingResponse(response);
            } else {
                // Handle regular response
                this.addMessage('ai', response.response);
            }
            
            // Update conversation list
            this.loadConversations();
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('ai', 'Sorry, I encountered an error processing your request. Please try again.');
            this.showToast('Error: ' + error.message, 'error');
        } finally {
            this.hideLoading();
            this.isStreaming = false;
            this.updateStatus('Ready', 'ready');
        }
    }
    
    async sendToAPI(message) {
        const response = await fetch('/api/chat/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.getAuthToken()}`
            },
            body: JSON.stringify({
                message: message,
                conversation_id: this.currentConversationId,
                user_id: this.getCurrentUserId(),
                stream: this.settings.streamingEnabled
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    async handleStreamingResponse(response) {
        // This would handle Server-Sent Events
        // For now, we'll simulate streaming
        const aiMessage = this.addMessage('ai', '');
        const words = response.response.split(' ');
        
        for (let i = 0; i < words.length; i++) {
            await new Promise(resolve => setTimeout(resolve, 50));
            aiMessage.querySelector('.message-bubble').textContent += words[i] + ' ';
            this.scrollToBottom();
        }
    }
    
    addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        if (role === 'ai') {
            // Process markdown and code
            bubble.innerHTML = this.processMarkdown(content);
        } else {
            bubble.textContent = content;
        }
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        
        contentDiv.appendChild(bubble);
        contentDiv.appendChild(time);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageDiv;
    }
    
    processMarkdown(content) {
        // Basic markdown processing
        let processed = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/\n/g, '<br>');
        
        return processed;
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    startNewChat() {
        this.currentConversationId = null;
        this.chatTitle.textContent = 'New Conversation';
        this.chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🤖</div>
                <h3>Welcome to JARVIS</h3>
                <p>I'm your AI assistant powered by Atulya Tantra AGI. How can I help you today?</p>
                <div class="quick-actions">
                    <button class="quick-action-btn" data-message="What can you help me with?">
                        What can you help me with?
                    </button>
                    <button class="quick-action-btn" data-message="Tell me about your capabilities">
                        Tell me about your capabilities
                    </button>
                    <button class="quick-action-btn" data-message="Help me with a coding problem">
                        Help me with coding
                    </button>
                    <button class="quick-action-btn" data-message="Analyze some data for me">
                        Analyze data
                    </button>
                </div>
            </div>
        `;
    }
    
    clearChat() {
        if (confirm('Are you sure you want to clear this chat?')) {
            this.startNewChat();
        }
    }
    
    toggleVoiceInput() {
        if (!this.recognition) {
            this.showToast('Voice recognition not supported in this browser', 'warning');
            return;
        }
        
        if (this.isVoiceEnabled) {
            this.recognition.stop();
        } else {
            this.recognition.start();
            this.isVoiceEnabled = true;
            this.updateVoiceButton();
            this.showToast('Listening...', 'info');
        }
    }
    
    updateVoiceButton() {
        this.voiceBtn.style.backgroundColor = this.isVoiceEnabled ? '#ef4444' : '';
        this.voiceBtn.style.color = this.isVoiceEnabled ? '#ffffff' : '';
    }
    
    handleFileUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;
        
        // Process files
        files.forEach(file => {
            this.showToast(`Processing file: ${file.name}`, 'info');
            // Here you would upload the file to the API
        });
        
        // Clear file input
        event.target.value = '';
    }
    
    async loadConversations() {
        try {
            const response = await fetch('/api/chat/conversations', {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });
            
            if (response.ok) {
                const conversations = await response.json();
                this.renderConversations(conversations);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }
    
    renderConversations(conversations) {
        this.conversationsList.innerHTML = '';
        
        conversations.forEach(conv => {
            const convDiv = document.createElement('div');
            convDiv.className = 'conversation-item';
            convDiv.innerHTML = `
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-preview">${conv.preview || 'No messages yet'}</div>
                <div class="conversation-time">${new Date(conv.updated_at).toLocaleDateString()}</div>
            `;
            
            convDiv.addEventListener('click', () => {
                this.loadConversation(conv.conversation_id);
            });
            
            this.conversationsList.appendChild(convDiv);
        });
    }
    
    async loadConversation(conversationId) {
        try {
            const response = await fetch(`/api/chat/history/${conversationId}`, {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });
            
            if (response.ok) {
                const history = await response.json();
                this.currentConversationId = conversationId;
                this.chatTitle.textContent = history.title || 'Conversation';
                this.renderConversationHistory(history.messages);
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
            this.showToast('Error loading conversation', 'error');
        }
    }
    
    renderConversationHistory(messages) {
        this.chatMessages.innerHTML = '';
        
        messages.forEach(msg => {
            this.addMessage(msg.role, msg.content);
        });
        
        this.scrollToBottom();
    }
    
    showSettings() {
        this.settingsModal.classList.add('show');
        this.populateSettings();
    }
    
    hideSettings() {
        this.settingsModal.classList.remove('show');
    }
    
    populateSettings() {
        document.getElementById('aiProvider').value = this.settings.aiProvider || 'ollama';
        document.getElementById('model').value = this.settings.model || 'gemma2:2b';
        document.getElementById('temperature').value = this.settings.temperature || 0.7;
        document.getElementById('temperatureValue').textContent = this.settings.temperature || 0.7;
        document.getElementById('voiceEnabled').checked = this.settings.voiceEnabled !== false;
        document.getElementById('theme').value = this.settings.theme || 'auto';
    }
    
    saveSettings() {
        this.settings = {
            aiProvider: document.getElementById('aiProvider').value,
            model: document.getElementById('model').value,
            temperature: parseFloat(document.getElementById('temperature').value),
            voiceEnabled: document.getElementById('voiceEnabled').checked,
            theme: document.getElementById('theme').value,
            streamingEnabled: true
        };
        
        localStorage.setItem('jarvis-settings', JSON.stringify(this.settings));
        this.applyTheme();
        this.hideSettings();
        this.showToast('Settings saved', 'success');
    }
    
    loadSettings() {
        const saved = localStorage.getItem('jarvis-settings');
        return saved ? JSON.parse(saved) : {
            aiProvider: 'ollama',
            model: 'gemma2:2b',
            temperature: 0.7,
            voiceEnabled: true,
            theme: 'auto',
            streamingEnabled: true
        };
    }
    
    applyTheme(theme = null) {
        const selectedTheme = theme || this.settings.theme;
        
        if (selectedTheme === 'auto') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', selectedTheme);
        }
    }
    
    updateStatus(text, type) {
        const statusText = this.chatStatus.querySelector('span');
        const indicator = this.chatStatus.querySelector('.status-indicator');
        
        statusText.textContent = text;
        
        indicator.className = 'status-indicator';
        if (type === 'processing') {
            indicator.style.backgroundColor = '#f59e0b';
        } else if (type === 'error') {
            indicator.style.backgroundColor = '#ef4444';
        } else {
            indicator.style.backgroundColor = '#10b981';
        }
    }
    
    showLoading() {
        this.loadingOverlay.classList.add('show');
    }
    
    hideLoading() {
        this.loadingOverlay.classList.remove('show');
    }
    
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        this.toastContainer.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    getAuthToken() {
        // In a real app, this would get the token from localStorage or cookies
        return 'demo-token';
    }
    
    getCurrentUserId() {
        // In a real app, this would get the user ID from the auth system
        return 'demo-user';
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.jarvis = new JARVISInterface();
});

// Handle theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (window.jarvis && window.jarvis.settings.theme === 'auto') {
        window.jarvis.applyTheme();
    }
});

// Handle visibility change (pause/resume when tab is hidden/visible)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Pause any ongoing operations
        console.log('App paused');
    } else {
        // Resume operations
        console.log('App resumed');
    }
});

// Handle online/offline status
window.addEventListener('online', () => {
    window.jarvis?.showToast('Connection restored', 'success');
});

window.addEventListener('offline', () => {
    window.jarvis?.showToast('Connection lost', 'warning');
});

// Service Worker registration (for PWA capabilities)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}