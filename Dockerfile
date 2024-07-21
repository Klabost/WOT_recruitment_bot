FROM python:3.10.12-slim-bullseye

RUN pip install -U \
    pip \
    setuptools \
    wheel

WORKDIR /app

RUN useradd -m -r user && \
    chown user /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app/ /app

USER user

ENTRYPOINT ["python3", "main.py"]