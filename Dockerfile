# Fixed Python and Python packages; record the built image digest for bitwise exports.
FROM python:3.12.14-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/wenfeng
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
WORKDIR /work
ENTRYPOINT ["python", "/opt/wenfeng/scripts/run.py"]
