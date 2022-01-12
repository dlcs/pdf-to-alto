FROM ubuntu:focal as build

# avoid issue with packages requiring interaction (e.g. tzdata)
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y wget cmake clang git autoconf pkg-config

# Change submodule to https as we're cloning only. Avoids issues with ssh
RUN mkdir /home/pdfalto && cd /home/pdfalto \
    && git clone https://github.com/kermitt2/pdfalto.git && cd pdfalto && ./install_deps.sh \
    && git submodule set-url xpdf-4.03 https://github.com/kermitt2/xpdf-4.03.git && git submodule update --init --recursive \
    && cmake ./ && make

FROM ubuntu:focal

LABEL maintainer="Donald Gray <donald.gray@digirati.com>"
LABEL org.opencontainers.image.source=https://github.com/dlcs/pdf-to-alto
LABEL org.opencontainers.image.description="Extract ALTO from PDF"

RUN apt-get update && apt-get install -y python3 python3-pip python-dev libmupdf-dev

COPY --from=build  /home/pdfalto/pdfalto/pdfalto /usr/bin/pdfalto

CMD ["/usr/bin/pdfalto", "-v"]