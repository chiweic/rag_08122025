// RAG System Frontend Application
// API URL - use same origin (no port needed as both frontend and API are on same server)
const API_BASE_URL = window.location.origin;

class RAGChatApp {
    constructor() {
        this.chatContainer = document.getElementById('chat-container');
        this.queryInput = document.getElementById('query-input');
        this.sendButton = document.getElementById('send-button');
        this.statusText = document.getElementById('status-text');
        this.referencesPanel = document.getElementById('references-panel');
        this.referencesContent = document.getElementById('references-content');
        this.bookRecommendations = document.getElementById('book-recommendations');
        this.audioRecommendations = document.getElementById('audio-recommendations');
        this.performanceCanvas = document.getElementById('performance-canvas');
        
        this.isLoading = false;
        this.currentQuery = '';
        this.performanceData = [];
        this.maxDataPoints = 10;
        
        this.init();
        this.initPerformanceChart();
    }

    init() {
        // Bind event listeners
        this.sendButton.addEventListener('click', () => this.sendQuery());
        this.queryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendQuery();
            }
        });

        // Check API connection
        this.checkConnection();
        
        // Make app instance globally available for modal callbacks
        window.ragApp = this;
        
        // Add event delegation for view buttons
        this.chatContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-content-btn')) {
                const chunkId = e.target.getAttribute('data-chunk-id');
                const title = e.target.getAttribute('data-title');
                this.showContentModal(chunkId, title, e);
            }
        });
    }

    async checkConnection() {
        try {
            const response = await fetch(`${API_BASE_URL}/health`);
            const data = await response.json();
            
            if (data.initialized) {
                this.updateStatus('Connected', true);
            } else {
                this.updateStatus('Not Initialized', false);
                this.showSystemMessage('System not initialized. Please initialize the backend first.');
            }
        } catch (error) {
            this.updateStatus('Disconnected', false);
            this.showSystemMessage('Cannot connect to backend. Please ensure the API server is running on port 8000.');
        }
    }

    updateStatus(text, isConnected) {
        this.statusText.textContent = text;
        const indicator = document.querySelector('.status-indicator');
        indicator.style.backgroundColor = isConnected ? '#4ade80' : '#ef4444';
    }

    showSystemMessage(message) {
        this.addMessage(message, 'assistant', null, null, true);
    }

    addMessage(content, role = 'user', sources = null, computationTime = null, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${role}`;
        
        let messageHTML = `
            <div class="message-bubble">
                <div class="message-content${isError ? ' error-message' : ''}">${this.escapeHtml(content)}</div>
        `;

        // Add computation time if available - show prominently for assistant messages
        if (computationTime && role === 'assistant') {
            messageHTML += `
                <div class="metadata" style="background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); margin-top: 15px; padding: 12px; border-radius: 10px; border: 1px solid #d1d5db;">
                    <div class="runtime-info" style="font-size: 0.9rem; font-weight: 500;">
                        <span style="color: #059669;">⚡ Retrieval: ${computationTime.retrieval.toFixed(2)}s</span>
                        <span style="color: #7c3aed;">🧠 Synthesis: ${computationTime.synthesis.toFixed(2)}s</span>
                        <span style="color: #dc2626; font-weight: 700;">⏱️ Total: ${computationTime.total.toFixed(2)}s</span>
                    </div>
                </div>
            `;
        }

        messageHTML += '</div>';
        messageDiv.innerHTML = messageHTML;
        
        this.chatContainer.appendChild(messageDiv);
        
        // Handle sources in the separate references panel
        if (sources && sources.length > 0) {
            this.showReferences(sources);
        }
        
        this.scrollToBottom();
    }

    showReferences(sources) {
        // Show the references panel
        this.referencesPanel.classList.add('show');
        
        // Create carousel for references
        const carousel = this.createSourceCarousel(sources);
        this.referencesContent.innerHTML = carousel;
        
        // Clear blur effects on references
        setTimeout(() => {
            const referencesPanel = this.referencesPanel;
            if (referencesPanel) {
                referencesPanel.style.filter = 'none';
                referencesPanel.style.opacity = '1';
                
                // Remove loading indicator
                const loadingText = referencesPanel.querySelector('.references-loading');
                if (loadingText) {
                    loadingText.remove();
                }
            }
        }, 300); // Small delay for smooth transition
    }

    showBookRecommendations(books) {
        if (books && books.length > 0) {
            // Create single-frame carousel for book recommendations
            const carouselHTML = this.createSingleFrameBookCarousel(books);
            this.bookRecommendations.innerHTML = carouselHTML;
            
            // Start auto-rotation if more than one book
            if (books.length > 1) {
                this.startBookAutoRotation(books);
            }
        } else {
            this.bookRecommendations.innerHTML = '<div class="sidebar-empty">No recommendations available</div>';
            this.stopBookAutoRotation();
        }
        
        // Clear blur effects on book recommendations with smooth transition
        setTimeout(() => {
            const bookRecommendations = this.bookRecommendations;
            if (bookRecommendations) {
                bookRecommendations.style.filter = 'none';
                bookRecommendations.style.opacity = '1';
                bookRecommendations.style.pointerEvents = 'auto';
                
                // Remove loading indicator
                const loadingText = bookRecommendations.querySelector('.recommendation-loading');
                if (loadingText) {
                    loadingText.style.opacity = '0';
                    setTimeout(() => loadingText.remove(), 200);
                }
            }
        }, 400); // Slightly longer delay for book recommendations
    }
    
    startBookAutoRotation(books) {
        // Clear any existing interval
        this.stopBookAutoRotation();
        
        // Get the carousel element
        const carousel = this.bookRecommendations.querySelector('.single-frame-carousel');
        if (!carousel) return;
        
        const frameId = carousel.id;
        let isPaused = false;
        
        // Get the auto-rotate indicator
        const indicator = carousel.querySelector('.auto-rotate-indicator');
        const indicatorDot = indicator ? indicator.querySelector('span:first-child') : null;
        
        // Pause on hover
        carousel.addEventListener('mouseenter', () => {
            isPaused = true;
            if (indicatorDot) {
                indicatorDot.style.background = '#fbbf24'; // Yellow when paused
            }
        });
        
        // Resume on mouse leave
        carousel.addEventListener('mouseleave', () => {
            isPaused = false;
            if (indicatorDot) {
                indicatorDot.style.background = '#10b981'; // Green when active
            }
        });
        
        // Auto-rotate every 3 seconds
        this.bookRotationInterval = setInterval(() => {
            if (!isPaused) {
                const content = carousel.querySelector('.frame-content');
                if (content) {
                    const currentIndex = parseInt(content.getAttribute('data-current'));
                    const nextIndex = (currentIndex + 1) % books.length;
                    this.jumpToFrame(frameId, nextIndex);
                }
            }
        }, 3000);
    }
    
    stopBookAutoRotation() {
        if (this.bookRotationInterval) {
            clearInterval(this.bookRotationInterval);
            this.bookRotationInterval = null;
        }
    }
    
    blurRecommendationsAndReferences() {
        // Blur book recommendations
        const bookRecommendations = this.bookRecommendations;
        if (bookRecommendations && bookRecommendations.children.length > 0) {
            bookRecommendations.style.transition = 'all 0.3s ease';
            bookRecommendations.style.filter = 'blur(3px)';
            bookRecommendations.style.opacity = '0.5';
            bookRecommendations.style.pointerEvents = 'none';
            
            // Add loading indicator to book recommendations
            const loadingText = document.createElement('div');
            loadingText.className = 'recommendation-loading';
            loadingText.style.cssText = `
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: #667eea;
                font-weight: 600;
                font-size: 0.9rem;
                z-index: 10;
                background: white;
                padding: 8px 16px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            `;
            loadingText.textContent = '🔄 Updating recommendations...';
            
            // Make book recommendations container relative for positioning
            bookRecommendations.style.position = 'relative';
            bookRecommendations.appendChild(loadingText);
        }
        
        // Blur audio recommendations
        const audioRecommendations = this.audioRecommendations;
        if (audioRecommendations && audioRecommendations.children.length > 0) {
            audioRecommendations.style.transition = 'all 0.3s ease';
            audioRecommendations.style.filter = 'blur(3px)';
            audioRecommendations.style.opacity = '0.5';
            audioRecommendations.style.pointerEvents = 'none';
            
            // Add loading indicator to audio recommendations
            const loadingText = document.createElement('div');
            loadingText.className = 'recommendation-loading';
            loadingText.style.cssText = `
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: #059669;
                font-weight: 600;
                font-size: 0.9rem;
                z-index: 10;
                background: white;
                padding: 8px 16px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            `;
            loadingText.textContent = '🔄 Updating audio...';
            
            // Make audio recommendations container relative for positioning
            audioRecommendations.style.position = 'relative';
            audioRecommendations.appendChild(loadingText);
        }
        
        // Blur references panel
        const referencesPanel = this.referencesPanel;
        if (referencesPanel && referencesPanel.classList.contains('show')) {
            referencesPanel.style.transition = 'all 0.3s ease';
            referencesPanel.style.filter = 'blur(2px)';
            referencesPanel.style.opacity = '0.6';
            
            // Add loading indicator to references
            const existingLoader = referencesPanel.querySelector('.references-loading');
            if (!existingLoader) {
                const loadingText = document.createElement('div');
                loadingText.className = 'references-loading';
                loadingText.style.cssText = `
                    position: absolute;
                    top: 20px;
                    right: 20px;
                    color: #10b981;
                    font-weight: 500;
                    font-size: 0.8rem;
                    z-index: 10;
                    background: rgba(255,255,255,0.9);
                    padding: 4px 8px;
                    border-radius: 6px;
                    border: 1px solid rgba(16, 185, 129, 0.2);
                `;
                loadingText.textContent = '🔄 New references loading...';
                
                referencesPanel.style.position = 'relative';
                referencesPanel.appendChild(loadingText);
            }
        }
    }
    
    clearRecommendationsAndReferencesEffects() {
        // Clear book recommendations effects
        const bookRecommendations = this.bookRecommendations;
        if (bookRecommendations) {
            bookRecommendations.style.filter = 'none';
            bookRecommendations.style.opacity = '1';
            bookRecommendations.style.pointerEvents = 'auto';
            
            // Remove loading indicator
            const loadingText = bookRecommendations.querySelector('.recommendation-loading');
            if (loadingText) {
                loadingText.remove();
            }
        }
        
        // Clear audio recommendations effects
        const audioRecommendations = this.audioRecommendations;
        if (audioRecommendations) {
            audioRecommendations.style.filter = 'none';
            audioRecommendations.style.opacity = '1';
            audioRecommendations.style.pointerEvents = 'auto';
            
            // Remove loading indicator
            const loadingText = audioRecommendations.querySelector('.recommendation-loading');
            if (loadingText) {
                loadingText.remove();
            }
        }
        
        // Clear references panel effects
        const referencesPanel = this.referencesPanel;
        if (referencesPanel) {
            referencesPanel.style.filter = 'none';
            referencesPanel.style.opacity = '1';
            
            // Remove loading indicator
            const loadingText = referencesPanel.querySelector('.references-loading');
            if (loadingText) {
                loadingText.remove();
            }
        }
    }

    showLoading() {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-indicator';
        loadingDiv.style.cssText = 'display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 20px;';
        
        // Add loading dots
        const dotsContainer = document.createElement('div');
        dotsContainer.className = 'loading';
        dotsContainer.innerHTML = `
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
        `;
        
        // Add timer display
        const timerDiv = document.createElement('div');
        timerDiv.id = 'loading-timer';
        timerDiv.style.cssText = 'color: #6b7280; font-size: 0.9rem; font-weight: 500;';
        timerDiv.textContent = 'Processing... 0.0s';
        
        loadingDiv.appendChild(dotsContainer);
        loadingDiv.appendChild(timerDiv);
        this.chatContainer.appendChild(loadingDiv);
        
        // Start timer
        const startTime = Date.now();
        this.loadingTimer = setInterval(() => {
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            const timer = document.getElementById('loading-timer');
            if (timer) {
                timer.textContent = `Processing... ${elapsed}s`;
            }
        }, 100);
        
        this.scrollToBottom();
    }

    hideLoading() {
        // Clear timer
        if (this.loadingTimer) {
            clearInterval(this.loadingTimer);
            this.loadingTimer = null;
        }
        
        const loadingDiv = document.getElementById('loading-indicator');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }

    async sendQuery() {
        const query = this.queryInput.value.trim();
        
        if (!query || this.isLoading) {
            return;
        }

        // Store current query for book recommendations and event recommendations
        this.currentQuery = query;
        this.lastUserMessage = query;
        console.log('🔧 Set lastUserMessage to:', this.lastUserMessage);
        
        // Add visual effects for new query
        this.blurRecommendationsAndReferences();
        
        // Add user message
        this.addMessage(query, 'user');
        
        // Clear input and disable send button
        this.queryInput.value = '';
        this.isLoading = true;
        this.sendButton.disabled = true;
        
        // Show loading indicator
        this.showLoading();

        try {
            // Use streaming endpoint
            const response = await fetch(`${API_BASE_URL}/query/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: query,
                    text_limit: 3,
                    audio_limit: 1,
                    event_limit: 1,
                    similarity_threshold: 0.3,
                    include_sources: true,
                    temperature: 0.7,
                    max_tokens: 1000
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            this.hideLoading();
            await this.handleStreamingResponse(response);
            
        } catch (error) {
            this.hideLoading();
            this.addMessage(
                `Error: ${error.message}`, 
                'assistant',
                null,
                null,
                true
            );
            console.error('Query error:', error);
        } finally {
            this.isLoading = false;
            this.sendButton.disabled = false;
            this.queryInput.focus();
        }
    }

    async handleStreamingResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let streamingMessageDiv = null;
        let currentAnswer = '';
        let sources = null;
        let timingInfo = {};
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        
                        if (data === '[DONE]') {
                            // Store the current answer for audio recommendations
                            this.lastAnswer = currentAnswer;
                            console.log('🔧 Set lastAnswer to:', this.lastAnswer);
                            
                            // Finalize the message with timing info
                            if (streamingMessageDiv) {
                                this.finalizeStreamingMessage(streamingMessageDiv, sources, timingInfo);
                            }
                            return;
                        }
                        
                        try {
                            const parsed = JSON.parse(data);
                            
                            switch (parsed.type) {
                                case 'start':
                                    // Create initial streaming message container
                                    streamingMessageDiv = this.createStreamingMessage();
                                    break;
                                    
                                case 'sources':
                                    sources = parsed.sources;
                                    if (parsed.retrieval_time) {
                                        timingInfo.retrieval = parsed.retrieval_time;
                                    }
                                    break;
                                    
                                case 'answer':
                                    if (streamingMessageDiv && parsed.content) {
                                        currentAnswer += parsed.content;
                                        this.updateStreamingMessage(streamingMessageDiv, currentAnswer);
                                    }
                                    break;
                                    
                                case 'done':
                                    if (parsed.synthesis_time) {
                                        timingInfo.synthesis = parsed.synthesis_time;
                                    }
                                    if (parsed.total_time) {
                                        timingInfo.total = parsed.total_time;
                                    }
                                    break;
                                    
                                case 'error':
                                    throw new Error(parsed.message);
                            }
                        } catch (e) {
                            // Skip malformed JSON
                            continue;
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Streaming error:', error);
            if (streamingMessageDiv) {
                this.updateStreamingMessage(streamingMessageDiv, currentAnswer + '\n\n[Error: Stream interrupted]');
            }
        }
    }

    createStreamingMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message message-assistant';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = '<span class="streaming-cursor">▊</span>';
        
        bubbleDiv.appendChild(contentDiv);
        messageDiv.appendChild(bubbleDiv);
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageDiv;
    }

    updateStreamingMessage(messageDiv, content) {
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv) {
            contentDiv.innerHTML = this.escapeHtml(content) + '<span class="streaming-cursor">▊</span>';
            this.scrollToBottom();
        }
    }

    async finalizeStreamingMessage(messageDiv, sources, timingInfo) {
        console.log('🔧 finalizeStreamingMessage called');
        const contentDiv = messageDiv.querySelector('.message-content');
        if (contentDiv) {
            // Remove cursor
            const content = contentDiv.innerHTML.replace('<span class="streaming-cursor">▊</span>', '');
            contentDiv.innerHTML = content;
            
            const bubbleDiv = messageDiv.querySelector('.message-bubble');
            
            // Add timing info if available
            if (timingInfo.retrieval || timingInfo.synthesis || timingInfo.total) {
                this.addTimingToMessage(bubbleDiv, timingInfo);
                
                // Add performance data to chart
                this.addPerformanceData(timingInfo);
            }
            
            // Show sources in the references panel
            if (sources && sources.length > 0) {
                this.showReferences(sources);
            }
            
            // Get and show book recommendations in the sidebar
            console.log('🔧 About to load book recommendations');
            await this.loadBookRecommendations();
            
            // Load and show event recommendations  
            console.log('🔧 About to load event recommendations');
            await this.loadEventRecommendations();
            
            // Load and show audio recommendations
            console.log('🔧 About to load audio recommendations');
            await this.loadAudioRecommendations();
            
            // Load and show related queries
            console.log('🔧 About to load related queries');
            await this.loadRelatedQueries();
        }
        
        this.scrollToBottom();
    }
    
    showRelatedQueries(queries) {
        console.log('🎯 Displaying related queries:', queries);
        if (!queries || queries.length === 0) {
            console.log('❌ No related queries to show');
            return;
        }
        
        const relatedQueriesHTML = this.createRelatedQueriesDisplay(queries);
        
        // Find the last assistant message and append related queries
        const lastAssistantMessage = [...this.chatContainer.querySelectorAll('.message-assistant')].pop();
        if (lastAssistantMessage) {
            const bubbleDiv = lastAssistantMessage.querySelector('.message-bubble');
            if (bubbleDiv) {
                // Remove any existing related queries first
                const existingRelated = bubbleDiv.querySelector('.related-queries');
                if (existingRelated) {
                    console.log('🔄 Removing existing related queries');
                    existingRelated.remove();
                }
                bubbleDiv.insertAdjacentHTML('beforeend', relatedQueriesHTML);
                console.log('✅ Related queries added to message');
            } else {
                console.log('❌ No message bubble found');
            }
        } else {
            console.log('❌ No assistant message found');
        }
    }
    
    createRelatedQueriesDisplay(queries) {
        if (!queries || queries.length === 0) return '';
        
        return `
            <div class="related-queries" style="
                margin-top: 16px;
                padding: 12px;
                background: rgba(102, 126, 234, 0.05);
                border-radius: 8px;
                border-left: 3px solid rgba(102, 126, 234, 0.3);
            ">
                <div class="related-header" style="
                    font-size: 0.8rem;
                    color: #6b7280;
                    margin-bottom: 8px;
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                ">
                    <span>💭</span>
                    <span>Related Questions</span>
                </div>
                
                <div class="query-suggestions">
                    ${queries.map(q => `
                        <div class="suggestion-query" 
                             data-query="${this.escapeHtml(q.text)}"
                             data-reason="${this.escapeHtml(q.reason)}"
                             style="
                                color: #9ca3af;
                                font-size: 0.85rem;
                                padding: 8px 12px;
                                margin: 4px 0;
                                border-radius: 6px;
                                cursor: pointer;
                                transition: all 0.2s ease;
                                border: 1px solid transparent;
                                position: relative;
                                display: flex;
                                justify-content: space-between;
                                align-items: center;
                             "
                             onmouseover="this.style.color='#667eea'; this.style.background='rgba(102, 126, 234, 0.1)'; this.style.borderColor='rgba(102, 126, 234, 0.2)'; this.style.transform='translateX(4px)'"
                             onmouseout="this.style.color='#9ca3af'; this.style.background='transparent'; this.style.borderColor='transparent'; this.style.transform='translateX(0)'"
                             onclick="window.ragApp.executeRelatedQuery('${this.escapeHtml(q.text)}')">
                            <span class="query-text">${this.escapeHtml(q.text)}</span>
                            <span class="query-reason" style="
                                font-size: 0.7rem;
                                color: #a1a1aa;
                                background: rgba(161, 161, 170, 0.1);
                                padding: 2px 6px;
                                border-radius: 4px;
                                margin-left: 8px;
                            ">${this.escapeHtml(q.reason)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    executeRelatedQuery(query) {
        // Populate input and trigger search
        this.queryInput.value = query;
        this.sendQuery();
    }
    
    initPerformanceChart() {
        if (!this.performanceCanvas) return;
        
        this.ctx = this.performanceCanvas.getContext('2d');
        this.drawChart();
    }
    
    addPerformanceData(computationTime) {
        if (!computationTime) return;
        
        const dataPoint = {
            retrieval: computationTime.retrieval || 0,
            synthesis: computationTime.synthesis || 0,
            total: computationTime.total || 0,
            timestamp: Date.now()
        };
        
        this.performanceData.push(dataPoint);
        
        // Keep only last N data points
        if (this.performanceData.length > this.maxDataPoints) {
            this.performanceData.shift();
        }
        
        this.drawChart();
    }
    
    drawChart() {
        if (!this.ctx || this.performanceData.length === 0) return;
        
        const canvas = this.performanceCanvas;
        const ctx = this.ctx;
        const data = this.performanceData;
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Chart dimensions
        const padding = 5;
        const chartWidth = canvas.width - padding * 2;
        const chartHeight = canvas.height - padding * 2;
        
        // Find max values for scaling
        const maxTotal = Math.max(...data.map(d => d.total), 1);
        const scaleY = chartHeight / maxTotal;
        const scaleX = chartWidth / Math.max(data.length - 1, 1);
        
        // Draw lines
        ctx.lineWidth = 1.5;
        
        // Draw retrieval line (green)
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.8)';
        ctx.beginPath();
        data.forEach((point, i) => {
            const x = padding + i * scaleX;
            const y = canvas.height - padding - (point.retrieval * scaleY);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
        
        // Draw synthesis line (purple)
        ctx.strokeStyle = 'rgba(124, 58, 237, 0.8)';
        ctx.beginPath();
        data.forEach((point, i) => {
            const x = padding + i * scaleX;
            const y = canvas.height - padding - (point.synthesis * scaleY);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
        
        // Draw total line (white, thicker)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        data.forEach((point, i) => {
            const x = padding + i * scaleX;
            const y = canvas.height - padding - (point.total * scaleY);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
        
        // Draw latest values as text
        if (data.length > 0) {
            const latest = data[data.length - 1];
            ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(`${latest.total.toFixed(1)}s`, canvas.width - 2, 12);
        }
        
        // Draw legend dots
        const legendY = canvas.height - 4;
        ctx.fillStyle = 'rgba(16, 185, 129, 0.8)';
        ctx.fillRect(2, legendY - 2, 4, 2);
        ctx.fillStyle = 'rgba(124, 58, 237, 0.8)';
        ctx.fillRect(8, legendY - 2, 4, 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
        ctx.fillRect(14, legendY - 2, 4, 2);
    }

    addSourcesToMessage(bubbleDiv, sources) {
        const sourcesHTML = this.createSourceCarousel(sources);
        bubbleDiv.insertAdjacentHTML('beforeend', sourcesHTML);
    }

    addTimingToMessage(bubbleDiv, timingInfo) {
        const timingHTML = `
            <div class="metadata" style="background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); margin-top: 15px; padding: 12px; border-radius: 10px; border: 1px solid #d1d5db;">
                <div class="runtime-info" style="font-size: 0.9rem; font-weight: 500;">
                    ${timingInfo.retrieval ? `<span style="color: #059669;">⚡ Retrieval: ${timingInfo.retrieval.toFixed(2)}s</span>` : ''}
                    ${timingInfo.synthesis ? `<span style="color: #7c3aed;">🧠 Synthesis: ${timingInfo.synthesis.toFixed(2)}s</span>` : ''}
                    ${timingInfo.total ? `<span style="color: #dc2626; font-weight: 700;">⏱️ Total: ${timingInfo.total.toFixed(2)}s</span>` : ''}
                </div>
            </div>
        `;
        
        bubbleDiv.insertAdjacentHTML('beforeend', timingHTML);
    }

    async loadBookRecommendations() {
        if (!this.currentQuery) return;
        
        try {
            const books = await this.getBookRecommendations(this.currentQuery);
            this.showBookRecommendations(books);
        } catch (error) {
            console.warn('Failed to load book recommendations:', error);
            this.showBookRecommendations([]);
        }
    }
    
    async loadRelatedQueries() {
        if (!this.currentQuery) return;
        
        try {
            const queries = await this.getRelatedQueries(this.currentQuery);
            this.showRelatedQueries(queries);
        } catch (error) {
            console.warn('Failed to load related queries:', error);
            this.showRelatedQueries([]);
        }
    }

    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    escapeHtml(text) {
        if (text == null || text === undefined) {
            return '';
        }
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }

    async showContentModal(chunkId, title, event) {
        console.log('showContentModal called with:', { chunkId, title });
        event.stopPropagation();
        
        try {
            // Get full chunk content
            const response = await fetch(`${API_BASE_URL}/chunk/${chunkId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch chunk content: ${response.status}`);
            }

            const chunkData = await response.json();
            
            // Create modal
            this.createModal(title, chunkData.content, chunkData.metadata, chunkData);
            
        } catch (error) {
            console.error('Error fetching chunk content:', error);
            this.createModal(title, 'Error loading content. Please try again.', {}, {});
        }
    }

    createModal(title, content, metadata, chunkData = {}) {
        // Remove existing modal if any
        const existingModal = document.getElementById('content-modal');
        if (existingModal) {
            existingModal.remove();
        }

        // Create modal overlay
        const modal = document.createElement('div');
        modal.id = 'content-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            backdrop-filter: blur(4px);
            animation: fadeIn 0.2s ease;
        `;

        // Create modal content
        const modalContent = document.createElement('div');
        modalContent.style.cssText = `
            background: white;
            border-radius: 16px;
            width: 90%;
            max-width: 800px;
            max-height: 80%;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s ease;
        `;

        // Create header
        const header = document.createElement('div');
        header.style.cssText = `
            padding: 20px 24px;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 16px 16px 0 0;
        `;

        const titleDiv = document.createElement('div');
        titleDiv.style.cssText = `
            font-size: 1.2rem;
            font-weight: 600;
            line-height: 1.4;
            margin-right: 16px;
        `;
        titleDiv.textContent = title;

        const closeButton = document.createElement('button');
        closeButton.style.cssText = `
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 8px;
            color: white;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s ease;
            backdrop-filter: blur(4px);
        `;
        closeButton.textContent = '✕ Close';
        closeButton.onmouseover = () => {
            closeButton.style.background = 'rgba(255, 255, 255, 0.3)';
            closeButton.style.transform = 'scale(1.05)';
        };
        closeButton.onmouseout = () => {
            closeButton.style.background = 'rgba(255, 255, 255, 0.2)';
            closeButton.style.transform = 'scale(1)';
        };
        closeButton.onclick = () => this.closeModal();

        header.appendChild(titleDiv);
        header.appendChild(closeButton);

        // Create metadata section if available
        let metadataSection = '';
        if (metadata && Object.keys(metadata).length > 0) {
            metadataSection = `
                <div style="
                    padding: 20px 24px;
                    background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
                    border-bottom: 1px solid #e5e7eb;
                    font-size: 0.9rem;
                    color: #374151;
                ">
                    <div style="font-weight: 600; margin-bottom: 16px; color: #1f2937; font-size: 1rem;">
                        📊 Document Information
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 16px;">
                        ${metadata.title ? `
                            <div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #667eea;">
                                <div style="font-weight: 500; color: #6b7280; font-size: 0.8rem; margin-bottom: 4px;">📖 Title</div>
                                <div style="color: #1f2937; font-weight: 500;">${this.escapeHtml(metadata.title)}</div>
                            </div>
                        ` : ''}
                        
                        ${metadata.pages ? `
                            <div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #10b981;">
                                <div style="font-weight: 500; color: #6b7280; font-size: 0.8rem; margin-bottom: 4px;">📄 Pages</div>
                                <div style="color: #1f2937; font-weight: 500;">${metadata.pages}</div>
                            </div>
                        ` : ''}
                        
                        ${metadata.category ? `
                            <div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                                <div style="font-weight: 500; color: #6b7280; font-size: 0.8rem; margin-bottom: 4px;">🏷️ Category</div>
                                <div style="color: #1f2937; font-weight: 500;">${this.escapeHtml(metadata.category)}</div>
                            </div>
                        ` : ''}
                        
                        ${metadata.source ? `
                            <div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #8b5cf6;">
                                <div style="font-weight: 500; color: #6b7280; font-size: 0.8rem; margin-bottom: 4px;">📚 Source</div>
                                <div style="color: #1f2937; font-weight: 500;">${this.escapeHtml(metadata.source)}</div>
                            </div>
                        ` : ''}
                    </div>
                    
                    ${metadata.keyphrases && metadata.keyphrases.length > 0 ? `
                        <div style="margin-top: 12px;">
                            <div style="font-weight: 500; color: #6b7280; font-size: 0.8rem; margin-bottom: 8px;">🔍 Key Phrases</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                                ${metadata.keyphrases.map(phrase => `
                                    <span style="
                                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                        color: white;
                                        padding: 4px 8px;
                                        border-radius: 12px;
                                        font-size: 0.75rem;
                                        font-weight: 500;
                                        white-space: nowrap;
                                    ">${this.escapeHtml(phrase)}</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        }

        // Create content section
        const contentSection = document.createElement('div');
        contentSection.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            line-height: 1.6;
            color: #374151;
            font-size: 0.95rem;
        `;
        
        const headerSection = chunkData.header ? `
            <div style="
                background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
                padding: 16px 24px;
                border-bottom: 1px solid #e5e7eb;
                border-left: 4px solid #f59e0b;
                margin-bottom: 20px;
            ">
                <div style="font-weight: 600; color: #92400e; font-size: 0.9rem; margin-bottom: 8px;">
                    📋 Section Header
                </div>
                <div style="color: #78350f; font-weight: 500; line-height: 1.5;">
                    ${this.escapeHtml(chunkData.header)}
                </div>
            </div>
        ` : '';

        contentSection.innerHTML = metadataSection + `
            <div style="padding: 0 24px;">
                ${headerSection}
                <div style="
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    border: 1px solid #e5e7eb;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                ">
                    <div style="font-weight: 600; color: #1f2937; font-size: 0.9rem; margin-bottom: 12px; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px;">
                        📝 Content
                    </div>
                    <div style="white-space: pre-wrap; word-wrap: break-word; line-height: 1.7; color: #374151;">
                        ${this.escapeHtml(content)}
                    </div>
                </div>
            </div>
        `;

        modalContent.appendChild(header);
        modalContent.appendChild(contentSection);
        modal.appendChild(modalContent);

        // Add to document
        document.body.appendChild(modal);

        // Close on background click
        modal.onclick = (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        };

        // Close on Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    closeModal() {
        const modal = document.getElementById('content-modal');
        if (modal) {
            modal.style.animation = 'fadeOut 0.2s ease';
            setTimeout(() => {
                modal.remove();
            }, 200);
        }
    }

    createSourceCarousel(sources) {
        if (!sources || sources.length === 0) return '';
        
        // Separate different types of sources
        const audioSources = [];
        const documentSources = [];
        const videoSources = [];
        
        sources.forEach(source => {
            const sourceType = source.metadata?.source_type || 'document';
            if (sourceType === 'audio') {
                audioSources.push(source);
            } else if (sourceType === 'video') {
                videoSources.push(source);
            } else {
                documentSources.push(source);
            }
        });
        
        const carouselId = 'source-carousel-' + Date.now();
        
        return `
            <div class="source-references" style="margin-top: 15px;">
                
                <div class="source-carousel-container" style="position: relative;">
                    <div id="${carouselId}" class="source-carousel" style="
                        display: flex;
                        overflow-x: auto;
                        scroll-behavior: smooth;
                        gap: 12px;
                        padding: 8px 0;
                        scrollbar-width: none;
                        -ms-overflow-style: none;
                    ">
                        ${documentSources.map((source, index) => this.createSourceCard(source, index)).join('')}
                        ${audioSources.map(source => this.createAudioReferenceFromData(source)).join('')}
                        ${videoSources.map(source => this.createVideoReferenceFromData(source)).join('')}
                    </div>
                    
                    ${(documentSources.length + audioSources.length + videoSources.length) > 3 ? `
                        <button class="carousel-nav carousel-prev" style="
                            position: absolute;
                            left: -8px;
                            top: 50%;
                            transform: translateY(-50%);
                            background: rgba(16, 185, 129, 0.9);
                            color: white;
                            border: none;
                            border-radius: 50%;
                            width: 32px;
                            height: 32px;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                            transition: all 0.2s ease;
                            z-index: 10;
                        " onclick="this.parentElement.querySelector('.source-carousel').scrollBy({left: -240, behavior: 'smooth'})"
                           onmouseover="this.style.background='rgba(16, 185, 129, 1)'; this.style.transform='translateY(-50%) scale(1.1)'"
                           onmouseout="this.style.background='rgba(16, 185, 129, 0.9)'; this.style.transform='translateY(-50%) scale(1)'">
                            ‹
                        </button>
                        
                        <button class="carousel-nav carousel-next" style="
                            position: absolute;
                            right: -8px;
                            top: 50%;
                            transform: translateY(-50%);
                            background: rgba(16, 185, 129, 0.9);
                            color: white;
                            border: none;
                            border-radius: 50%;
                            width: 32px;
                            height: 32px;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                            transition: all 0.2s ease;
                            z-index: 10;
                        " onclick="this.parentElement.querySelector('.source-carousel').scrollBy({left: 240, behavior: 'smooth'})"
                           onmouseover="this.style.background='rgba(16, 185, 129, 1)'; this.style.transform='translateY(-50%) scale(1.1)'"
                           onmouseout="this.style.background='rgba(16, 185, 129, 0.9)'; this.style.transform='translateY(-50%) scale(1)'">
                            ›
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    createBookCarousel(books) {
        if (!books || books.length === 0) return '';
        
        const carouselId = 'book-carousel-' + Date.now();
        
        return `
            <div class="book-recommendations" style="margin-top: 20px;">
                <div style="font-weight: 600; margin-bottom: 12px; color: #374151; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;">
                    📚 推薦書籍 (${books.length} 本)
                </div>
                
                <div class="book-carousel-container" style="position: relative;">
                    <div id="${carouselId}" class="book-carousel" style="
                        display: flex;
                        overflow-x: auto;
                        scroll-behavior: smooth;
                        gap: 12px;
                        padding: 8px 0;
                        scrollbar-width: none;
                        -ms-overflow-style: none;
                    ">
                        ${books.map((book, index) => this.createBookCard(book, index)).join('')}
                    </div>
                    
                    ${books.length > 3 ? `
                        <button class="carousel-nav carousel-prev" style="
                            position: absolute;
                            left: -8px;
                            top: 50%;
                            transform: translateY(-50%);
                            background: rgba(102, 126, 234, 0.9);
                            color: white;
                            border: none;
                            border-radius: 50%;
                            width: 32px;
                            height: 32px;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                            transition: all 0.2s ease;
                            z-index: 10;
                        " onclick="this.parentElement.querySelector('.book-carousel').scrollBy({left: -240, behavior: 'smooth'})"
                           onmouseover="this.style.background='rgba(102, 126, 234, 1)'; this.style.transform='translateY(-50%) scale(1.1)'"
                           onmouseout="this.style.background='rgba(102, 126, 234, 0.9)'; this.style.transform='translateY(-50%) scale(1)'">
                            ‹
                        </button>
                        
                        <button class="carousel-nav carousel-next" style="
                            position: absolute;
                            right: -8px;
                            top: 50%;
                            transform: translateY(-50%);
                            background: rgba(102, 126, 234, 0.9);
                            color: white;
                            border: none;
                            border-radius: 50%;
                            width: 32px;
                            height: 32px;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                            transition: all 0.2s ease;
                            z-index: 10;
                        " onclick="this.parentElement.querySelector('.book-carousel').scrollBy({left: 240, behavior: 'smooth'})"
                           onmouseover="this.style.background='rgba(102, 126, 234, 1)'; this.style.transform='translateY(-50%) scale(1.1)'"
                           onmouseout="this.style.background='rgba(102, 126, 234, 0.9)'; this.style.transform='translateY(-50%) scale(1)'">
                            ›
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    createSourceCard(source, index) {
        const relevanceColor = source.score > 0.4 ? '#059669' : source.score > 0.3 ? '#d97706' : '#dc2626';
        const relevanceText = source.score > 0.4 ? 'High' : source.score > 0.3 ? 'Medium' : 'Low';
        const similarity = `${(source.score * 100).toFixed(0)}%`;
        const pages = source.pages || 'N/A';
        const category = source.category || 'Unknown';
        const title = source.title || 'Untitled';
        
        return `
            <div class="source-card" style="
                min-width: 220px;
                max-width: 220px;
                background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                cursor: pointer;
                position: relative;
                overflow: hidden;
            " onclick="window.ragApp.showContentModal('${source.chunk_id}', '${this.escapeHtml(title)}', event)"
               onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'"
               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'">
               
                <div style="
                    position: absolute;
                    top: 12px;
                    right: 12px;
                    background: ${relevanceColor};
                    color: white;
                    padding: 4px 8px;
                    border-radius: 12px;
                    font-size: 0.7rem;
                    font-weight: 600;
                ">${similarity}</div>
                
                <div class="source-header" style="margin-bottom: 8px; margin-right: 40px;">
                    <div class="source-title" style="
                        font-weight: 600;
                        color: #1f2937;
                        font-size: 0.9rem;
                        line-height: 1.3;
                        display: -webkit-box;
                        -webkit-line-clamp: 3;
                        -webkit-box-orient: vertical;
                        overflow: hidden;
                    ">${this.escapeHtml(title)}</div>
                </div>
                
                <div class="source-content" style="margin-bottom: 12px;">
                    <div class="source-info" style="
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 8px;
                        margin-bottom: 8px;
                    ">
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <span style="color: #6b7280; font-size: 0.75rem;">📄</span>
                            <span style="color: #4b5563; font-size: 0.75rem; font-weight: 500;">${pages}</span>
                        </div>
                        
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <span style="color: #6b7280; font-size: 0.75rem;">🎯</span>
                            <span style="color: #4b5563; font-size: 0.75rem; font-weight: 500;">${relevanceText}</span>
                        </div>
                    </div>
                    
                    <div class="source-category" style="
                        background: rgba(16, 185, 129, 0.1);
                        color: #10b981;
                        padding: 4px 8px;
                        border-radius: 6px;
                        font-size: 0.7rem;
                        font-weight: 500;
                        border-left: 3px solid #10b981;
                        margin-bottom: 8px;
                    ">${this.escapeHtml(category)}</div>
                    
                    <div style="
                        background: #f3f4f6; 
                        padding: 6px 8px; 
                        border-radius: 4px; 
                        border-left: 3px solid ${relevanceColor};
                    ">
                        <div style="color: #6b7280; font-size: 0.65rem; margin-bottom: 2px;">Content Preview</div>
                        <div style="
                            color: #374151; 
                            font-size: 0.7rem; 
                            line-height: 1.3;
                            display: -webkit-box;
                            -webkit-line-clamp: 2;
                            -webkit-box-orient: vertical;
                            overflow: hidden;
                        ">${this.escapeHtml((source.text || '').substring(0, 80))}${source.text && source.text.length > 80 ? '...' : ''}</div>
                    </div>
                </div>
                
                <div class="source-footer" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding-top: 8px;
                    border-top: 1px solid #f3f4f6;
                ">
                    <div class="source-score" style="
                        font-weight: 600;
                        color: ${relevanceColor};
                        font-size: 0.85rem;
                    ">Score: ${similarity}</div>
                    
                    <div class="source-action" style="
                        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                        color: white;
                        padding: 4px 8px;
                        border-radius: 6px;
                        font-size: 0.7rem;
                        font-weight: 500;
                    ">📖 View</div>
                </div>
            </div>
        `;
    }

    createSingleFrameBookCarousel(books) {
        if (!books || books.length === 0) return '';
        
        const frameId = 'book-frame-' + Date.now();
        let currentIndex = 0;
        
        const html = `
            <div class="single-frame-carousel" id="${frameId}" style="
                background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
                border: 1px solid #e9d5ff;
                border-radius: 12px;
                padding: 12px;
                position: relative;
                overflow: hidden;
                min-height: 140px;
            ">
                <div class="frame-header" style="
                    font-weight: 600;
                    color: #6b21a8;
                    font-size: 0.9rem;
                    margin-bottom: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                ">
                    <span>📚 推薦書籍</span>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        ${books.length > 1 ? `
                            <span class="auto-rotate-indicator" style="
                                display: flex;
                                align-items: center;
                                gap: 4px;
                                background: rgba(107, 33, 168, 0.1);
                                padding: 2px 8px;
                                border-radius: 8px;
                                font-size: 0.7rem;
                                color: #6b21a8;
                            ">
                                <span style="
                                    display: inline-block;
                                    width: 6px;
                                    height: 6px;
                                    background: #10b981;
                                    border-radius: 50%;
                                    animation: pulse 2s infinite;
                                ">
                                </span>
                                Auto
                            </span>
                        ` : ''}
                        <span class="book-counter" style="
                            background: rgba(107, 33, 168, 0.1);
                            padding: 2px 8px;
                            border-radius: 12px;
                            font-size: 0.75rem;
                        ">1 / ${books.length}</span>
                    </div>
                </div>
                
                <div class="frame-content" data-books='${JSON.stringify(books).replace(/'/g, '&#39;')}' data-current="0">
                    ${this.createSingleBookFrame(books[0], 0, books.length)}
                </div>
                
                ${books.length > 1 ? `
                    <div class="frame-dots" style="
                        display: flex;
                        justify-content: center;
                        gap: 6px;
                        margin-top: 8px;
                    ">
                        ${books.map((_, idx) => `
                            <div class="dot" data-index="${idx}" onclick="window.ragApp.jumpToFrame('${frameId}', ${idx})" style="
                                width: 8px;
                                height: 8px;
                                border-radius: 50%;
                                background: ${idx === 0 ? '#667eea' : '#e9d5ff'};
                                cursor: pointer;
                                transition: all 0.2s ease;
                            "></div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
        
        return html;
    }

    createSingleBookFrame(book, index, total) {
        if (!book) return '<div style="color: #6b7280;">No book data available</div>';
        
        const similarity = book.similarity_score ? `${(book.similarity_score * 100).toFixed(0)}%` : '';
        const price = book.price || 'N/A';
        const reason = book.recommendation_reason || '推薦閱讀';
        
        return `
            <div class="book-frame" style="
                animation: fadeIn 0.3s ease;
            ">
                ${similarity ? `
                    <div style="
                        position: absolute;
                        top: 16px;
                        right: 16px;
                        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                        color: white;
                        padding: 4px 10px;
                        border-radius: 12px;
                        font-size: 0.75rem;
                        font-weight: 600;
                    ">相關度 ${similarity}</div>
                ` : ''}
                
                <div class="book-main" style="margin-right: ${similarity ? '80px' : '0'};">
                    <div class="book-title" style="
                        font-weight: 600;
                        color: #1f2937;
                        font-size: 0.95rem;
                        line-height: 1.3;
                        margin-bottom: 6px;
                    ">${this.escapeHtml(book.title)}</div>
                    
                    <div class="book-author" style="
                        color: #6b7280;
                        font-size: 0.8rem;
                        margin-bottom: 10px;
                    ">${this.escapeHtml(book.author || '聖嚴法師')}</div>
                    
                    <div class="book-intro" style="
                        color: #4b5563;
                        font-size: 0.75rem;
                        line-height: 1.5;
                        margin-bottom: 10px;
                        display: -webkit-box;
                        -webkit-line-clamp: 3;
                        -webkit-box-orient: vertical;
                        overflow: hidden;
                    ">${this.escapeHtml(book.content_introduction ? book.content_introduction.substring(0, 150) + '...' : '暫無簡介')}</div>
                    
                    <div class="book-meta" style="
                        display: flex;
                        gap: 10px;
                        flex-wrap: wrap;
                        margin-bottom: 10px;
                    ">
                        <div class="reason-tag" style="
                            background: rgba(102, 126, 234, 0.1);
                            color: #667eea;
                            padding: 4px 10px;
                            border-radius: 6px;
                            font-size: 0.7rem;
                            font-weight: 500;
                            border-left: 3px solid #667eea;
                        ">${this.escapeHtml(reason)}</div>
                        
                        ${book.isbn ? `
                            <div class="isbn-tag" style="
                                background: rgba(239, 68, 68, 0.1);
                                color: #dc2626;
                                padding: 4px 10px;
                                border-radius: 6px;
                                font-size: 0.7rem;
                                font-weight: 500;
                            ">ISBN: ${this.escapeHtml(book.isbn)}</div>
                        ` : ''}
                        
                        <div class="price-tag" style="
                            background: rgba(16, 185, 129, 0.1);
                            color: #059669;
                            padding: 4px 10px;
                            border-radius: 6px;
                            font-size: 0.7rem;
                            font-weight: 600;
                        ">${this.escapeHtml(price)}</div>
                    </div>
                </div>
                
                <div class="book-action" style="
                    display: flex;
                    justify-content: center;
                    margin-top: 12px;
                ">
                    <button onclick="window.open('${book.url}', '_blank')" style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 8px 24px;
                        cursor: pointer;
                        font-size: 0.8rem;
                        font-weight: 500;
                        transition: all 0.2s ease;
                        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
                    " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(102, 126, 234, 0.4)'"
                       onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(102, 126, 234, 0.3)'">
                        查看詳情 →
                    </button>
                </div>
            </div>
        `;
    }

    navigateFrame(frameId, direction) {
        const carousel = document.getElementById(frameId);
        if (!carousel) return;
        
        const content = carousel.querySelector('.frame-content');
        const books = JSON.parse(content.getAttribute('data-books'));
        let currentIndex = parseInt(content.getAttribute('data-current'));
        
        currentIndex += direction;
        
        if (currentIndex < 0) currentIndex = 0;
        if (currentIndex >= books.length) currentIndex = books.length - 1;
        
        content.setAttribute('data-current', currentIndex);
        content.innerHTML = this.createSingleBookFrame(books[currentIndex], currentIndex, books.length);
        
        // Update counter
        const counter = carousel.querySelector('.book-counter');
        if (counter) {
            counter.textContent = `${currentIndex + 1} / ${books.length}`;
        }
        
        
        // Update dots
        const dots = carousel.querySelectorAll('.dot');
        dots.forEach((dot, idx) => {
            dot.style.background = idx === currentIndex ? '#667eea' : '#e9d5ff';
        });
    }

    jumpToFrame(frameId, targetIndex) {
        const carousel = document.getElementById(frameId);
        if (!carousel) return;
        
        const content = carousel.querySelector('.frame-content');
        const books = JSON.parse(content.getAttribute('data-books'));
        
        if (targetIndex < 0 || targetIndex >= books.length) return;
        
        content.setAttribute('data-current', targetIndex);
        content.innerHTML = this.createSingleBookFrame(books[targetIndex], targetIndex, books.length);
        
        // Update counter
        const counter = carousel.querySelector('.book-counter');
        if (counter) {
            counter.textContent = `${targetIndex + 1} / ${books.length}`;
        }
        
        
        // Update dots
        const dots = carousel.querySelectorAll('.dot');
        dots.forEach((dot, idx) => {
            dot.style.background = idx === targetIndex ? '#667eea' : '#e9d5ff';
        });
    }

    createSidebarBookCard(book, index) {
        const similarity = book.similarity_score ? `${(book.similarity_score * 100).toFixed(0)}%` : '';
        const price = book.price || 'N/A';
        const reason = book.recommendation_reason || '推薦閱讀';
        
        return `
            <div class="sidebar-book-card" style="
                background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                transition: all 0.2s ease;
                cursor: pointer;
                position: relative;
            " onclick="window.open('${book.url}', '_blank')"
               onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.15)'"
               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 1px 3px rgba(0,0,0,0.1)'">
               
                ${similarity ? `
                    <div style="
                        position: absolute;
                        top: 8px;
                        right: 8px;
                        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                        color: white;
                        padding: 2px 6px;
                        border-radius: 8px;
                        font-size: 0.65rem;
                        font-weight: 600;
                    ">${similarity}</div>
                ` : ''}
                
                <div class="book-title" style="
                    font-weight: 600;
                    color: #1f2937;
                    font-size: 0.85rem;
                    line-height: 1.3;
                    margin-bottom: 4px;
                    margin-right: 30px;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                ">${this.escapeHtml(book.title)}</div>
                
                <div class="book-author" style="
                    color: #6b7280;
                    font-size: 0.75rem;
                    margin-bottom: 6px;
                ">${this.escapeHtml(book.author || '聖嚴法師')}</div>
                
                <div class="book-reason" style="
                    background: rgba(102, 126, 234, 0.1);
                    color: #667eea;
                    padding: 3px 6px;
                    border-radius: 4px;
                    font-size: 0.65rem;
                    font-weight: 500;
                    margin-bottom: 6px;
                    border-left: 2px solid #667eea;
                ">${this.escapeHtml(reason)}</div>
                
                <div class="book-footer" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-size: 0.75rem;
                ">
                    <div style="color: #059669; font-weight: 600;">${this.escapeHtml(price)}</div>
                    <div style="color: #667eea; font-weight: 500;">查看詳情 →</div>
                </div>
            </div>
        `;
    }

    createBookCard(book, index) {
        const similarity = book.similarity_score ? `${(book.similarity_score * 100).toFixed(0)}%` : '';
        const price = book.price || 'N/A';
        const reason = book.recommendation_reason || '推薦閱讀';
        
        return `
            <div class="book-card" style="
                min-width: 220px;
                max-width: 220px;
                background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: all 0.3s ease;
                cursor: pointer;
                position: relative;
                overflow: hidden;
            " onclick="window.open('${book.url}', '_blank')"
               onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.15)'"
               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'">
               
                ${similarity ? `
                    <div style="
                        position: absolute;
                        top: 12px;
                        right: 12px;
                        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                        color: white;
                        padding: 4px 8px;
                        border-radius: 12px;
                        font-size: 0.7rem;
                        font-weight: 600;
                    ">${similarity}</div>
                ` : ''}
                
                <div class="book-header" style="margin-bottom: 12px;">
                    <div class="book-title" style="
                        font-weight: 600;
                        color: #1f2937;
                        font-size: 0.9rem;
                        line-height: 1.3;
                        margin-bottom: 6px;
                        display: -webkit-box;
                        -webkit-line-clamp: 2;
                        -webkit-box-orient: vertical;
                        overflow: hidden;
                    ">${this.escapeHtml(book.title)}</div>
                    
                    <div class="book-author" style="
                        color: #6b7280;
                        font-size: 0.8rem;
                        font-weight: 500;
                    ">${this.escapeHtml(book.author || '聖嚴法師')}</div>
                </div>
                
                <div class="book-content" style="margin-bottom: 12px;">
                    <div class="book-description" style="
                        color: #4b5563;
                        font-size: 0.75rem;
                        line-height: 1.4;
                        display: -webkit-box;
                        -webkit-line-clamp: 3;
                        -webkit-box-orient: vertical;
                        overflow: hidden;
                        margin-bottom: 8px;
                    ">${this.escapeHtml(book.content_introduction ? book.content_introduction.substring(0, 100) + '...' : '')}</div>
                    
                    <div class="recommendation-reason" style="
                        background: rgba(102, 126, 234, 0.1);
                        color: #667eea;
                        padding: 4px 8px;
                        border-radius: 6px;
                        font-size: 0.7rem;
                        font-weight: 500;
                        border-left: 3px solid #667eea;
                    ">${this.escapeHtml(reason)}</div>
                </div>
                
                <div class="book-footer" style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding-top: 8px;
                    border-top: 1px solid #f3f4f6;
                ">
                    <div class="book-price" style="
                        font-weight: 600;
                        color: #059669;
                        font-size: 0.85rem;
                    ">${this.escapeHtml(price)}</div>
                    
                    <div class="book-action" style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 4px 8px;
                        border-radius: 6px;
                        font-size: 0.7rem;
                        font-weight: 500;
                    ">查看詳情</div>
                </div>
            </div>
        `;
    }

    async getBookRecommendations(query) {
        try {
            const response = await fetch(`${API_BASE_URL}/books/recommend`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    top_k: 6,
                    min_similarity: 0.05
                })
            });

            if (!response.ok) {
                console.warn('Book recommendations not available');
                return [];
            }

            const data = await response.json();
            return data.recommendations || [];

        } catch (error) {
            console.warn('Error fetching book recommendations:', error);
            return [];
        }
    }
    
    async getRelatedQueries(query) {
        console.log('🔍 Fetching related queries for:', query);
        try {
            const response = await fetch(`${API_BASE_URL}/queries/related`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    top_k: 3,
                    min_similarity: 0.1
                })
            });

            if (!response.ok) {
                console.warn('Related queries not available');
                return [];
            }

            const data = await response.json();
            console.log('📝 Related queries received:', data.related_queries);
            return data.related_queries || [];

        } catch (error) {
            console.warn('Error fetching related queries:', error);
            return [];
        }
    }

    getMockVideoData() {
        // Mock video data for demonstration
        return {
            title: "聖嚴法師：禪修的基本方法與實踐",
            cover: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='280' height='140' fill='%23374151'%3E%3Crect width='280' height='140'/%3E%3Ctext x='50%25' y='50%25' fill='white' text-anchor='middle' dy='.3em' font-size='14' font-family='sans-serif'%3E禪修教學影片%3C/text%3E%3C/svg%3E",
            src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
            duration: "46:32",
            description: "聖嚴法師親自講解禪修的基本方法，包括坐禪姿勢、呼吸調節、心念專注等核心要點，適合初學者學習。",
            channel: "法鼓山頻道",
            similarity_score: 0.85,
            chunk_id: "video_zen_meditation_basic_methods",
            type: "video"
        };
    }

    createVideoReference(videoData) {
        if (!videoData) return '';
        
        const similarity = `${(videoData.similarity_score * 100).toFixed(0)}%`;
        
        return `
            <div class="video-reference" onclick="window.ragApp.playVideo('${videoData.src}', '${this.escapeHtml(videoData.title)}')">
                <div class="video-cover" style="background-image: url('${videoData.cover}')">
                    <div class="video-play-btn">
                        <span>▶</span>
                    </div>
                    <div class="video-duration">${videoData.duration}</div>
                </div>
                
                <div class="video-meta">
                    <div class="video-type">VIDEO</div>
                    <div class="video-similarity">${similarity}</div>
                </div>
                
                <div class="video-title">${this.escapeHtml(videoData.title)}</div>
                
                <div class="video-description">
                    ${this.escapeHtml(videoData.description)}
                </div>
                
                <div class="video-footer">
                    <div class="video-channel">${this.escapeHtml(videoData.channel)}</div>
                    <div class="video-action">🎬 播放</div>
                </div>
            </div>
        `;
    }

    playVideo(src, title) {
        const modal = document.createElement('div');
        modal.className = 'video-modal';
        modal.id = 'video-modal';
        
        modal.innerHTML = `
            <div class="video-modal-content">
                <button class="video-modal-close" onclick="window.ragApp.closeVideoModal()">✕</button>
                <video controls autoplay style="max-width: 800px; max-height: 600px;">
                    <source src="${src}" type="video/mp4">
                    <p>Your browser does not support the video tag.</p>
                </video>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeVideoModal();
            }
        });
        
        // Close on Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                this.closeVideoModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    closeVideoModal() {
        const modal = document.getElementById('video-modal');
        if (modal) {
            // Pause the video before removing
            const video = modal.querySelector('video');
            if (video) {
                video.pause();
            }
            
            modal.remove();
            document.body.style.overflow = 'auto';
        }
    }

    getMockAudioData() {
        // Mock audio data for demonstration
        return {
            title: "聖嚴法師開示：心靈環保的重要性",
            src: "https://commondatastorage.googleapis.com/codeskulptor-assets/Epoq-Lepidoptera.ogg",
            duration: "18:45",
            description: "聖嚴法師深入淺出地解釋心靈環保的概念，如何在日常生活中實踐內心的清淨與平靜。",
            speaker: "聖嚴法師",
            similarity_score: 0.78,
            chunk_id: "audio_environmental_protection_mind",
            type: "audio"
        };
    }

    createAudioReference(audioData) {
        if (!audioData) return '';
        
        const similarity = `${(audioData.similarity_score * 100).toFixed(0)}%`;
        
        // Generate waveform bars
        const waveformBars = Array.from({length: 15}, (_, i) => 
            `<div class="waveform-bar"></div>`
        ).join('');
        
        return `
            <div class="audio-reference" onclick="window.ragApp.playAudio('${audioData.src}', '${this.escapeHtml(audioData.title)}')">
                <div class="audio-waveform">
                    <div class="waveform-bars">
                        ${waveformBars}
                    </div>
                    <div class="audio-play-btn">
                        <span>▶</span>
                    </div>
                    <div class="audio-duration">${audioData.duration}</div>
                </div>
                
                <div class="audio-meta">
                    <div class="audio-type">AUDIO</div>
                    <div class="audio-similarity">${similarity}</div>
                </div>
                
                <div class="audio-title">${this.escapeHtml(audioData.title)}</div>
                
                <div class="audio-description">
                    ${this.escapeHtml(audioData.description)}
                </div>
                
                <div class="audio-footer">
                    <div class="audio-speaker">${this.escapeHtml(audioData.speaker)}</div>
                    <div class="audio-action">🎧 收聽</div>
                </div>
            </div>
        `;
    }
    
    createAudioReferenceFromData(source) {
        if (!source || !source.metadata) return '';
        
        const metadata = source.metadata;
        const similarity = source.similarity_score ? 
            `${(source.similarity_score * 100).toFixed(0)}%` : '85%';
        
        // Generate waveform bars
        const waveformBars = Array.from({length: 15}, (_, i) => 
            `<div class="waveform-bar"></div>`
        ).join('');
        
        // Extract relevant content excerpt
        const excerpt = source.content ? 
            source.content.substring(0, 150) + '...' : 
            '點擊收聽完整音頻內容';
        
        // Format timestamp if available
        const timeRange = metadata.timestamp_start && metadata.timestamp_end ? 
            `${metadata.timestamp_start} - ${metadata.timestamp_end}` : 
            '完整音頻';
        
        return `
            <div class="audio-reference" onclick="window.ragApp.playAudio('${metadata.audio_url}', '${this.escapeHtml(metadata.audio_title)}')">
                <div class="audio-waveform">
                    <div class="waveform-bars">
                        ${waveformBars}
                    </div>
                    <div class="audio-play-btn">
                        <span>▶</span>
                    </div>
                    <div class="audio-duration">${timeRange}</div>
                </div>
                
                <div class="audio-meta">
                    <div class="audio-type">${metadata.section || 'AUDIO'}</div>
                    <div class="audio-similarity">${similarity}</div>
                </div>
                
                <div class="audio-title">${this.escapeHtml(metadata.audio_title)}</div>
                
                <div class="audio-description">
                    ${this.escapeHtml(excerpt)}
                </div>
                
                <div class="audio-footer">
                    <div class="audio-speaker">${metadata.speaker || '聖嚴法師'}</div>
                    <div class="audio-action">🎧 收聽</div>
                </div>
            </div>
        `;
    }
    
    createVideoReferenceFromData(source) {
        // Placeholder for future video implementation
        return '';
    }

    playAudio(src, title) {
        const modal = document.createElement('div');
        modal.className = 'audio-modal';
        modal.id = 'audio-modal';
        
        // Generate larger waveform for modal
        const modalWaveformBars = Array.from({length: 25}, (_, i) => {
            const heights = [20, 40, 60, 80, 100, 70, 90, 45, 65, 35, 75, 55, 85, 25, 45, 60, 30, 50, 70, 40, 80, 35, 95, 25, 55];
            return `<div class="modal-waveform-bar" style="height: ${heights[i] || 50}%; animation-delay: ${i * 0.1}s;"></div>`;
        }).join('');
        
        modal.innerHTML = `
            <div class="audio-modal-content">
                <button class="audio-modal-close" onclick="window.ragApp.closeAudioModal()">✕</button>
                
                <div class="audio-modal-title">${this.escapeHtml(title)}</div>
                
                <div class="audio-modal-waveform">
                    <div class="modal-waveform-bars">
                        ${modalWaveformBars}
                    </div>
                </div>
                
                <audio controls autoplay style="width: 100%; margin: 16px 0;">
                    <source src="${src}" type="audio/mpeg">
                    <source src="${src}" type="audio/mp3">
                    <p>Your browser does not support the audio element.</p>
                </audio>
                
                <div style="text-align: center; margin-top: 16px; font-size: 0.9rem; opacity: 0.8;">
                    🎧 請使用音頻控制器播放、暫停和調節音量
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeAudioModal();
            }
        });
        
        // Close on Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                this.closeAudioModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    closeAudioModal() {
        const modal = document.getElementById('audio-modal');
        if (modal) {
            // Pause the audio before removing
            const audio = modal.querySelector('audio');
            if (audio) {
                audio.pause();
            }
            
            modal.remove();
            document.body.style.overflow = 'auto';
        }
    }

    async loadEventRecommendations() {
        console.log('🏮 loadEventRecommendations called, lastUserMessage:', this.lastUserMessage);
        if (!this.lastUserMessage) {
            console.log('🏮 No lastUserMessage, returning early');
            return;
        }
        
        try {
            console.log('🏮 Fetching event recommendations for:', this.lastUserMessage);
            
            const response = await fetch(`${API_BASE_URL}/events/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: this.lastUserMessage,
                    top_k: 6,
                    min_similarity: 0.05,  // Lower threshold for philosophical queries
                    upcoming_only: true
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('🏮 Event recommendations received:', data);
                console.log('🏮 Number of events:', data.count);
                this.showEventRecommendations(data.recommendations);
            } else {
                console.error('Failed to fetch event recommendations:', response.status, response.statusText);
            }
        } catch (error) {
            console.warn('Error fetching event recommendations:', error);
        }
    }

    showEventRecommendations(events) {
        const container = document.getElementById('event-recommendations');
        if (!container) {
            console.error('🏮 Event recommendations container not found!');
            return;
        }
        
        console.log('🏮 Showing', events?.length || 0, 'events');
        
        if (!events || events.length === 0) {
            container.innerHTML = '<div class="sidebar-empty">No upcoming events found for this topic</div>';
            return;
        }
        
        // Store events for modal access
        this.currentEvents = events;
        
        console.log('🏮 Creating event carousel with events:', events);
        container.innerHTML = this.createEventCarousel(events);
    }

    createEventCarousel(events) {
        if (!events || events.length === 0) return '';
        
        const carouselId = 'event-carousel-' + Date.now();
        
        return `
            <div class="event-carousel-container" style="position: relative;">
                <div id="${carouselId}" class="source-carousel" style="
                    display: flex;
                    overflow-x: auto;
                    scroll-behavior: smooth;
                    gap: 12px;
                    padding: 8px 0;
                    scrollbar-width: none;
                    -ms-overflow-style: none;
                ">
                    ${events.map((event, index) => this.createEventCard(event, index)).join('')}
                </div>
                
                ${events.length > 1 ? `
                    <button class="carousel-nav carousel-prev" style="
                        position: absolute;
                        left: -8px;
                        top: 50%;
                        transform: translateY(-50%);
                        background: rgba(124, 58, 237, 0.8);
                        color: white;
                        border: none;
                        border-radius: 50%;
                        width: 24px;
                        height: 24px;
                        cursor: pointer;
                        font-size: 12px;
                        z-index: 10;
                        backdrop-filter: blur(10px);
                    " onclick="window.ragApp.scrollCarousel('${carouselId}', -300)">‹</button>
                    
                    <button class="carousel-nav carousel-next" style="
                        position: absolute;
                        right: -8px;
                        top: 50%;
                        transform: translateY(-50%);
                        background: rgba(124, 58, 237, 0.8);
                        color: white;
                        border: none;
                        border-radius: 50%;
                        width: 24px;
                        height: 24px;
                        cursor: pointer;
                        font-size: 12px;
                        z-index: 10;
                        backdrop-filter: blur(10px);
                    " onclick="window.ragApp.scrollCarousel('${carouselId}', 300)">›</button>
                ` : ''}
            </div>
        `;
    }

    createEventCard(event, index) {
        if (!event) return '';
        
        console.log('🔧 Creating event card', index + 1, 'for event:', event.title);
        
        const similarity = `${(event.similarity_score * 100).toFixed(0)}%`;
        const isUpcoming = event.is_upcoming;
        const location = event.location.length > 30 ? event.location.substring(0, 30) + '...' : event.location;
        
        // Format date for display
        let dateDisplay = event.date_range;
        if (event.start_date && event.end_date) {
            const start = new Date(event.start_date);
            const end = new Date(event.end_date);
            if (start.getTime() === end.getTime()) {
                dateDisplay = start.toLocaleDateString('zh-TW');
            } else {
                dateDisplay = `${start.toLocaleDateString('zh-TW')} - ${end.toLocaleDateString('zh-TW')}`;
            }
        }
        
        return `
            <div class="event-reference" onclick="window.ragApp.showEventModal(${index})">
                <div class="event-header">
                    <div class="event-type">${this.escapeHtml(event.event_type)}</div>
                    <div class="event-similarity">${similarity}</div>
                </div>
                
                <div class="event-title">${this.escapeHtml(event.title)}</div>
                
                <div class="event-date-location">
                    <div class="event-date">
                        <span>📅</span> ${this.escapeHtml(dateDisplay)}
                    </div>
                    <div class="event-location">
                        <span>📍</span> ${this.escapeHtml(location)}
                    </div>
                </div>
                
                <div class="event-organizer">
                    ${this.escapeHtml(event.organizer)}
                </div>
                
                <div class="event-description">
                    ${this.escapeHtml(event.description || '詳細資訊請參考活動頁面')}
                </div>
                
                <div class="event-footer">
                    <div class="event-status ${isUpcoming ? 'upcoming' : ''}">
                        <span>${isUpcoming ? '🟢' : '🔴'}</span>
                        ${isUpcoming ? '即將開始' : '已結束'}
                    </div>
                    <div class="event-action">📅 查看詳情</div>
                </div>
            </div>
        `;
    }

    showEventModal(eventIndex) {
        if (!this.currentEvents || !this.currentEvents[eventIndex]) {
            console.error('Event not found for index:', eventIndex);
            return;
        }
        const eventData = this.currentEvents[eventIndex];
        
        const modal = document.createElement('div');
        modal.className = 'event-modal';
        modal.id = 'event-modal';
        
        // Format date for display
        let dateDisplay = eventData.date_range;
        if (eventData.start_date && eventData.end_date) {
            const start = new Date(eventData.start_date);
            const end = new Date(eventData.end_date);
            if (start.getTime() === end.getTime()) {
                dateDisplay = start.toLocaleDateString('zh-TW');
            } else {
                dateDisplay = `${start.toLocaleDateString('zh-TW')} - ${end.toLocaleDateString('zh-TW')}`;
            }
        }
        
        modal.innerHTML = `
            <div class="event-modal-content">
                <button class="event-modal-close" onclick="window.ragApp.closeEventModal()">✕</button>
                
                <div class="event-modal-title">${this.escapeHtml(eventData.title)}</div>
                
                <div class="event-modal-details">
                    <div class="event-detail-item">
                        <div class="event-detail-label">活動日期</div>
                        <div class="event-detail-value">${this.escapeHtml(dateDisplay)}</div>
                    </div>
                    <div class="event-detail-item">
                        <div class="event-detail-label">活動時間</div>
                        <div class="event-detail-value">${this.escapeHtml(eventData.time_range || '請參考官網')}</div>
                    </div>
                    <div class="event-detail-item">
                        <div class="event-detail-label">主辦單位</div>
                        <div class="event-detail-value">${this.escapeHtml(eventData.organizer)}</div>
                    </div>
                    <div class="event-detail-item">
                        <div class="event-detail-label">活動對象</div>
                        <div class="event-detail-value">${this.escapeHtml(eventData.target_audience)}</div>
                    </div>
                </div>
                
                <div class="event-detail-item" style="margin-bottom: 16px;">
                    <div class="event-detail-label">活動地點</div>
                    <div class="event-detail-value">${this.escapeHtml(eventData.location)}</div>
                </div>
                
                ${eventData.description ? `
                <div class="event-modal-description">
                    <div class="event-detail-label" style="margin-bottom: 8px;">活動內容</div>
                    ${this.escapeHtml(eventData.description)}
                </div>
                ` : ''}
                
                <div class="event-modal-actions">
                    ${eventData.website ? `
                        <a href="${eventData.website}" target="_blank" class="event-modal-btn primary">
                            🌐 官方網站
                        </a>
                    ` : ''}
                    <button class="event-modal-btn secondary" onclick="window.ragApp.closeEventModal()">
                        關閉
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        document.body.style.overflow = 'hidden';
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeEventModal();
            }
        });
        
        // Close on Escape key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                this.closeEventModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    closeEventModal() {
        const modal = document.getElementById('event-modal');
        if (modal) {
            modal.remove();
            document.body.style.overflow = 'auto';
        }
    }

    scrollCarousel(carouselId, scrollAmount) {
        const carousel = document.getElementById(carouselId);
        if (carousel) {
            carousel.scrollBy({
                left: scrollAmount,
                behavior: 'smooth'
            });
        }
    }

    async loadAudioRecommendations() {
        console.log('🎧 loadAudioRecommendations called, lastUserMessage:', this.lastUserMessage);
        if (!this.lastUserMessage || !this.lastAnswer) {
            console.log('🎧 No lastUserMessage or lastAnswer, returning early');
            return;
        }
        
        try {
            console.log('🎧 Fetching audio recommendations for:', this.lastUserMessage);
            
            const queryAndAnswer = `${this.lastUserMessage} ${this.lastAnswer}`;
            const response = await fetch(`${API_BASE_URL}/audio/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query_and_answer: queryAndAnswer,
                    top_k: 3,
                    min_similarity: 0.05
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('🎧 Audio recommendations received:', data);
                console.log('🎧 Number of audio chunks:', data.count);
                this.showAudioRecommendations(data.recommendations);
            } else {
                console.error('Failed to fetch audio recommendations:', response.status, response.statusText);
            }
        } catch (error) {
            console.warn('Error fetching audio recommendations:', error);
        }
    }

    showAudioRecommendations(audioChunks) {
        const container = document.getElementById('audio-recommendations');
        if (!container) {
            console.error('🎧 Audio recommendations container not found!');
            return;
        }
        
        console.log('🎧 Showing', audioChunks?.length || 0, 'audio chunks');
        
        if (!audioChunks || audioChunks.length === 0) {
            container.innerHTML = '<div class="sidebar-empty">No related audio teachings found</div>';
            return;
        }
        
        // Store audio chunks for modal access
        this.currentAudioChunks = audioChunks;
        
        console.log('🎧 Creating audio carousel with chunks:', audioChunks);
        container.innerHTML = this.createAudioCarousel(audioChunks);
        
        // Clear blur effects on audio recommendations with smooth transition
        setTimeout(() => {
            const audioRecommendations = this.audioRecommendations;
            if (audioRecommendations) {
                audioRecommendations.style.filter = 'none';
                audioRecommendations.style.opacity = '1';
                audioRecommendations.style.pointerEvents = 'auto';
                
                // Remove loading indicator
                const loadingText = audioRecommendations.querySelector('.recommendation-loading');
                if (loadingText) {
                    loadingText.style.opacity = '0';
                    setTimeout(() => loadingText.remove(), 200);
                }
            }
        }, 450); // Slightly longer delay for audio recommendations
    }

    createAudioCarousel(audioChunks) {
        if (!audioChunks || audioChunks.length === 0) return '';
        
        const carouselId = 'audio-carousel-' + Date.now();
        
        return `
            <div class="audio-carousel-container" style="position: relative;">
                <div id="${carouselId}" class="source-carousel" style="
                    display: flex;
                    overflow-x: auto;
                    scroll-behavior: smooth;
                    gap: 12px;
                    padding: 8px 0;
                    scrollbar-width: none;
                    -ms-overflow-style: none;
                ">
                    ${audioChunks.map((audio, index) => this.createAudioCard(audio, index)).join('')}
                </div>
                
                ${audioChunks.length > 1 ? `
                    <button class="carousel-nav carousel-prev" style="
                        position: absolute;
                        left: -8px;
                        top: 50%;
                        transform: translateY(-50%);
                        background: rgba(255, 255, 255, 0.9);
                        border: 1px solid #e5e7eb;
                        border-radius: 50%;
                        width: 30px;
                        height: 30px;
                        cursor: pointer;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        z-index: 2;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: #6b7280;
                        font-size: 14px;
                        font-weight: bold;
                    " onclick="window.ragApp.scrollCarousel('${carouselId}', -200)">❮</button>
                    
                    <button class="carousel-nav carousel-next" style="
                        position: absolute;
                        right: -8px;
                        top: 50%;
                        transform: translateY(-50%);
                        background: rgba(255, 255, 255, 0.9);
                        border: 1px solid #e5e7eb;
                        border-radius: 50%;
                        width: 30px;
                        height: 30px;
                        cursor: pointer;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        z-index: 2;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: #6b7280;
                        font-size: 14px;
                        font-weight: bold;
                    " onclick="window.ragApp.scrollCarousel('${carouselId}', 200)">❯</button>
                ` : ''}
            </div>
        `;
    }

    createAudioCard(audio, index) {
        if (!audio) return '';
        
        console.log('🔧 Creating audio card', index + 1, 'for audio:', audio.audio_title);
        
        const similarity = `${(audio.similarity_score * 100).toFixed(0)}%`;
        const timestamp = audio.timestamp_start && audio.timestamp_end ? 
            `${audio.timestamp_start} - ${audio.timestamp_end}` : '';
        
        return `
            <div class="audio-reference" 
                 onclick="window.ragApp.showAudioModal('${audio.id}')"
                 style="min-width: 280px; cursor: pointer;">
                
                <div class="audio-waveform">
                    <div class="waveform-bars">
                        ${Array.from({length: 15}, (_, i) => `<div class="waveform-bar"></div>`).join('')}
                    </div>
                    <div class="audio-play-btn">▶</div>
                    ${timestamp ? `<div class="audio-duration">${timestamp}</div>` : ''}
                </div>
                
                <div class="audio-meta">
                    <div class="audio-type">音聲</div>
                    <div class="audio-similarity">${similarity}</div>
                </div>
                
                <div class="audio-title">${this.escapeHtml(audio.audio_title)}</div>
                
                <div class="audio-description">${this.escapeHtml(audio.content.substring(0, 100))}...</div>
                
                <div class="audio-footer">
                    <div class="audio-speaker">${this.escapeHtml(audio.speaker)}</div>
                    <div class="audio-action">聆聽</div>
                </div>
            </div>
        `;
    }

    // Helper function to convert MM:SS time format to seconds
    timeToSeconds(timeStr) {
        if (!timeStr) return 0;
        const parts = timeStr.split(':');
        if (parts.length === 2) {
            return parseInt(parts[0]) * 60 + parseInt(parts[1]);
        }
        return 0;
    }

    showAudioModal(audioId) {
        const audioData = this.currentAudioChunks?.find(a => a.id === audioId);
        if (!audioData) {
            console.error('Audio data not found for ID:', audioId);
            return;
        }
        
        // Create modal
        const modal = document.createElement('div');
        modal.id = 'audio-modal';
        modal.className = 'audio-modal';
        modal.style.display = 'flex';
        
        modal.innerHTML = `
            <div class="audio-modal-content">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div class="audio-modal-title" style="margin: 0;">${this.escapeHtml(audioData.audio_title)}</div>
                    <button class="audio-modal-close" onclick="window.ragApp.closeAudioModal()" 
                            onmouseover="this.style.background='rgba(255, 255, 255, 0.4)'; this.style.transform='scale(1.1)'" 
                            onmouseout="this.style.background='rgba(255, 255, 255, 0.2)'; this.style.transform='scale(1)'" 
                            style="
                        position: static;
                        background: rgba(255, 255, 255, 0.2);
                        color: white;
                        border: none;
                        border-radius: 50%;
                        width: 30px;
                        height: 30px;
                        cursor: pointer;
                        font-size: 16px;
                        font-weight: bold;
                        backdrop-filter: blur(10px);
                        transition: all 0.2s ease;
                        flex-shrink: 0;
                    ">✕</button>
                </div>
                
                <div class="audio-modal-waveform">
                    <div class="modal-waveform-bars">
                        ${Array.from({length: 20}, (_, i) => `<div class="modal-waveform-bar" style="height: ${Math.random() * 80 + 20}%;"></div>`).join('')}
                    </div>
                </div>
                
                ${audioData.audio_url ? `
                    <audio id="audio-player-${audioData.id}" controls style="width: 100%; margin: 16px 0;" preload="metadata">
                        <source src="${audioData.audio_url}" type="audio/mpeg">
                        您的瀏覽器不支援音頻播放。
                    </audio>
                ` : ''}
                
                <div style="background: rgba(0, 0, 0, 0.2); padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <div style="font-size: 0.9rem; margin-bottom: 8px;"><strong>講者:</strong> ${this.escapeHtml(audioData.speaker)}</div>
                    <div style="font-size: 0.9rem; margin-bottom: 8px;"><strong>章節:</strong> ${this.escapeHtml(audioData.section)}</div>
                    ${audioData.timestamp_start && audioData.timestamp_end ? `
                        <div style="font-size: 0.9rem;"><strong>時間:</strong> ${audioData.timestamp_start} - ${audioData.timestamp_end}</div>
                    ` : ''}
                </div>
                
                <div style="background: rgba(0, 0, 0, 0.2); padding: 16px; border-radius: 8px; line-height: 1.6;">
                    ${this.escapeHtml(audioData.content)}
                </div>
                
                ${audioData.audio_url ? `
                    <div style="text-align: center; margin-top: 16px;">
                        <a href="${audioData.audio_url}" target="_blank" style="
                            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                            color: white;
                            padding: 8px 16px;
                            border-radius: 8px;
                            text-decoration: none;
                            font-weight: 500;
                        ">開啟原始音頻</a>
                    </div>
                ` : ''}
            </div>
        `;
        
        document.body.appendChild(modal);
        document.body.style.overflow = 'hidden';
        
        // Set audio current time to the start timestamp
        if (audioData.audio_url && audioData.timestamp_start) {
            const audioPlayer = document.getElementById(`audio-player-${audioData.id}`);
            if (audioPlayer) {
                const startSeconds = this.timeToSeconds(audioData.timestamp_start);
                const endSeconds = this.timeToSeconds(audioData.timestamp_end);
                
                // Wait for audio metadata to load before setting current time
                audioPlayer.addEventListener('loadedmetadata', () => {
                    audioPlayer.currentTime = startSeconds;
                    console.log(`🎧 Set audio start time to ${startSeconds}s (${audioData.timestamp_start})`);
                });
                
                // Optional: Auto-pause at end time (comment out if not desired)
                if (endSeconds > startSeconds) {
                    audioPlayer.addEventListener('timeupdate', () => {
                        if (audioPlayer.currentTime >= endSeconds) {
                            audioPlayer.pause();
                            console.log(`🎧 Auto-paused at end time ${endSeconds}s (${audioData.timestamp_end})`);
                        }
                    });
                }
            }
        }
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeAudioModal();
            }
        });
        
        // Close on ESC key
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                this.closeAudioModal();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    closeAudioModal() {
        const modal = document.getElementById('audio-modal');
        if (modal) {
            modal.remove();
            document.body.style.overflow = 'auto';
        }
    }


    async summarizeLastAnswer() {
        const messages = document.querySelectorAll('.message-assistant .message-content');
        if (messages.length === 0) {
            alert('還沒有任何回答可以摘要\nNo answer available to summarize');
            return;
        }
        
        const lastMessage = messages[messages.length - 1];
        const originalText = lastMessage.textContent.trim();
        
        if (!originalText) {
            alert('沒有找到可摘要的內容\nNo content found to summarize');
            return;
        }
        
        // Check if already summarized
        if (lastMessage.querySelector('.summary-bubble')) {
            alert('已經摘要過了 / Already summarized');
            return;
        }

        // Store original HTML for restoration on error
        const originalHTML = lastMessage.innerHTML;
        
        // Create typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.innerHTML = `
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
            <span class="typing-text">正在生成摘要 Generating summary...</span>
        `;
        
        // Add typing indicator after the message
        lastMessage.appendChild(typingIndicator);
        
        try {
            const response = await fetch(`${API_BASE_URL}/summarize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: '', // Empty to use cached result from last query
                    max_length: 300
                })
            });
            
            if (!response.ok) {
                throw new Error('Summarization failed');
            }
            
            const data = await response.json();
            
            // Remove typing indicator with smooth animation
            typingIndicator.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                if (typingIndicator && typingIndicator.parentNode) {
                    typingIndicator.remove();
                }
            }, 300);
            
            // Create summary bubble with slight delay for smooth transition
            setTimeout(() => {
                const summaryBubble = document.createElement('div');
                summaryBubble.className = 'summary-bubble';
                summaryBubble.innerHTML = `
                    <div class="summary-bubble-header">
                        📝 摘要 Summary
                        ${data.computation_time ? `<span style="font-size: 0.8rem; opacity: 0.8;">(${data.computation_time.toFixed(1)}s)</span>` : ''}
                    </div>
                    <div class="summary-bubble-content">
                        ${data.summary.replace(/\n/g, '<br>')}
                    </div>
                `;
                
                // Add summary bubble after the original message
                lastMessage.appendChild(summaryBubble);
            }, 350);
            
        } catch (error) {
            console.error('Summarization error:', error);
            
            // Remove typing indicator
            if (typingIndicator && typingIndicator.parentNode) {
                typingIndicator.remove();
            }
            
            // Restore original content
            lastMessage.innerHTML = originalHTML;
            
            // Show error message
            const errorMsg = document.createElement('div');
            errorMsg.style.cssText = 'color: #ef4444; margin-top: 10px; font-size: 0.9rem;';
            errorMsg.textContent = '❌ 摘要失敗 Summarization failed. Please try again.';
            lastMessage.appendChild(errorMsg);
        }
    }
}

