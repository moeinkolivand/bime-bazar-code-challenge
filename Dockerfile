FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --index-url https://archive.ito.gov.ir/mirror2/python/simple/ --no-cache-dir --upgrade pip && \
    pip install --index-url https://archive.ito.gov.ir/mirror2/python/simple/ --no-cache-dir -r requirements.txt

FROM builder

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
