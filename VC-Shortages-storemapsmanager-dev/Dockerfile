FROM docker.target.com/managed/python/tgt-poetry-base:3.11-debian-slim-bookworm

ENV RUNTIME_VERSION=v2.4.5

ARG WORKDIR=/home/storemapsapp
ARG USER=storemapsapp
COPY . /home/storemapsapp
WORKDIR /home/storemapsapp

RUN mkdir -p /home/storemapsapp/certs
RUN mkdir -p /home/storemapsapp/config

RUN apt-get update && \
    apt-get install -y \
    libpq-dev libsm6 libxext6 \
    gcc curl \
    wget \
    bzip2 \
    ca-certificates \
    sudo \
    locales \
    git \
    tar \
    cron \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install -i https://binrepo.target.com/artifactory/api/pypi/tgt-python/simple tgt-certs
RUN curl -o ./certs/tgt-ca-bundle.crt http://browserconfig.target.com/tgt-certs/tgt-ca-bundle.crt
RUN curl -sk "https://binrepo.target.com/artifactory/platform/runtime-connector/${RUNTIME_VERSION}/runtime-connector-linux-amd64-${RUNTIME_VERSION}.tgz" -o /runtime-connector.tgz && tar xvzf /runtime-connector.tgz -C / && rm /runtime-connector.tgz

RUN pip install -r requirements.txt --no-cache-dir

EXPOSE 6000
ENTRYPOINT ["/runtime-connector", "--", "tgt-instrument", "python", "main.py"]