# Use an official Python runtime as a parent image
# FROM python:3.9-slim
# FROM --platform=linux/arm64 debian:bookworm-slim
# Use an official Python runtime as the parent image
FROM --platform=linux/amd64 python:3.9-slim

RUN ping -c 1 192.168.2.30 > /dev/null 2>&1 && \
    (mkdir -p ~/.config/pip && \
    echo "[global]" > ~/.config/pip/pip.conf && \
    echo "index-url = http://192.168.2.30:8081/repository/pypi/simple" >> ~/.config/pip/pip.conf && \
    echo "trusted-host = 192.168.2.30" >> ~/.config/pip/pip.conf && \
    echo "timeout = 300" >> ~/.config/pip/pip.conf) || true

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
RUN pip install --timeout=100 -r requirements.txt

# Expose port 8000 for the WebSocket server
EXPOSE 8000

# Use CMD instead of ENTRYPOINT for flexibility
CMD ["python3", "/app/src/server.py"]