// Global function for showing auth modal
function showAuthModal() {
    // Mock login functionality
    const isLoggedIn = localStorage.getItem('mockUserLoggedIn') === 'true';
    
    if (isLoggedIn) {
        // User is logged in, show logout option
        const shouldLogout = confirm('您已登入\nYou are logged in\n\n點擊確定登出\nClick OK to logout');
        if (shouldLogout) {
            localStorage.setItem('mockUserLoggedIn', 'false');
            localStorage.removeItem('mockUserName');
            updateAuthButton();
            hidePracticeTab();
            alert('已登出\nLogged out successfully');
        }
    } else {
        // Mock login process
        const userName = prompt('模擬登入 Mock Login\n請輸入用戶名 Please enter username:', '禪修學員');
        if (userName && userName.trim()) {
            localStorage.setItem('mockUserLoggedIn', 'true');
            localStorage.setItem('mockUserName', userName.trim());
            updateAuthButton();
            showPracticeTab();
            alert(`歡迎 ${userName.trim()}！\nWelcome ${userName.trim()}!\n\n您現在可以查看修行歷程\nYou can now view your practice journey`);
        }
    }
}

// Update auth button text based on login status
function updateAuthButton() {
    const authButton = document.querySelector('.auth-button');
    const isLoggedIn = localStorage.getItem('mockUserLoggedIn') === 'true';
    const userName = localStorage.getItem('mockUserName') || 'User';
    
    if (authButton) {
        if (isLoggedIn) {
            authButton.textContent = `👤 ${userName}`;
        } else {
            authButton.textContent = '登入 / 註冊';
        }
    }
}

