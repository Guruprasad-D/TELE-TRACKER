FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir flask flask_httpauth python-telegram-bot==20.6

# Expose port
EXPOSE 5000

# Start the app
CMD ["python", "app.py"]
