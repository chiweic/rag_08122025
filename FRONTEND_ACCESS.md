# Frontend Access Guide

## ✅ Frontend is Already Connected and Running!

The frontend is automatically served by the FastAPI backend and is already configured to connect to all API endpoints.

## Access the Frontend

### Local Access
**URL**: http://localhost:8000/

Open this URL in your web browser to access the **佛學普化小助手** (Buddhist Assistant) interface.

### Network Access
If you want to access from other devices on your network:
**URL**: http://YOUR_IP_ADDRESS:8000/

To find your IP address:
```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

## Frontend Features

The web interface provides:

### Main Chat Interface
- 💬 **Real-time Q&A** with streaming responses
- 📚 **Source citations** with document references
- ⏱️ **Performance metrics** (retrieval & synthesis time)
- 🔄 **Chat history** with beautiful message cards

### Right Sidebar Recommendations
- 📚 **Book Recommendations** (法鼓文化)
  - Based on your queries
  - 622 books in catalog
  - Direct links to purchase

- 🏮 **Event Recommendations** (解行並重)
  - Buddhist events and activities
  - 210 events available
  - Location and schedule info

- 🎧 **Audio Teaching Recommendations**
  - Dharma talks and teachings
  - 2,287 audio chunks
  - Relevant to your questions

### Interactive Actions
- 📝 **Summarize** - Get concise summaries of answers
- 🧠 **Quiz** - Generate and evaluate quizzes
- 🔗 **Related Queries** - Discover similar questions

### Popular Queries Section
- Quick-access to common Buddhist questions
- One-click to get answers

## How It Works

### API Connection
The frontend automatically connects to the backend API at the same origin (`window.location.origin`).

Configuration in [frontend/app.js](frontend/app.js:3):
```javascript
const API_BASE_URL = window.location.origin;
```

### Health Check
On page load, the frontend checks the API connection:
```javascript
async checkConnection() {
    const response = await fetch(`${API_BASE_URL}/health`);
    // Updates status indicator
}
```

### Query Flow
1. User types question
2. Frontend sends POST to `/query` or `/query/stream`
3. Backend retrieves relevant documents from Qdrant
4. Gemini LLM generates answer
5. Response streamed back to frontend
6. Recommendations loaded in parallel

## Current Configuration

### Backend Status
- ✅ **Server**: Running on 0.0.0.0:8000
- ✅ **LLM**: Google Gemini (gemini-2.5-flash-lite)
- ✅ **Embeddings**: Google Gemini (models/embedding-001, 768-dim)
- ✅ **Vector DB**: Qdrant (1,067 documents indexed)
- ✅ **Data**: Text chunks, audio, events all loaded

### Frontend Files
- **HTML**: [frontend/index.html](frontend/index.html) (2,264 lines)
- **JavaScript**: [frontend/app.js](frontend/app.js)
- **Served by**: FastAPI static file mount

## Testing the Frontend

### Quick Test
1. Open http://localhost:8000/ in your browser
2. You should see the purple gradient interface with "佛學普化小助手"
3. Status indicator should show "已連接" (Connected)
4. Try asking: "什麼是三寶？"

### Expected Behavior
- **Answer appears** with streaming effect (character by character)
- **Sources panel** shows relevant documents
- **Book recommendations** appear in right sidebar
- **Event recommendations** appear below books
- **Performance chart** updates with query time

## Troubleshooting

### Frontend Not Loading
```bash
# Check if server is running
curl http://localhost:8000/health

# Should return:
{"status":"healthy","initialized":true,"vector_store_connected":true,"pipeline_ready":true}
```

### API Connection Failed
- Check browser console (F12) for errors
- Verify server is running: `ps aux | grep "python main.py"`
- Restart server if needed

### No Answers Appearing
1. Check system is initialized:
   ```bash
   curl http://localhost:8000/statistics
   ```
2. If not initialized, run:
   ```bash
   curl -X POST http://localhost:8000/initialize
   ```

### Recommendations Not Showing
- Recommendations load after the answer
- Check browser console for errors
- Verify recommenders initialized in server logs

## API Endpoints Used by Frontend

The frontend uses these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check API status |
| `/query` | POST | Get answer (non-streaming) |
| `/query/stream` | POST | Get answer (streaming SSE) |
| `/retrieve` | POST | Get source documents |
| `/books/recommend` | POST | Get book recommendations |
| `/events/recommend` | POST | Get event recommendations |
| `/audio/recommend` | POST | Get audio recommendations |
| `/queries/related` | POST | Get related queries |
| `/summarize` | POST | Summarize text |
| `/quiz/generate` | POST | Generate quiz |
| `/quiz/evaluate` | POST | Evaluate answers |

## Browser Compatibility

Tested and working on:
- ✅ Chrome/Edge (Chromium-based)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

## Next Steps

### For Users
1. Open http://localhost:8000/
2. Start asking Buddhist questions
3. Explore book and event recommendations
4. Try the quiz feature

### For Developers
1. Frontend code in `frontend/` directory
2. Modify `frontend/app.js` for functionality changes
3. Modify `frontend/index.html` for UI changes
4. Server auto-reloads on file changes (if in dev mode)

## Production Deployment

For production deployment:
1. Set proper CORS origins in `.env`
2. Use reverse proxy (nginx/apache)
3. Enable HTTPS
4. Set appropriate rate limits
5. Monitor performance with the built-in performance chart

---

**🎉 Your frontend is ready to use!**

Open http://localhost:8000/ and start exploring!
