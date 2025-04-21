FROM python:3.12-slim

# Install system dependencies for Playwright and git
RUN apt-get update && apt-get install -y \
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
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Install Playwright browsers with system dependencies
# Use PLAYWRIGHT_BROWSERS_PATH=0 to install browsers in the global location
ENV PLAYWRIGHT_BROWSERS_PATH=0
RUN python -m playwright install --with-deps chromium
RUN python -c "from playwright.sync_api import sync_playwright; sync_playwright().start()" || echo "Playwright initialization attempted"

# Create directories
RUN mkdir -p /app/working/out

# Create a directory for SSH keys if needed
RUN mkdir -p /app/keys

# Set environment variables
ENV PYTHONPATH=/app
ENV USE_CLOUD_STORAGE=true

# Expose the port
EXPOSE 8080

