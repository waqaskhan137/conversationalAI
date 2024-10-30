# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install system-level dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libasound-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any required Python packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8000 for the WebSocket server
EXPOSE 8000

# Use CMD instead of ENTRYPOINT for flexibility
CMD ["python3", "/app/src/server.py"]
