FROM python:3.11-slim

LABEL maintainer="Donald Gray <donald.gray@digirati.com>"
LABEL org.opencontainers.image.source=https://github.com/dlcs/pdf-to-alto
LABEL org.opencontainers.image.description="Extract ALTO from PDF"

COPY /deps/pdfalto /usr/bin/pdfalto

COPY requirements.txt /opt/app/requirements.txt

WORKDIR /opt/app
RUN pip install --no-cache-dir -r requirements.txt

COPY app /opt/app/app
COPY monitor.py /opt/app/monitor.py
COPY wait-for-localstack.sh /opt/app/wait-for-localstack.sh

RUN chmod +x wait-for-localstack.sh

CMD ["python3", "/opt/app/monitor.py"]