// Show practice tab when logged in
function showPracticeTab() {
    const practiceTab = document.getElementById('practice-tab');
    if (practiceTab) {
        practiceTab.classList.add('show');
    }
}

// Hide practice tab when logged out
function hidePracticeTab() {
    const practiceTab = document.getElementById('practice-tab');
    if (practiceTab) {
        practiceTab.classList.remove('show');
    }
}

// Show practice journey modal
function showPracticeJourney() {
    const modal = document.getElementById('practice-modal');
    if (modal) {
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
        
        // Load quiz history when modal opens
        loadQuizHistory();
    }
}

// Close practice journey modal
function closePracticeJourney() {
    const modal = document.getElementById('practice-modal');
    if (modal) {
        modal.classList.remove('show');
        document.body.style.overflow = 'auto';
    }
}

// Global function for handling popular query clicks
function askPopularQuery(query) {
    if (window.ragApp) {
        // Set the query in the input field
        const inputField = document.getElementById('query-input');
        if (inputField) {
            inputField.value = query;
        }
        
        // Trigger the query
        window.ragApp.sendQuery();
        
        // Hide the popular queries section after selection
        const popularQueries = document.querySelector('.popular-queries');
        if (popularQueries) {
            popularQueries.style.display = 'none';
        }
    }
}

