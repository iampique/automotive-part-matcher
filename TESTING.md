# Testing Frontend and Backend Together

This guide will help you test both the frontend and backend working together.

## Prerequisites

1. **Backend Environment Setup**
   - Ensure you have a `.env` file in the `backend/` directory with:
     - `QDRANT_URL`
     - `QDRANT_API_KEY`
     - `OPENAI_API_KEY`
     - `ANTHROPIC_API_KEY`
   - Make sure data has been ingested (run `python ingest_data.py` if needed)

2. **Frontend Dependencies**
   - Node.js and npm installed
   - Frontend dependencies installed (`npm install` in `frontend/` directory)

## Step-by-Step Testing

### Step 1: Start the Backend Server

Open a terminal and run:

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python -m app.main
```

Or using uvicorn directly:

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Verify backend is running:**
- Open http://localhost:8000/docs in your browser
- You should see the FastAPI Swagger documentation

### Step 2: Start the Frontend Server

Open a **new terminal** (keep backend running) and run:

```bash
cd frontend
npm run dev
```

You should see output like:
```
  ▲ Next.js 16.0.10
  - Local:        http://localhost:3000
  - Ready in [time]
```

**Verify frontend is running:**
- Open http://localhost:3000 in your browser
- You should see the "Automotive Connector Matcher" interface

### Step 3: Test the Integration

1. **Test Text Search:**
   - In the frontend, enter a search query like:
     ```
     Need 48-pin connector for EV battery, 48V rated, IP67 protection, automotive grade
     ```
   - Click "Search"
   - You should see:
     - Loading spinner
     - Results displayed in cards
     - Workflow trace (if execution trace is available)

2. **Test File Upload:**
   - Switch to "Upload Document" tab
   - Upload a PDF or DOCX file with connector requirements
   - Click "Search"
   - Verify results appear

3. **Test Advanced Options:**
   - Click "Show Advanced Options"
   - Toggle between Claude and OpenAI
   - Toggle ACORN on/off
   - Run searches with different configurations

### Step 4: Verify Backend Logs

Check the backend terminal for:
- API request logs
- Processing time logs
- Any error messages

## Troubleshooting

### Backend won't start
- Check that `.env` file exists and has all required variables
- Verify virtual environment is activated
- Check that port 8000 is not already in use
- Ensure all Python dependencies are installed

### Frontend won't start
- Verify Node.js is installed (`node --version`)
- Run `npm install` in the frontend directory
- Check that port 3000 is not already in use

### CORS Errors
- Backend CORS is configured for `http://localhost:3000` and `http://localhost:3001`
- If frontend runs on a different port, update CORS settings in `backend/app/api.py`

### No Results Returned
- Verify data has been ingested into Qdrant
- Check backend logs for errors
- Verify Qdrant connection settings in `.env`
- Check that the collection exists and has data

### API Connection Errors
- Verify backend is running on http://localhost:8000
- Check browser console for network errors
- Verify `NEXT_PUBLIC_API_URL` environment variable if set (defaults to localhost:8000)

## Quick Health Check

Test backend health endpoint:
```bash
curl http://localhost:8000/api/health
```

Should return:
```json
{"status":"healthy","version":"1.0.0"}
```

## Expected Behavior

When everything is working correctly:

1. **Search Input:**
   - Text input or file upload works
   - Loading state shows during search
   - No errors in console

2. **Results Display:**
   - Match cards appear with connector information
   - Score badges show with color coding
   - Expandable details work
   - Workflow trace shows execution steps

3. **Workflow Trace:**
   - Shows execution steps when available
   - Displays processing time
   - Shows ACORN status

4. **Error Handling:**
   - Errors display in a user-friendly format
   - Backend errors are caught and displayed
   - Network errors are handled gracefully

