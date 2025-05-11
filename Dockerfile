
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Create a wrapper script to handle different modes
RUN echo '#!/bin/bash\nif [ "$1" = "test" ]; then\n  python -m pytest -v\nelse\n  python runner.py --config config_a.json --logdir /app/logs --parallel\nfi' > /usr/local/bin/run.sh && \
    chmod +x /usr/local/bin/run.sh

# Default: run the simulation
ENTRYPOINT ["/usr/local/bin/run.sh"]
CMD []
