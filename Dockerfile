FROM ubuntu:24.04

MAINTAINER Stefano Dalla Palma

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip

RUN apt-get install git -y

COPY . /app
WORKDIR /app

RUN pip install git+https://github.com/Mikmocc00/radon-terraform-metrics.git
RUN pip install git+https://github.com/Mikmocc00/radon-kubernetes-metrics.git
RUN pip install git+https://github.com/Mikmocc00/radon-docker-metrics.git

RUN pip install -r requirements.txt


RUN python -m spacy download en_core_web_sm


RUN pip install .


ENV TMP_REPOSITORIES_DIR=/tmp/

CMD repo-miner -h
