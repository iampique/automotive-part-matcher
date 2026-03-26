# Setting Up Qdrant Locally

This guide will help you set up Qdrant locally to load your connector data.

## Step 1: Install Docker Desktop

1. **Download Docker Desktop for Mac:**
   - Visit: https://www.docker.com/products/docker-desktop/
   - Click "Download for Mac" (choose Intel or Apple Silicon based on your Mac)
   - Or use Homebrew: `brew install --cask docker`

2. **Install and Start Docker Desktop:**
   - Open the downloaded `.dmg` file
   - Drag Docker to Applications
   - Open Docker Desktop from Applications
   - Wait for Docker to start (you'll see a whale icon in the menu bar)

3. **Verify Docker is running:**
   ```bash
   docker --version
   docker ps
   ```

## Step 2: Start Qdrant Locally

Run the setup script:

```bash
cd backend
./setup_local_qdrant.sh
```

This script will:
- Check if Docker is running
- Start a Qdrant container on port 6333
- Update your `.env` file to use `http://localhost:6333`
- Remove the API key requirement (not needed for local instances)

## Step 3: Load Your Data

Once Qdrant is running, load your connector data:

```bash
cd backend
source venv/bin/activate
python3 ingest_data.py
```

This will:
- Create the collection
- Load 500 connectors from `data/raw/connector_catalog.json`
- Generate embeddings using OpenAI
- Upload all connectors to Qdrant

## Step 4: Verify Data Loaded

Check that data was loaded successfully:

```bash
# The ingestion script will show statistics at the end
# You can also check the Qdrant dashboard at:
open http://localhost:6333/dashboard
```

## Troubleshooting

### Docker not starting
- Make sure Docker Desktop is running (check menu bar for whale icon)
- Try restarting Docker Desktop
- Check system requirements: https://docs.docker.com/desktop/install/mac-install/

### Port 6333 already in use
```bash
# Stop existing Qdrant container
docker stop qdrant
docker rm qdrant

# Or use a different port
docker run -d --name qdrant -p 6334:6333 qdrant/qdrant:latest
# Then update .env: QDRANT_URL=http://localhost:6334
```

### Connection errors
- Make sure Qdrant container is running: `docker ps`
- Check logs: `docker logs qdrant`
- Verify .env has correct URL: `cat .env | grep QDRANT_URL`

## Stopping Qdrant

When you're done:

```bash
docker stop qdrant
```

To start it again later:

```bash
docker start qdrant
```

Or use the setup script again (it will detect if Qdrant is already running).
