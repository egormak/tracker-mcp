FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies required by FastMCP and httpx
# (Using requirements.txt limits layers)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# By default, FastMCP runs on stdio, meaning we don't expose a network port 
# unless specifically requested. MCP clients talk to this container's stdin/stdout.

# Notice that the TRACKER_API_URL should point to the host machine.
# If you run docker run -i, you can pass -e TRACKER_API_URL=http://host.docker.internal:3000
ENV TRACKER_API_URL=http://host.docker.internal:3000

# Specify how to run the MCP server
ENTRYPOINT ["python", "server.py"]
