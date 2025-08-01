FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Mini-Claude files
COPY . .

# Create necessary directories
RUN mkdir -p /app/backups /app/logs /app/data

# Set up entrypoint
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port for potential web interface
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV MINI_CLAUDE_HOME=/app
ENV MINI_CLAUDE_DATA=/app/data

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["daemon"]