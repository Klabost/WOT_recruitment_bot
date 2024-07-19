FROM python:3.10.12-slim-bullseye

ENV TINI_VERSION="v0.19.0"

ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

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

ENTRYPOINT ["/tini", "--", "python3", "main.py"]