// Global function for summarizing the last answer
function summarizeLastAnswer() {
    if (window.ragApp) {
        window.ragApp.summarizeLastAnswer();
    }
}

// Quiz functionality
let currentQuizData = null;
let currentQuestionIndex = 0;
let userAnswers = [];

function startQuiz() {
    // Show quiz modal
    const modal = document.getElementById('quiz-modal');
    modal.classList.add('show');
    
    // Reset quiz state
    currentQuizData = null;
    currentQuestionIndex = 0;
    userAnswers = [];
    
    // Show start screen
    document.getElementById('quiz-question').style.display = 'none';
    document.getElementById('quiz-result').style.display = 'none';
    document.getElementById('quiz-start').style.display = 'block';
    document.getElementById('quiz-submit').style.display = 'none';
    document.getElementById('quiz-next').style.display = 'none';
}

function closeQuiz() {
    const modal = document.getElementById('quiz-modal');
    modal.classList.remove('show');
}

async function generateQuiz() {
    try {
        // The backend will check if we have cached query results with sources
        // No need to check DOM elements here since the API handles the validation

        // Show loading indicator
        document.getElementById('quiz-start').innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
                <span class="typing-text">正在生成問題 Generating questions...</span>
            </div>
        `;

        // Call the new API to generate quiz
        const response = await fetch(`${API_BASE_URL}/quiz/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: localStorage.getItem('mockUserId') || 'anonymous'
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to generate quiz');
        }

        const quizData = await response.json();
        currentQuizData = quizData;
        currentQuestionIndex = 0;
        userAnswers = [];
        
        // Hide start button, show first question
        document.getElementById('quiz-start').style.display = 'none';
        showQuestion();
        
    } catch (error) {
        console.error('Error generating quiz:', error);
        
        // Restore start button on error
        document.getElementById('quiz-start').innerHTML = `
            <h3>🎯 智慧測驗 Wisdom Quiz</h3>
            <p>基於您最近的查詢，我們將生成個人化的佛法理解測驗</p>
            <p>Based on your recent query, we'll generate a personalized Buddhist understanding quiz</p>
            <button onclick="generateQuiz()" class="quiz-btn quiz-btn-primary">
                開始測驗 Start Quiz
            </button>
        `;
        
        alert('生成測驗時發生錯誤 / Error generating quiz: ' + error.message);
    }
}

