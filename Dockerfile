
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python","runner.py","--sessions","3","--duration","30","--logdir","/app/logs"]
