FROM python:3.10-slim

# Install FFmpeg, Node.js (for YouTube challenges), and required media tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project code and assets
COPY . .

# Expose ports (7860 for Hugging Face Spaces, 8000 for Render / local)
ENV PORT=7860
EXPOSE 7860 8000

CMD ["python", "server.py"]
