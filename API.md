# API Documentation

## Backend Endpoints

The Flask backend provides the following REST API endpoints:

### 1. Health Check

**Endpoint:** `GET /health`

**Description:** Check server status and available tools.

**Response:**
```json
{
  "status": "Server is running!",
  "available_tools": {
    "python": true,
    "javascript": true,
    "java": false,
    "c": false,
    "cpp": false
  },
  "ai_mentor_enabled": true
}
```

### 2. List Available Tools

**Endpoint:** `GET /tools`

**Description:** Get list of compilation/execution tools available on the server.

**Response:**
```json
{
  "available": {
    "python": true,
    "javascript": true,
    "java": false,
    "c": false,
    "cpp": false
  },
  "message": "Tools marked as 'false' are not installed. See README for setup instructions."
}
```

### 3. Analyze Code

**Endpoint:** `POST /analyze`

**Description:** Analyze source code for issues and execute it.

**Request Body:**
```json
{
  "code": "print('hello world')",
  "language": "python"
}
```

**Request Parameters:**
- `code` (required, string): The source code to analyze
- `language` (optional, string): Programming language (default: "python")
  - Supported: `python`, `javascript`, `java`, `c`, `cpp`

**Response:**
```json
{
  "ok": true,
  "language": "python",
  "summary": {
    "line_count": 1,
    "issue_count": 0
  },
  "issues": [
    {
      "line": 1,
      "severity": "warning",
      "code": "LONG_LINE",
      "message": "Line exceeds 79 characters"
    }
  ],
  "execution": {
    "stdout": "hello world\n",
    "stderr": "",
    "returncode": 0,
    "timed_out": false,
    "tool_missing": false,
    "error": null
  },
  "ai_mentor_feedback": "Your code looks good!"
}
```

**Response Fields:**
- `ok`: Whether the request was successful
- `language`: The language that was analyzed
- `summary`: Overview statistics
- `issues`: Array of detected code issues
  - `line`: Line number where issue was found
  - `severity`: "error", "warning", or "info"
  - `code`: Issue code identifier
  - `message`: Human-readable issue description
- `execution`: Execution results
  - `stdout`: Standard output from program execution
  - `stderr`: Standard error output
  - `returncode`: Process exit code (0 = success)
  - `timed_out`: Whether execution timed out
  - `tool_missing`: Whether required compiler/runtime is missing
  - `error`: Detailed error information if one occurred
- `ai_mentor_feedback`: AI-generated feedback about errors

**Error Responses:**

- **400 Bad Request** - Missing or invalid code
  ```json
  {
    "ok": false,
    "error": "Invalid or missing 'code' field in request body."
  }
  ```

- **422 Unprocessable Entity** - Tools not available
  ```json
  {
    "ok": false,
    "error": "Tools for language 'java' are not installed on this server.",
    "suggestion": "Check the /tools endpoint for available languages or see README for setup."
  }
  ```

- **500 Internal Server Error** - Server error during analysis
  ```json
  {
    "ok": false,
    "error": "Internal server error during analysis."
  }
  ```

### 4. Root Endpoint

**Endpoint:** `GET /`

**Description:** Get API documentation.

**Response:**
```json
{
  "message": "AI Code Mentor Backend API",
  "version": "1.0",
  "endpoints": {
    "POST /analyze": "Analyze code (requires JSON: code, language)",
    "GET /health": "Server health check",
    "GET /tools": "List available compilation tools"
  }
}
```

---

## Issue Codes

Common issue codes returned by the analyzer:

### Static Analysis Issues
- `SYNTAX_ERROR` - Python syntax error
- `LONG_LINE` - Line exceeds 79 characters
- `TODO_COMMENT` - TODO/FIXME comment found
- `TRAILING_WHITESPACE` - Line has trailing whitespace
- `TABS_INDENT` - Using tabs instead of spaces for indentation
- `LANGUAGE_UNSUPPORTED` - Language not yet fully supported

### Compilation Issues
- `C_ERROR`, `C_WARNING` - GCC compiler error/warning
- `CPP_ERROR`, `CPP_WARNING` - G++ compiler error/warning
- `JAVA_ERROR`, `JAVA_WARNING` - Javac compiler error/warning

---

## Error Explanations

The analyzer provides helpful error explanations for common runtime errors:

### Python Errors
- **ZeroDivisionError** - Explains dividing by zero
- **NameError** - Variable not defined
- **TypeError** - Wrong data type for operation
- **IndexError** - List index out of range
- **KeyError** - Dictionary key not found

### JavaScript Errors
- **ReferenceError** - Variable not defined
- **TypeError** - Operation on wrong type
- **SyntaxError** - Invalid syntax

### Java Errors
- **NullPointerException** - Using null reference

---

## Environment Variables

Configure the backend with environment variables in `.env`:

```ini
# Google Gemini API Key (required for AI Mentor)
GEMINI_API_KEY=your_api_key_here

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True

# Frontend API Endpoint (optional, defaults to http://localhost:5000)
VITE_API_ENDPOINT=http://localhost:5000

# Logging
LOG_LEVEL=INFO
```

---

## CORS Configuration

The backend has CORS (Cross-Origin Resource Sharing) enabled to allow requests from the frontend on a different port.

**Allowed Origins:** All (configured via `flask-cors`)

For production, modify the CORS configuration in `app.py`:
```python
CORS(app, origins=['https://yourdomain.com'])
```

---

## Rate Limiting

The AI Mentor feature uses Google's Gemini API:
- **Free Tier:** 15 requests per minute
- **Paid Tier:** Much higher limits with billing account

If rate-limited, you'll see an `AI_MENTOR_API_ERROR` response.

---

## Example Usage

### Python Requests Library
```python
import requests

response = requests.post(
    'http://localhost:5000/analyze',
    json={
        'code': 'print("hello")',
        'language': 'python'
    }
)

result = response.json()
print(result['execution']['stdout'])
```

### JavaScript Fetch API
```javascript
const response = await fetch('http://localhost:5000/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: 'console.log("hello");',
    language: 'javascript'
  })
});

const result = await response.json();
console.log(result.execution.stdout);
```

### cURL
```bash
curl -X POST http://localhost:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(10/0)",
    "language": "python"
  }'
```

---

## Troubleshooting

### Connection Refused
- Make sure Flask is running: `python app.py`
- Check port 5000 is available

### CORS Error
- Frontend must be on different port (5173 for Vite)
- Backend has CORS enabled

### AI Mentor Not Working
- Check GEMINI_API_KEY is set in `.env`
- Check your API key is valid
- Check for rate limiting (wait 1 minute)

### Tool Not Found
- Check `/tools` endpoint to see what's available
- Install missing tools (GCC, Java, etc.)
- Add tools to system PATH

---
