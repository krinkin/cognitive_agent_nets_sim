
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Make run script executable
RUN chmod +x /app/run.sh

# Default: run the simulation
ENTRYPOINT ["/app/run.sh"]
CMD []
