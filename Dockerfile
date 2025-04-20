FROM python:3.12-slim

# Install system dependencies for Playwright
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
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Install Playwright browsers with system dependencies
RUN PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install --with-deps chromium

# Copy the application code
COPY . .

# Create directories
RUN mkdir -p /app/working/out

# Create a directory for SSH keys if needed
RUN mkdir -p /app/keys

# Set environment variables
ENV PYTHONPATH=/app
ENV USE_CLOUD_STORAGE=true
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright/browsers

# Expose the port
EXPOSE 8080

# Use Gunicorn to run the Flask app
# Increased timeout from 120 to 600 seconds to accommodate long-running page cleaning
# Using sync worker since the app runs as a scheduled job, not a long-running service
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "600", "--log-level", "info", "src.media_lens.cloud_entrypoint:app"]

