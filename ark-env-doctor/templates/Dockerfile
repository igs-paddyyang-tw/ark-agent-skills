FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl golang-go && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY requirements.txt* ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

CMD ["bash"]
