# code-server/blob/main/ci/release-image/Dockerfile

ARG BASE=debian:12
FROM scratch AS packages
COPY code-server*.deb /tmp/

FROM $BASE
RUN apt-get update \
  && apt-get install -y \
    curl \
    dumb-init \
    git \
    git-lfs \
    htop \
    locales \
    lsb-release \
    man-db \
    nano \
    openssh-client \
    procps \
    sudo \
    vim-tiny \
    wget \
    zsh \
  && git lfs install \
  && rm -rf /var/lib/apt/lists/*

RUN sed -i "s/# en_US.UTF-8/en_US.UTF-8/" /etc/locale.gen \
  && locale-gen
ENV LANG=en_US.UTF-8

RUN if grep -q 1000 /etc/passwd; then userdel -r "$(id -un 1000)"; fi \
  && adduser --gecos '' --disabled-password mlop
# && echo "mlop ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/nopasswd

RUN ARCH="$(dpkg --print-architecture)" \
  && curl -fsSL "https://github.com/boxboat/fixuid/releases/download/v0.6.0/fixuid-0.6.0-linux-$ARCH.tar.gz" | tar -C /usr/local/bin -xzf - \
  && chown root:root /usr/local/bin/fixuid \
  && chmod 4755 /usr/local/bin/fixuid \
  && mkdir -p /etc/fixuid \
  && printf "user: mlop\ngroup: mlop\n" > /etc/fixuid/config.yml

COPY entrypoint.sh /usr/bin/entrypoint.sh
RUN --mount=from=packages,src=/tmp,dst=/tmp/packages dpkg -i /tmp/packages/code-server*$(dpkg --print-architecture).deb

ENV ENTRYPOINTD=${HOME}/entrypoint.d

EXPOSE 8080
USER 1000
ENV USER=mlop
WORKDIR /home/mlop
ENTRYPOINT ["/usr/bin/entrypoint.sh", "--bind-addr", "0.0.0.0:8080", "."]
