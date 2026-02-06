FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/coastcast

RUN addgroup --system coastcast && adduser --system --ingroup coastcast coastcast

COPY pyproject.toml constraints-runtime.txt README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip && python -m pip install --constraint constraints-runtime.txt .

COPY configs ./configs
COPY data/gold/features.parquet ./data/gold/
COPY artifacts/runtime/model_bundle.joblib artifacts/runtime/metrics.json artifacts/runtime/signature.json artifacts/runtime/test_predictions.parquet ./artifacts/runtime/
COPY reports ./reports

RUN chown -R coastcast:coastcast /opt/coastcast
USER coastcast

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)"

CMD ["streamlit", "run", "src/coastcast/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
