# Testing Guide

This guide will help you test the automotive part matcher system.

## Prerequisites

Before running tests, you need:

1. **Python 3.8+** (you have Python 3.14.1 ✓)
2. **Virtual environment** (we'll create this)
3. **API Keys**:
   - Qdrant Cloud URL and API Key
   - OpenAI API Key
   - Anthropic API Key (optional, for future use)

## Setup Steps

### 1. Create Virtual Environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create .env File

Copy the example file and fill in your API keys:

```bash
cp .env.example .env
```

Then edit `.env` and add your credentials:

```env
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key
LLM_PROVIDER=claude
COLLECTION_NAME=automotive_connectors
```

### 4. Run Tests

```bash
python test_system.py
```

## What the Tests Do

The test script (`test_system.py`) will:

1. **Test Configuration Loading** - Verifies settings are loaded correctly
2. **Test Qdrant Connection** - Connects to your Qdrant Cloud instance
3. **Test Collection Creation** - Creates the collection with indexes
4. **Test Embedding Generation** - Generates embeddings using OpenAI
5. **Test Connector Upload** - Uploads 3 sample connectors
6. **Test Search Functionality** - Tests semantic search with and without filters
7. **Test Collection Statistics** - Retrieves collection info

## Expected Output

If everything works, you should see:

```
✓ Configuration loaded successfully!
✓ Qdrant service initialized successfully!
✓ Collection created successfully!
✓ Generated embedding with 3072 dimensions
✓ Successfully uploaded 3 connectors
✓ Found X results
✓ Collection Statistics retrieved
🎉 All tests passed! System is working correctly.
```

## Troubleshooting

### "Configuration loading failed"
- Check that `.env` file exists in `backend/` directory
- Verify all required environment variables are set

### "Qdrant connection failed"
- Verify `QDRANT_URL` and `QDRANT_API_KEY` are correct
- Check that your Qdrant Cloud instance is accessible
- Ensure you're using the correct URL format (https://...)

### "Embedding generation failed"
- Verify `OPENAI_API_KEY` is correct
- Check that you have credits/quota available on OpenAI
- Ensure the API key has access to the embedding model

### "Collection creation failed"
- Check Qdrant permissions
- Verify collection name doesn't conflict with existing collections
- Check Qdrant Cloud plan limits

## Getting API Keys

### Qdrant Cloud
1. Sign up at https://cloud.qdrant.io
2. Create a cluster
3. Get your cluster URL and API key from the dashboard

### OpenAI
1. Sign up at https://platform.openai.com
2. Go to API Keys section
3. Create a new API key
4. Ensure you have credits/quota for embeddings API

## Next Steps

After tests pass:
- You can start uploading real connector data using `ingest_data.py`
- The API endpoints will be available when you run `main.py`
- Check the `README.md` for more information

