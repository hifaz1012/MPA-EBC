FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY README.md .

# Expose HTTP port for optional FastMCP HTTP transport / health checks
EXPOSE 8000

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
