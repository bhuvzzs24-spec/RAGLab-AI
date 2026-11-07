FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false HF_HOME=/models RAGLAB_DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/api/requirements.txt apps/api/requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock.txt
COPY apps/api/ ./
RUN useradd --uid 10001 --create-home raglab && mkdir /data /models && chown raglab:raglab /data /models
USER raglab
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4)"
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
