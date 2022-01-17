FROM debian:bullseye as build

# avoid issue with packages requiring interaction (e.g. tzdata)
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y wget cmake clang git autoconf pkg-config

# Change submodule to https as we're cloning only. Avoids issues with ssh
# 8bb209c0c21476ee904a is 0.4 with some bugfixes
RUN mkdir /home/pdfalto && cd /home/pdfalto \
    && git clone https://github.com/kermitt2/pdfalto.git && cd pdfalto && git checkout 8bb209c0c21476ee904a && ./install_deps.sh \
    && git submodule set-url xpdf-4.03 https://github.com/kermitt2/xpdf-4.03.git && git submodule update --init --recursive \
    && cmake ./ && make

FROM python:3.9-slim

LABEL maintainer="Donald Gray <donald.gray@digirati.com>"
LABEL org.opencontainers.image.source=https://github.com/dlcs/pdf-to-alto
LABEL org.opencontainers.image.description="Extract ALTO from PDF"

COPY --from=build  /home/pdfalto/pdfalto/pdfalto /usr/bin/pdfalto

COPY requirements.txt /opt/app/requirements.txt

WORKDIR /opt/app
RUN pip install --no-cache-dir -r requirements.txt
COPY . /opt/app

RUN chmod +x wait-for-localstack.sh

CMD ["python3", "/opt/app/monitor.py"]