function showQuestion() {
    if (!currentQuizData || currentQuestionIndex >= currentQuizData.questions.length) {
        submitAllAnswers();
        return;
    }
    
    const question = currentQuizData.questions[currentQuestionIndex];
    
    // Show question with reference information
    document.getElementById('question-text').innerHTML = `
        <div style="margin-bottom: 15px;">
            <h4>問題 ${currentQuestionIndex + 1}/${currentQuizData.questions.length}</h4>
            <p style="font-size: 1.1rem; line-height: 1.6; margin: 10px 0;">${question}</p>
        </div>
        <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea;">
            <p style="margin: 0; font-size: 0.9rem; color: #6b7280;">
                <strong>參考文本 Reference:</strong> ${currentQuizData.reference_chunk.title}
            </p>
            <details style="margin-top: 10px;">
                <summary style="cursor: pointer; color: #667eea; font-size: 0.9rem;">查看參考內容 View Reference Content</summary>
                <p style="margin: 10px 0 0 0; font-size: 0.85rem; color: #4b5563; line-height: 1.5;">
                    ${currentQuizData.reference_chunk.content}
                </p>
            </details>
        </div>
    `;
    
    // Replace options with text area
    const optionsContainer = document.getElementById('quiz-options');
    optionsContainer.innerHTML = `
        <div style="margin: 20px 0;">
            <label for="quiz-answer" style="display: block; margin-bottom: 8px; font-weight: 600; color: #374151;">
                請輸入您的答案 Please enter your answer:
            </label>
            <textarea 
                id="quiz-answer" 
                placeholder="請根據參考文本深入思考並回答這個問題..."
                style="width: 100%; min-height: 120px; padding: 12px; border: 2px solid #e5e7eb; border-radius: 8px; font-size: 1rem; line-height: 1.5; resize: vertical; font-family: inherit;"
                oninput="checkAnswerInput()"
            ></textarea>
            <div style="margin-top: 8px; font-size: 0.9rem; color: #6b7280;">
                提示：請用中文回答，分享您的理解和感想 (建議至少30字)
            </div>
        </div>
    `;
    
    // Show question section and submit button
    document.getElementById('quiz-question').style.display = 'block';
    document.getElementById('quiz-result').style.display = 'none';
    document.getElementById('quiz-submit').style.display = 'block';
    document.getElementById('quiz-submit').disabled = true;
    document.getElementById('quiz-next').style.display = 'none';
}

