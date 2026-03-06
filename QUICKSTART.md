# Quick Start Guide

Get AI Code Mentor running in 5 minutes!

## Prerequisites Check

Before starting, verify you have these installed:

```bash
python --version          # Should be 3.10+
node --version           # Check Node is installed
npm --version            # Check npm is installed
```

If any of these fail, see [README.md](README.md#required-tools) for installation links.

---

## Setup (2 minutes)

### 1. Windows Users
```powershell
# Run the automated setup script
.\setup.ps1

# You'll be asked to edit .env file
# Copy your GEMINI_API_KEY there from:
# https://makersuite.google.com/app/apikey
```

### 2. macOS/Linux Users
```bash
# Run the automated setup script
bash setup.sh

# You'll be asked to edit .env file
# Copy your GEMINI_API_KEY there from:
# https://makersuite.google.com/app/apikey
```

---

## Get Your API Key (1 minute)

1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Edit `.env` file in the project folder:
   ```ini
   GEMINI_API_KEY=paste_your_key_here
   ```

---

## Start the Servers (2 minutes)

### Terminal 1: Start Backend
```bash
python app.py
```

You should see:
```
📊 Server Starting with Configuration:
   Available Tools: {'python': True, 'javascript': True, ...}
   AI Mentor Enabled: True
   CORS Enabled: Yes

🚀 Flask app running on http://127.0.0.1:5000
```

### Terminal 2: Start Frontend
```bash
npm run dev
```

You should see:
```
➜  Local:   http://localhost:5173/
```

---

## Open the App

Go to: **http://localhost:5173/**

---

## Try It Out!

```python
# Example: Try this code
print("Hello, World!")
x = 10 / 0  # This will error
```

1. Paste the code above
2. Click **Run Code**
3. See the error explanation and AI feedback!

---

## Troubleshooting

### Connection Refused?
- Make sure Flask is running: `python app.py`
- Check it's on port 5000: http://127.0.0.1:5000/health

### AI Mentor Not Working?
- Check `.env` has your GEMINI_API_KEY
- Restart Flask: `python app.py`
- Check Flask console for errors

### Tool Not Found?
- Go to http://localhost:5000/tools
- See which languages are unavailable
- Install the missing tools (see README.md)

---

## What's Next?

- 📖 Read [API.md](API.md) for full API documentation
- 🧪 Run tests: `pytest`
- 🎨 Explore light/dark mode toggle in the UI
- 💻 Try different programming languages

---

## Key Files

- **Frontend**: [src/App.jsx](src/App.jsx)
- **Backend**: [app.py](app.py)
- **Docs**: [README.md](README.md), [API.md](API.md)
- **Tests**: [tests/](tests/)

---

## Help & Support

- Backend Issues → Check [README.md#troubleshooting](README.md#-troubleshooting)
- API Questions → See [API.md](API.md)
- Setup Issues → Review [README.md](README.md#💻-local-setup-instructions)
- Test Questions → Read [tests/README.md](tests/README.md)

---

**Happy coding! 🚀**
