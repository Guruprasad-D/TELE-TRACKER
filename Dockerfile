# Use official Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy all project files into the container
COPY . .

# Optional: Ensure pip is up to date
RUN pip install --upgrade pip

# Install required Python packages
RUN pip install --no-cache-dir \
    flask \
    flask_httpauth \
    requests \
    python-telegram-bot==20.6

# Expose the port Flask will run on
EXPOSE 5000

# Run the app using Python directly
CMD ["python", "app.py"]
