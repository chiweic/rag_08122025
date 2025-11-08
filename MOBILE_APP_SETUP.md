# Mobile App Setup Guide (Capacitor)

## Overview
This guide explains how to deploy the DDM RAG frontend as a native mobile app using Capacitor.

## Architecture

```
Mobile App (Capacitor)
  ↓
https://api.changpt.org (Cloudflare Tunnel)
  ↓
localhost:8000 (FastAPI Backend)
  ↓
Qdrant Vector DB
```

## Current Configuration

### Backend CORS Settings (`.env`)
```env
CORS_ORIGINS=https://api.changpt.org,http://localhost:8000,capacitor://localhost,ionic://localhost,http://localhost,https://localhost
```

### Frontend API URL (`index.html`)
```javascript
const API_BASE_URL = 'https://api.changpt.org';
```

### Capacitor Config (`capacitor.config.json`)
```json
{
  "appId": "org.changpt.ddmrag",
  "appName": "學佛入門",
  "webDir": "frontend_v2",
  "server": {
    "url": "https://api.changpt.org"
  }
}
```

## Troubleshooting "Failed to Fetch" Error

### 1. Check Network Connectivity
**Problem**: Mobile device can't reach `https://api.changpt.org`

**Solutions**:
- Ensure mobile device is on same network or has internet access
- Verify Cloudflare Tunnel is running and publicly accessible
- Test API endpoint in mobile browser: `https://api.changpt.org/health`

### 2. Check Server Accessibility
```bash
# On mobile browser, visit:
https://api.changpt.org/health

# Should return:
{
  "status": "healthy",
  "initialized": true,
  "qdrant_collection": {...}
}
```

### 3. Check CORS Configuration
**Problem**: CORS blocking requests from Capacitor app

**Verify**:
```bash
# Check what origins are allowed
source venv/bin/activate
python -c "from config import settings; print(settings.cors_origins)"
```

**Should include**:
- `capacitor://localhost`
- `ionic://localhost`
- `http://localhost`
- `https://localhost`

### 4. Check Capacitor HTTP Plugin
Capacitor apps should use the native HTTP plugin for better CORS handling.

**Install** (if not already):
```bash
npm install @capacitor/http
```

**Then update frontend to use CapacitorHttp instead of fetch**:
```javascript
import { CapacitorHttp } from '@capacitor/http';

const response = await CapacitorHttp.request({
  url: `${API_BASE_URL}/query`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  data: { question: 'test' }
});
```

### 5. Enable Mixed Content (Android)
Add to `capacitor.config.json`:
```json
{
  "android": {
    "allowMixedContent": true,
    "webContentsDebuggingEnabled": true
  }
}
```

### 6. Check iOS App Transport Security
For iOS, ensure `Info.plist` allows HTTPS connections:
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <false/>
    <key>NSExceptionDomains</key>
    <dict>
        <key>api.changpt.org</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key>
            <false/>
            <key>NSIncludesSubdomains</key>
            <true/>
        </dict>
    </dict>
</dict>
```

## Debugging Steps

### 1. Open Mobile App DevTools
**Android**:
```bash
# Enable web debugging in capacitor.config.json
"webContentsDebuggingEnabled": true

# Then open Chrome DevTools
chrome://inspect
```

**iOS**:
```
Safari → Develop → [Your Device] → [App Name]
```

### 2. Check Console Logs
The app now logs detailed fetch information:
```
🔗 API Base URL: https://api.changpt.org
📱 User Agent: Mozilla/5.0 (iPhone...)
🌐 Origin: capacitor://localhost
🌐 Fetching: https://api.changpt.org/query
✅ Response: 200 OK
```

Or on error:
```
❌ Fetch failed for https://api.changpt.org/query
   Error type: TypeError
   Error message: Network request failed
```

### 3. Test API Directly
In mobile browser (not the app), visit:
```
https://api.changpt.org/
https://api.changpt.org/health
https://api.changpt.org/docs
```

If these work but the app doesn't, it's a Capacitor/CORS issue.

## Alternative: Development Mode
For testing, you can bypass Cloudflare and connect directly to your development machine:

### 1. Find your local IP
```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Should show something like: 192.168.1.100
```

### 2. Update API_BASE_URL temporarily
In mobile app's localStorage:
```javascript
localStorage.setItem('API_BASE_URL_OVERRIDE', 'http://192.168.1.100:8000');
```

### 3. Update CORS to allow your IP
```env
CORS_ORIGINS=...,http://192.168.1.100:8000
```

### 4. Restart backend
```bash
python main.py
```

## Production Deployment Checklist

- [ ] Cloudflare Tunnel is running and accessible
- [ ] Backend `.env` has correct CORS_ORIGINS
- [ ] Frontend API_BASE_URL points to production domain
- [ ] Capacitor config has correct appId and appName
- [ ] SSL certificate is valid for api.changpt.org
- [ ] Backend /health endpoint returns 200 OK
- [ ] Mobile browser can access API directly
- [ ] App uses CapacitorHttp plugin (recommended)
- [ ] Android allowMixedContent enabled
- [ ] iOS App Transport Security configured

## Common Issues

### Issue: "Failed to fetch" on mobile, works in browser
**Cause**: Capacitor CORS requirements differ from web browsers

**Fix**: Use `@capacitor/http` plugin instead of native fetch API

### Issue: "Network request failed" immediately
**Cause**: Server unreachable from mobile device

**Fix**: Check Cloudflare Tunnel is public, or use local IP in development

### Issue: Requests work sometimes, fail others
**Cause**: Timeout or network instability

**Fix**: Add retry logic and increase timeout:
```javascript
const response = await fetch(url, {
  ...options,
  signal: AbortSignal.timeout(30000) // 30 second timeout
});
```

## Need Help?
Check the console logs first - they now show detailed fetch information including:
- API URL being called
- Origin (capacitor:// vs http://)
- Response status or error details

This information is crucial for debugging mobile app connectivity issues.
