/**
 * VMS Chatbot JavaScript
 * Handles chatbot UI interactions and API communication
 */

class VMSChatbot {
    constructor() {
        this.container = document.getElementById('chatbot-container');
        this.overlay = document.getElementById('chatbot-overlay');
        this.messagesContainer = document.getElementById('chatbot-messages');
        this.input = document.getElementById('chatbot-input');
        this.sendBtn = document.getElementById('chatbot-send-btn');
        this.clearBtn = document.getElementById('chatbot-clear-btn');
        this.closeBtn = document.getElementById('chatbot-close-btn');
        
        this.isOpen = false;
        this.isLoading = false;
        this.csrfToken = this.getCSRFToken();
        
        this.init();
    }
    
    init() {
        // Sidebar toggle event listener - use document click delegation
        document.addEventListener('click', (e) => {
            const sidebarToggle = e.target.closest('#sidebar-chatbot-toggle');
            if (sidebarToggle) {
                e.preventDefault();
                this.toggleChat();
            }
        });
        
        // Send button and input
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Clear button
        if (this.clearBtn) {
            this.clearBtn.addEventListener('click', () => this.clearChat());
        }
        
        // Close button
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.toggleChat());
        }
        
        // Overlay click to close
        if (this.overlay) {
            this.overlay.addEventListener('click', () => this.toggleChat());
        }
        
        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.toggleChat();
            }
        });
        
        // Quick action buttons
        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                if (query) {
                    this.input.value = query;
                    this.sendMessage();
                }
            });
        });
        
        // Load chat history on open
        this.loadHistory();
    }
    
    getCSRFToken() {
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }
    
    toggleChat() {
        this.isOpen = !this.isOpen;
        this.container.classList.toggle('active', this.isOpen);
        
        // Toggle overlay
        if (this.overlay) {
            this.overlay.classList.toggle('active', this.isOpen);
        }
        
        // Prevent body scroll when chatbot is open
        document.body.style.overflow = this.isOpen ? 'hidden' : '';
        
        if (this.isOpen) {
            this.input.focus();
            this.scrollToBottom();
        }
    }
    
    async sendMessage() {
        const message = this.input.value.trim();
        if (!message || this.isLoading) return;
        
        // Add user message to chat
        this.addMessage(message, 'user');
        this.input.value = '';
        
        // Show typing indicator
        this.showTypingIndicator();
        this.isLoading = true;
        this.sendBtn.disabled = true;
        
        try {
            const response = await fetch('/chatbot/message/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ message })
            });
            
            const data = await response.json();
            
            this.hideTypingIndicator();
            
            if (data.success) {
                this.addBotResponse(data.response);
            } else {
                this.addMessage(data.error || 'Sorry, something went wrong.', 'bot', true);
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addMessage('Unable to connect to the server. Please try again.', 'bot', true);
            console.error('Chatbot error:', error);
        }
        
        this.isLoading = false;
        this.sendBtn.disabled = false;
    }
    
    addMessage(content, type, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${type}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        if (isError) bubble.style.background = '#fee2e2';
        
        // Parse content for line breaks
        bubble.innerHTML = this.formatMessage(content);
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = this.formatTime(new Date());
        
        messageDiv.appendChild(bubble);
        messageDiv.appendChild(time);
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addBotResponse(response) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = this.formatMessage(response.message);
        
        messageDiv.appendChild(bubble);
        
        // Add data table if present
        if (response.data && response.data_type === 'table') {
            const tableContainer = this.createDataTable(response.data);
            messageDiv.appendChild(tableContainer);
            messageDiv.classList.add('has-table');
        }
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = this.formatTime(new Date());
        
        messageDiv.appendChild(time);
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    createDataTable(data) {
        if (!data || data.length === 0) return document.createElement('div');
        
        const container = document.createElement('div');
        container.className = 'chat-data-table';
        
        const table = document.createElement('table');
        
        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        const headers = Object.keys(data[0]);
        
        headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        data.forEach(row => {
            const tr = document.createElement('tr');
            headers.forEach(header => {
                const td = document.createElement('td');
                td.textContent = row[header] ?? '-';
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        
        table.appendChild(tbody);
        container.appendChild(table);
        
        return container;
    }
    
    formatMessage(text) {
        if (!text) return '';
        
        // Convert newlines to <br>
        let formatted = text.replace(/\n/g, '<br>');
        
        // Make bullet points look nicer
        formatted = formatted.replace(/•/g, '<span style="color: #4e73df;">•</span>');
        
        return formatted;
    }
    
    formatTime(date) {
        return date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }
    
    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'chat-message bot';
        indicator.id = 'typing-indicator';
        
        const typing = document.createElement('div');
        typing.className = 'typing-indicator';
        typing.innerHTML = '<span></span><span></span><span></span>';
        
        indicator.appendChild(typing);
        this.messagesContainer.appendChild(indicator);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    }
    
    async loadHistory() {
        try {
            const response = await fetch('/chatbot/history/');
            const data = await response.json();
            
            if (data.success && data.messages && data.messages.length > 0) {
                // Clear welcome message if there's history
                const welcome = this.messagesContainer.querySelector('.welcome-message');
                if (welcome) welcome.remove();
                
                data.messages.forEach(msg => {
                    if (msg.type === 'user') {
                        this.addMessage(msg.content, 'user');
                    } else {
                        this.addBotResponse({
                            message: msg.content,
                            data: msg.data,
                            data_type: msg.data ? 'table' : 'text'
                        });
                    }
                });
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }
    
    async clearChat() {
        try {
            const response = await fetch('/chatbot/clear/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Clear messages and show welcome
                this.messagesContainer.innerHTML = `
                    <div class="welcome-message">
                        <div class="welcome-icon">🤖</div>
                        <h4>VMS Assistant</h4>
                        <p>Ask me about drivers, vehicles, trips, fuel, and more!</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error clearing chat:', error);
        }
    }
}

// Initialize chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if chatbot elements exist
    if (document.getElementById('chatbot-container')) {
        window.vmsChatbot = new VMSChatbot();
    }
});
