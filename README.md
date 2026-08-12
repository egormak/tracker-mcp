# Tracker MCP Server

This is an MCP (Model Context Protocol) server designed to connect to your local `tracker-server`. It exposes endpoints like checking and applying today's schedule, retrieving statistics, registering tasks, and managing timers directly to LLM clients (like Claude Desktop or Cursor).

## Prerequisites
- A running instance of `tracker-server` (usually on `http://localhost:3000`).
- Python 3.11+ (if running locally) or Docker.

---

## 🚀 Running via Docker (Recommended)

When you deploy your MCP agent, you can hook it directly to the Docker image provided from the GitHub Container Registry. 

Because `tracker-server` is running on your host machine locally, Docker needs to know how to reach it. The image defaults to `http://host.docker.internal:3000` assuming you are on Mac/Windows or using Docker Desktop.

### For Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tracker-mcp": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "TRACKER_API_URL=http://host.docker.internal:3000",
        "ghcr.io/egormak/tracker-mcp:sha-57577b3"
      ]
    }
  }
}
```

> Note: Notice the `-i` flag. Because MCP communicates over stdin/stdout (`stdio`), you must run the docker container interactively, but without a TTY (`-t`).

---

## 🛠 Running Locally

If you are developing or simply prefer to run from source instead of Docker.

1. **Setup the Virtual Environment**:
   ```bash
   cd tracker-mcp
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the MCP Server manually**:
   ```bash
   # Make sure your tracker server is running!
   python server.py
   ```
   *Note: This will just block your terminal waiting for `stdio` MCP JSON RPC commands. This is expected.*

3. **Configure Claude Desktop (Local Mode)**:
   ```json
   {
     "mcpServers": {
       "tracker-mcp": {
         "command": "/absolute/path/to/tracker-mcp/venv/bin/python",
         "args": [
           "/absolute/path/to/tracker-mcp/server.py"
         ],
         "env": {
           "TRACKER_API_URL": "http://localhost:3000"
         }
       }
     }
   }
   ```
