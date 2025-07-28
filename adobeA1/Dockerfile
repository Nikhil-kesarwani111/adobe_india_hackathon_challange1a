FROM --platform=linux/amd64 python:3.11-slim
WORKDIR /app
COPY . .
RUN python -m venv .venv && \
    . .venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt
CMD ["/bin/bash", "-c", "source .venv/bin/activate && python main.py"]
