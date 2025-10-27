/**
 * Atulya Tantra AGI - Web Interface JavaScript
 * Main application logic for the web interface
 */

class TantraAGI {
    constructor() {
        this.apiBase = '/api';
        this.wsUrl = `ws://${window.location.host}/ws`;
        this.socket = null;
        this.isConnected = false;
        this.currentSession = null;
        this.messageHistory = [];
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupWebSocket();
        this.loadUserPreferences();
        this.renderInterface();
    }
    
    setupEventListeners() {
        // Send message button
        document.getElementById('sendButton').addEventListener('click', () => {
            this.sendMessage();
        });
        
        // Enter key in message input
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Clear chat button
        document.getElementById('clearChat').addEventListener('click', () => {
            this.clearChat();
        });
        
        // Settings button
        document.getElementById('settingsButton').addEventListener('click', () => {
            this.showSettings();
        });
        
        // Voice input button
        document.getElementById('voiceInput').addEventListener('click', () => {
            this.toggleVoiceInput();
        });
        
        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => {
            this.toggleTheme();
        });
    }
    
    setupWebSocket() {
        try {
            this.socket = new WebSocket(this.wsUrl);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.updateConnectionStatus('connected');
            };
            
            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
                
                // Attempt to reconnect after 3 seconds
                setTimeout(() => {
                    this.setupWebSocket();
                }, 3000);
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error');
            };
            
        } catch (error) {
            console.error('Error setting up WebSocket:', error);
            this.updateConnectionStatus('error');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'message':
                this.displayMessage(data.message, 'assistant');
                break;
            case 'status':
                this.updateSystemStatus(data.status);
                break;
            case 'error':
                this.displayError(data.error);
                break;
            case 'typing':
                this.showTypingIndicator();
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput.value.trim();
        
        if (!message) return;
        
        // Clear input
        messageInput.value = '';
        
        // Display user message
        this.displayMessage(message, 'user');
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            // Send via WebSocket if available
            if (this.isConnected && this.socket) {
                this.socket.send(JSON.stringify({
                    type: 'message',
                    message: message,
                    session_id: this.currentSession
                }));
            } else {
                // Fallback to HTTP API
                await this.sendMessageViaAPI(message);
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.displayError('Failed to send message. Please try again.');
        }
    }
    
    async sendMessageViaAPI(message) {
        try {
            const response = await fetch(`${this.apiBase}/chat/message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.currentSession
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.displayMessage(data.message, 'assistant');
            
        } catch (error) {
            console.error('Error sending message via API:', error);
            this.displayError('Failed to send message. Please try again.');
        }
    }
    
    displayMessage(message, sender) {
        const chatContainer = document.getElementById('chatContainer');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        // Create message content
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Add sender info
        const senderInfo = document.createElement('div');
        senderInfo.className = 'sender-info';
        senderInfo.textContent = sender === 'user' ? 'You' : 'JARVIS';
        messageContent.appendChild(senderInfo);
        
        // Add message text
        const messageText = document.createElement('div');
        messageText.className = 'message-text';
        messageText.innerHTML = this.formatMessage(message);
        messageContent.appendChild(messageText);
        
        // Add timestamp
        const timestamp = document.createElement('div');
        timestamp.className = 'timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();
        messageContent.appendChild(timestamp);
        
        messageDiv.appendChild(messageContent);
        chatContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // Store in history
        this.messageHistory.push({
            message: message,
            sender: sender,
            timestamp: new Date().toISOString()
        });
    }
    
    formatMessage(message) {
        // Basic markdown-like formatting
        return message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
    
    showTypingIndicator() {
        const chatContainer = document.getElementById('chatContainer');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant typing';
        typingDiv.id = 'typingIndicator';
        
        typingDiv.innerHTML = `
            <div class="message-content">
                <div class="sender-info">JARVIS</div>
                <div class="message-text">
                    <div class="typing-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        `;
        
        chatContainer.appendChild(typingDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    displayError(error) {
        const chatContainer = document.getElementById('chatContainer');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error';
        
        errorDiv.innerHTML = `
            <div class="message-content">
                <div class="sender-info">System</div>
                <div class="message-text">${error}</div>
            </div>
        `;
        
        chatContainer.appendChild(errorDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    clearChat() {
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.innerHTML = '';
        this.messageHistory = [];
        
        // Send clear request to server
        if (this.isConnected && this.socket) {
            this.socket.send(JSON.stringify({
                type: 'clear_chat',
                session_id: this.currentSession
            }));
        }
    }
    
    updateConnectionStatus(status) {
        const statusIndicator = document.getElementById('connectionStatus');
        const statusText = document.getElementById('statusText');
        
        statusIndicator.className = `status-indicator ${status}`;
        
        switch (status) {
            case 'connected':
                statusText.textContent = 'Connected';
                break;
            case 'disconnected':
                statusText.textContent = 'Disconnected';
                break;
            case 'error':
                statusText.textContent = 'Connection Error';
                break;
            default:
                statusText.textContent = 'Unknown';
        }
    }
    
    updateSystemStatus(status) {
        // Update system status indicators
        const cpuUsage = document.getElementById('cpuUsage');
        const memoryUsage = document.getElementById('memoryUsage');
        const diskUsage = document.getElementById('diskUsage');
        
        if (cpuUsage && status.cpu_usage !== undefined) {
            cpuUsage.textContent = `${status.cpu_usage.toFixed(1)}%`;
            cpuUsage.className = status.cpu_usage > 80 ? 'warning' : 'normal';
        }
        
        if (memoryUsage && status.memory_usage !== undefined) {
            memoryUsage.textContent = `${status.memory_usage.toFixed(1)}%`;
            memoryUsage.className = status.memory_usage > 85 ? 'warning' : 'normal';
        }
        
        if (diskUsage && status.disk_usage !== undefined) {
            diskUsage.textContent = `${status.disk_usage.toFixed(1)}%`;
            diskUsage.className = status.disk_usage > 90 ? 'warning' : 'normal';
        }
    }
    
    toggleVoiceInput() {
        const voiceButton = document.getElementById('voiceInput');
        
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            this.displayError('Voice input is not supported in this browser.');
            return;
        }
        
        if (voiceButton.classList.contains('recording')) {
            this.stopVoiceInput();
        } else {
            this.startVoiceInput();
        }
    }
    
    startVoiceInput() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        
        recognition.onstart = () => {
            const voiceButton = document.getElementById('voiceInput');
            voiceButton.classList.add('recording');
            voiceButton.textContent = '🎤 Listening...';
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('messageInput').value = transcript;
        };
        
        recognition.onend = () => {
            const voiceButton = document.getElementById('voiceInput');
            voiceButton.classList.remove('recording');
            voiceButton.textContent = '🎤';
        };
        
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            const voiceButton = document.getElementById('voiceInput');
            voiceButton.classList.remove('recording');
            voiceButton.textContent = '🎤';
        };
        
        recognition.start();
    }
    
    stopVoiceInput() {
        // Voice input will stop automatically
    }
    
    toggleTheme() {
        const body = document.body;
        const currentTheme = body.classList.contains('dark-theme') ? 'dark' : 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        body.classList.toggle('dark-theme');
        
        // Save preference
        localStorage.setItem('theme', newTheme);
        
        // Update theme button
        const themeButton = document.getElementById('themeToggle');
        themeButton.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    }
    
    showSettings() {
        // Create settings modal
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Settings</h2>
                    <span class="close">&times;</span>
                </div>
                <div class="modal-body">
                    <div class="setting">
                        <label for="themeSelect">Theme:</label>
                        <select id="themeSelect">
                            <option value="light">Light</option>
                            <option value="dark">Dark</option>
                        </select>
                    </div>
                    <div class="setting">
                        <label for="fontSize">Font Size:</label>
                        <input type="range" id="fontSize" min="12" max="18" value="14">
                    </div>
                    <div class="setting">
                        <label for="autoScroll">Auto Scroll:</label>
                        <input type="checkbox" id="autoScroll" checked>
                    </div>
                </div>
                <div class="modal-footer">
                    <button id="saveSettings">Save</button>
                    <button id="cancelSettings">Cancel</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Setup event listeners
        modal.querySelector('.close').addEventListener('click', () => {
            modal.remove();
        });
        
        modal.querySelector('#cancelSettings').addEventListener('click', () => {
            modal.remove();
        });
        
        modal.querySelector('#saveSettings').addEventListener('click', () => {
            this.saveSettings();
            modal.remove();
        });
        
        // Load current settings
        this.loadSettings(modal);
    }
    
    loadSettings(modal) {
        const theme = localStorage.getItem('theme') || 'light';
        const fontSize = localStorage.getItem('fontSize') || '14';
        const autoScroll = localStorage.getItem('autoScroll') !== 'false';
        
        modal.querySelector('#themeSelect').value = theme;
        modal.querySelector('#fontSize').value = fontSize;
        modal.querySelector('#autoScroll').checked = autoScroll;
    }
    
    saveSettings() {
        const theme = document.querySelector('#themeSelect').value;
        const fontSize = document.querySelector('#fontSize').value;
        const autoScroll = document.querySelector('#autoScroll').checked;
        
        localStorage.setItem('theme', theme);
        localStorage.setItem('fontSize', fontSize);
        localStorage.setItem('autoScroll', autoScroll);
        
        // Apply settings
        document.body.className = theme === 'dark' ? 'dark-theme' : '';
        document.documentElement.style.fontSize = fontSize + 'px';
    }
    
    loadUserPreferences() {
        const theme = localStorage.getItem('theme') || 'light';
        const fontSize = localStorage.getItem('fontSize') || '14';
        const autoScroll = localStorage.getItem('autoScroll') !== 'false';
        
        // Apply theme
        if (theme === 'dark') {
            document.body.classList.add('dark-theme');
        }
        
        // Apply font size
        document.documentElement.style.fontSize = fontSize + 'px';
        
        // Update theme button
        const themeButton = document.getElementById('themeToggle');
        if (themeButton) {
            themeButton.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
    }
    
    renderInterface() {
        // Initialize interface elements
        this.currentSession = this.generateSessionId();
        
        // Display welcome message
        this.displayMessage(
            "Hello! I'm JARVIS, your AI assistant. How can I help you today?",
            'assistant'
        );
    }
    
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9);
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.tantraAGI = new TantraAGI();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Page is hidden, pause non-essential operations
        console.log('Page hidden, pausing operations');
    } else {
        // Page is visible, resume operations
        console.log('Page visible, resuming operations');
    }
});

// Handle beforeunload
window.addEventListener('beforeunload', () => {
    if (window.tantraAGI && window.tantraAGI.socket) {
        window.tantraAGI.socket.close();
    }
});