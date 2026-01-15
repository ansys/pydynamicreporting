# Python version selected to satisfy:
# requires-python = ">=3.10, <3.13"
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY .. /app

# Create virtual environment inside container
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app/src

RUN pip install --upgrade pip setuptools wheel
RUN pip install uv

RUN make clean install

CMD ["python"]