function checkAnswerInput() {
    const answer = document.getElementById('quiz-answer').value.trim();
    const submitBtn = document.getElementById('quiz-submit');
    
    // Enable submit if answer has at least 10 characters
    submitBtn.disabled = answer.length < 10;
}

function submitQuizAnswer() {
    const answer = document.getElementById('quiz-answer').value.trim();
    if (answer.length < 10) {
        alert('請提供更詳細的回答 (至少10個字) / Please provide a more detailed answer (at least 10 characters)');
        return;
    }
    
    // Store the answer
    userAnswers.push(answer);
    
    // Move to next question or submit all answers
    currentQuestionIndex++;
    if (currentQuestionIndex < currentQuizData.questions.length) {
        showQuestion();
    } else {
        submitAllAnswers();
    }
}

async function submitAllAnswers() {
    try {
        // Show evaluation loading
        document.getElementById('quiz-question').style.display = 'none';
        document.getElementById('quiz-result').style.display = 'block';
        document.getElementById('quiz-submit').style.display = 'none';
        document.getElementById('quiz-next').style.display = 'none';
        
        const resultTitle = document.getElementById('result-title');
        const explanation = document.getElementById('quiz-explanation');
        
        resultTitle.textContent = '評估中 Evaluating...';
        explanation.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
                <span class="typing-text">正在評估您的答案 Evaluating your answers...</span>
            </div>
        `;

        // Submit answers for evaluation
        const response = await fetch(`${API_BASE_URL}/quiz/evaluate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                quiz_id: currentQuizData.quiz_id,
                answers: userAnswers,
                user_id: localStorage.getItem('mockUserId') || 'anonymous'
            })
        });

        if (!response.ok) {
            throw new Error('Failed to evaluate answers');
        }

        const evaluationResult = await response.json();
        
        // Store quiz attempt in localStorage
        storeQuizAttempt(currentQuizData, userAnswers, evaluationResult);
        
        showEvaluationResults(evaluationResult);
        
    } catch (error) {
        console.error('Error evaluating answers:', error);
        
        const explanation = document.getElementById('quiz-explanation');
        explanation.innerHTML = `
            <div style="color: #dc2626; text-align: center; padding: 20px;">
                <p>評估過程中發生錯誤 / Error during evaluation</p>
                <button onclick="closeQuiz()" class="quiz-btn quiz-btn-secondary">關閉 Close</button>
            </div>
        `;
    }
}

