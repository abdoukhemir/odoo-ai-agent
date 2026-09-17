# N8N Odoo API Bridge

A production-ready REST API service that acts as a bridge between Odoo's AI module and an existing n8n workflow, mimicking the OpenAI Chat Completions API.

## Setup

1. Clone or download the project files.

2. Install dependencies:
   ```
   npm install
   ```

3. Copy the environment file:
   ```
   cp .env.example .env
   ```

4. Edit `.env` with your actual values:
   - `PORT`: Port to run the server (default: 3000)
   - `N8N_WEBHOOK_URL`: Your n8n webhook URL
   - `API_KEY`: Secret key for authentication

5. Start the server:
   ```
   npm start
   ```

   For development with auto-restart:
   ```
   npm run dev
   ```

The server will start on the port specified in `.env` (default: 3000).

## API Endpoints

### Health Check
- **GET** `/health`
- Response: `{"status": "ok"}`

### Chat Completions
- **POST** `/v1/chat/completions`
- Headers:
  - `Authorization: Bearer <API_KEY>`
  - `Content-Type: application/json`
- Body: OpenAI-compatible chat completion request
- Response: OpenAI-compatible chat completion response

## Testing

Use the following curl command to test:

```bash
curl -X POST http://localhost:3000/v1/chat/completions \
-H "Authorization: Bearer supersecretkey" \
-H "Content-Type: application/json" \
-d '{
"model": "gpt-4",
"messages": [
{"role": "user", "content": "Hello"}
]
}'
```

## Architecture

- **server.js**: Entry point, starts the server
- **app.js**: Express app configuration and middleware
- **routes/chat.js**: Chat completion routes
- **controllers/chatController.js**: Request handling logic
- **services/n8nService.js**: Communication with n8n webhook
- **middleware/auth.js**: Authentication middleware

## Error Handling

- 400: Invalid request format
- 401: Unauthorized (invalid or missing API key)
- 500: Internal server error (e.g., n8n unavailable)

## Logging

Console logs are added for debugging:
- Incoming requests
- Extracted messages
- n8n payloads and responses
- Errors

## Production Considerations

- Use a process manager like PM2 in production
- Set up proper logging (e.g., Winston)
- Add rate limiting
- Use HTTPS
- Monitor with tools like New Relic or DataDog