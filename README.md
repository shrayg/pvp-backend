# PVP AI Terminal - Backend

## Deploy to Railway (Recommended)
1. Upload this folder to GitHub
2. Connect to Railway
3. Set environment variables:
   - GROK_API_KEY
   - CLAUDE_API_KEY
4. Deploy

## Deploy to Render
1. Upload to GitHub
2. Connect to Render
3. Set environment variables
4. Deploy

## Environment Variables
- GROK_API_KEY: Your X.AI API key
- CLAUDE_API_KEY: Your Anthropic API key

## Endpoints
- GET / - Health check
- GET /stream - Server-Sent Events
- GET /api/logs - Polling endpoint
