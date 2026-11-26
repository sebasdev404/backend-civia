FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home civia
COPY app ./app
COPY migrations ./migrations
COPY main.py manage.py sync_live_service.py ./
COPY ops ./ops
RUN mkdir -p static/covers static/thumbnails && chown -R civia:civia /app
USER civia
EXPOSE 8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log","--no-proxy-headers"]
