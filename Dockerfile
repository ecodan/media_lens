# Dockerfile for Google Cloud deployment (x86_64 Linux)
FROM python:3.12-slim

# Install system dependencies for Playwright and git
RUN apt-get update && apt-get install -y \
    # Playwright browser dependencies
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    curl \
    libx11-6 \
    libx11-xcb1 \
    libpangocairo-1.0-0 \
    libxss1 \
    git \
    ca-certificates \
    # Additional dependencies for Chromium
    libglib2.0-0 \
    libxcb1 \
    libxcursor1 \
    libxi6 \
    libxtst6 \
    libappindicator3-1 \
    libxshmfence1 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Install Playwright and Chromium browser
ENV PLAYWRIGHT_BROWSERS_PATH=0
RUN python -m playwright install chromium

# Note: Skipping 'playwright install-deps' because:
# 1. We've manually installed all required dependencies above
# 2. playwright install-deps targets Ubuntu packages which conflict with Debian Trixie
# 3. Manual dependency installation provides better control for cloud deployment

# Create directories
RUN mkdir -p /app/working/out

# Create a directory for SSH keys if needed
RUN mkdir -p /app/keys

# Set environment variables
ENV PYTHONPATH=/app/src
ENV USE_CLOUD_STORAGE=true

# Copy source code 
COPY src /app/src

# Copy configs
COPY config /app/config

# Copy both startup scripts (one for VM, one for container)
COPY startup-script.sh /app/vm-startup-script.sh
COPY container-startup.sh /app/container-startup.sh
RUN chmod +x /app/*.sh

# Expose the port
EXPOSE 8080

# Set container startup script as default command
CMD ["/app/container-startup.sh"]

