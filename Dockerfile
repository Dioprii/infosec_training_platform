FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV ACADEMY_DB=/app/data/academy.db TRUST_PROXY=1
VOLUME /app/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u;u.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:8000", "wsgi:app"]