function showEvaluationResults(evaluationResult) {
    const resultTitle = document.getElementById('result-title');
    const explanation = document.getElementById('quiz-explanation');
    
    resultTitle.textContent = '📝 評估結果 Evaluation Results';
    
    let resultHTML = `
        <div style="line-height: 1.6;">
            <div style="background: #f0f9ff; padding: 20px; border-radius: 12px; margin-bottom: 20px;">
                <h4 style="color: #0369a1; margin-bottom: 15px;">🎯 評估報告 Evaluation Report</h4>
                <div style="white-space: pre-line; color: #374151;">
                    ${evaluationResult.evaluation}
                </div>
            </div>
    `;
    
    // Add Zen master response if available
    if (evaluationResult.zen_master_response) {
        resultHTML += `
            <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 2px solid #f59e0b;">
                <h4 style="color: #b45309; margin-bottom: 15px;">🧘‍♂️ 禪師的話 Zen Master's Words</h4>
                <div style="color: #b45309; font-style: italic; font-size: 1.1rem;">
                    "${evaluationResult.zen_master_response}"
                </div>
            </div>
        `;
    }
    
    resultHTML += `
            <div style="text-align: center; margin-top: 25px;">
                <p style="color: #6b7280; margin-bottom: 20px;">您的答案已記錄在修行歷程中 / Your answers have been logged to your practice journey</p>
                <button onclick="closeQuiz()" class="quiz-btn quiz-btn-primary" style="margin-right: 10px;">
                    完成 Complete
                </button>
                <button onclick="restartQuiz()" class="quiz-btn quiz-btn-secondary">
                    重新測驗 Restart Quiz
                </button>
            </div>
        </div>
    `;
    
    explanation.innerHTML = resultHTML;
}

