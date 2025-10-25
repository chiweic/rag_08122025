// Get DOM elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

// Add event listener for send button
sendButton.addEventListener('click', sendMessage);

// Add event listener for Enter key
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Add event listeners for shortcut buttons
document.querySelectorAll('.shortcut-button').forEach(button => {
    button.addEventListener('click', () => {
        const question = button.getAttribute('data-question');
        sendPredefinedMessage(question);
    });
});

// Function to send user message
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessageToChat(message, 'user');
    
    // Clear input and disable button while processing
    userInput.value = '';
    sendButton.disabled = true;
    
    // Add streaming bot message placeholder
    const streamingMessageElement = addStreamingMessageToChat();
    
    try {
        // Call the RAG API
        await callRagApi(message, streamingMessageElement);
    } catch (error) {
        console.error('Error calling RAG API:', error);
        // Error message is now handled in callRagApi
    } finally {
        sendButton.disabled = false;
        userInput.focus();
    }
}

// Function to send predefined message
async function sendPredefinedMessage(question) {
    // Add user message to chat
    addMessageToChat(question, 'user');
    
    // Disable all buttons while processing
    sendButton.disabled = true;
    document.querySelectorAll('.shortcut-button').forEach(button => {
        button.disabled = true;
    });
    
    // Add streaming bot message placeholder
    const streamingMessageElement = addStreamingMessageToChat();
    
    try {
        // Call the RAG API
        await callRagApi(question, streamingMessageElement);
    } catch (error) {
        console.error('Error calling RAG API:', error);
        // Error message is now handled in callRagApi
    } finally {
        sendButton.disabled = false;
        document.querySelectorAll('.shortcut-button').forEach(button => {
            button.disabled = false;
        });
        userInput.focus();
    }
}

// Function to add a message to the chat
function addMessageToChat(content, sender) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    messageElement.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
    
    const contentElement = document.createElement('div');
    contentElement.classList.add('message-content');
    contentElement.textContent = content;
    
    messageElement.appendChild(contentElement);
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageElement;
}

// Function to add a streaming message placeholder
function addStreamingMessageToChat() {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'streaming-message');
    
    const contentElement = document.createElement('div');
    contentElement.classList.add('message-content');
    contentElement.textContent = '';
    
    const typingIndicator = document.createElement('div');
    typingIndicator.classList.add('typing-indicator');
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.classList.add('typing-dot');
        typingIndicator.appendChild(dot);
    }
    
    messageElement.appendChild(contentElement);
    messageElement.appendChild(typingIndicator);
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageElement;
}

// Function to update streaming message
function updateStreamingMessage(messageElement, content) {
    const contentElement = messageElement.querySelector('.message-content');
    contentElement.textContent = content;
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Function to call the RAG API
async function callRagApi(question, streamingMessageElement) {
    // Try direct API call first, fallback to proxy if needed
    const apiUrl = 'http://localhost:8000/query/stream';
    const proxyUrl = '/api/query/stream';
    
    try {
        // First try direct API call
        let response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question })
        });
        
        // If direct call fails with CORS error, try proxy
        if (!response.ok && response.type === 'cors') {
            console.log('Direct API call failed, trying proxy...');
            response = await fetch(proxyUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question })
            });
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Process the streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let accumulatedContent = '';
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                break;
            }
            
            // Decode the chunk
            const chunk = decoder.decode(value, { stream: true });
            
            // Process each line in the chunk
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6); // Remove 'data: ' prefix
                    
                    if (data === '[DONE]') {
                        // Stream is complete
                        break;
                    }
                    
                    try {
                        const parsedData = JSON.parse(data);
                        
                        // Handle different types of responses
                        if (parsedData.type === 'answer') {
                            // Accumulate answer content
                            accumulatedContent += parsedData.content;
                            updateStreamingMessage(streamingMessageElement, accumulatedContent);
                        } else if (parsedData.type === 'complete') {
                            // Stream is complete
                            console.log('Stream completed in', parsedData.total_time, 'seconds');
                            // Remove typing indicator when complete
                            const typingIndicator = streamingMessageElement.querySelector('.typing-indicator');
                            if (typingIndicator) {
                                streamingMessageElement.removeChild(typingIndicator);
                            }
                        }
                    } catch (parseError) {
                        console.error('Error parsing JSON:', parseError);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error in API call:', error);
        // Update the message with error info
        updateStreamingMessage(streamingMessageElement, `Sorry, I encountered an error: ${error.message}. Please try again.`);
        // Remove typing indicator
        const typingIndicator = streamingMessageElement.querySelector('.typing-indicator');
        if (typingIndicator) {
            streamingMessageElement.removeChild(typingIndicator);
        }
        throw error;
    }
}