function restartQuiz() {
    closeQuiz();
    setTimeout(() => startQuiz(), 100);
}

// Quiz history storage and display functions
function storeQuizAttempt(quizData, answers, evaluation) {
    try {
        const userId = localStorage.getItem('mockUserId') || 'anonymous';
        const quizHistory = JSON.parse(localStorage.getItem(`quizHistory_${userId}`) || '[]');
        
        const quizAttempt = {
            id: quizData.quiz_id,
            timestamp: new Date().toISOString(),
            quiz_questions: quizData.questions,
            user_answers: answers,
            reference_chunk: quizData.reference_chunk,
            source_query: quizData.source_query,
            evaluation: evaluation.evaluation,
            zen_master_response: evaluation.zen_master_response,
            created_at: new Date().toLocaleString('zh-TW', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            })
        };
        
        // Add to beginning of array (most recent first)
        quizHistory.unshift(quizAttempt);
        
        // Keep only last 50 quiz attempts
        if (quizHistory.length > 50) {
            quizHistory.splice(50);
        }
        
        localStorage.setItem(`quizHistory_${userId}`, JSON.stringify(quizHistory));
        console.log('Quiz attempt stored successfully');
        
    } catch (error) {
        console.error('Error storing quiz attempt:', error);
    }
}

function loadQuizHistory() {
    try {
        const userId = localStorage.getItem('mockUserId') || 'anonymous';
        const quizHistory = JSON.parse(localStorage.getItem(`quizHistory_${userId}`) || '[]');
        
        const container = document.getElementById('quiz-history-container');
        if (!container) return;
        
        if (quizHistory.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; color: #6b7280; padding: 40px;">
                    <p>您還沒有參加過任何測驗</p>
                    <p>You haven't taken any quizzes yet</p>
                </div>
            `;
            return;
        }
        
        let historyHTML = '';
        quizHistory.forEach((attempt, index) => {
            const zenMasterSection = attempt.zen_master_response ? `
                <div class="quiz-zen-master">
                    <div class="quiz-zen-master-header">🧘‍♂️ 禪師的話 Zen Master's Words</div>
                    <div class="quiz-zen-master-text">"${attempt.zen_master_response}"</div>
                </div>
            ` : '';
            
            const questionsHTML = attempt.quiz_questions.map((question, qIndex) => `
                <div class="quiz-question-item">
                    <div class="quiz-question-text">問題${qIndex + 1}: ${question}</div>
                    <div class="quiz-answer-text">${attempt.user_answers[qIndex] || '未回答'}</div>
                </div>
            `).join('');
            
            historyHTML += `
                <div class="quiz-history-item">
                    <div class="quiz-history-header">
                        <div class="quiz-history-title">📝 測驗記錄 #${quizHistory.length - index}</div>
                        <div class="quiz-history-date">${attempt.created_at}</div>
                    </div>
                    
                    <div class="quiz-history-reference">
                        <div class="quiz-history-reference-title">參考文本: ${attempt.reference_chunk.title}</div>
                        <div style="font-size: 0.85rem; color: #6b7280;">查詢: ${attempt.source_query}</div>
                    </div>
                    
                    <div class="quiz-history-questions">
                        ${questionsHTML}
                    </div>
                    
                    <details style="margin-bottom: 15px;">
                        <summary style="cursor: pointer; color: #667eea; font-weight: 600; font-size: 0.9rem;">查看評估結果 View Evaluation</summary>
                        <div style="margin-top: 10px; padding: 15px; background: #f8fafc; border-radius: 8px; font-size: 0.9rem; line-height: 1.5; white-space: pre-line;">
                            ${attempt.evaluation}
                        </div>
                    </details>
                    
                    ${zenMasterSection}
                </div>
            `;
        });
        
        container.innerHTML = historyHTML;
        
    } catch (error) {
        console.error('Error loading quiz history:', error);
        const container = document.getElementById('quiz-history-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; color: #dc2626; padding: 40px;">
                    <p>載入測驗記錄時發生錯誤</p>
                    <p>Error loading quiz history</p>
                </div>
            `;
        }
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new RAGChatApp();
    
    // Initialize auth state and practice tab
    updateAuthButton();
    const isLoggedIn = localStorage.getItem('mockUserLoggedIn') === 'true';
    if (isLoggedIn) {
        showPracticeTab();
    }
});