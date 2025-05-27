# code-server/blob/main/ci/release-image/Dockerfile

ARG BASE=debian:12
FROM scratch AS packages
COPY code-server*.deb /tmp/

FROM $BASE
# RUN sed -i -e 's/^Components: main$/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources
RUN apt-get update \
  && apt-get install -y \
    curl dumb-init git git-lfs htop locales lsb-release man-db nano openssh-client openssh-server procps wget vim zsh \
  && git lfs install \
  && rm -rf /var/lib/apt/lists/*
# RUN apt-get install -y sudo nvidia-smi nvidia-driver nvidia-cuda-toolkit

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

COPY settings.json /home/mlop/.local/share/code-server/User/settings.json
RUN chown -R mlop:mlop /home/mlop/

ENV ENTRYPOINTD=${HOME}/entrypoint.d
EXPOSE 8080
USER 1000
ENV USER=mlop
WORKDIR /home/mlop

RUN curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh" \
  && bash Miniforge3-$(uname)-$(uname -m).sh -p $HOME/conda -b -f \
  && rm Miniforge3-$(uname)-$(uname -m).sh \
  && $HOME/conda/bin/conda init bash \
  && $HOME/conda/bin/mamba install -y uv rust
RUN bash -c \
  "eval $($HOME/conda/bin/conda shell.bash hook 2> /dev/null) && \
  $HOME/conda/bin/uv pip install -U mlop ipykernel torch torchvision transformers"
RUN code-server --install-extension ms-python.python \
  && code-server --install-extension ms-toolsai.jupyter \
  && code-server --install-extension ms-azuretools.vscode-docker \
  && code-server --install-extension ms-vscode.makefile-tools \
  && code-server --install-extension ms-vscode.vscode-typescript-next \
  && code-server --install-extension charliermarsh.ruff \
  && code-server --install-extension redhat.vscode-yaml \
  && code-server --install-extension rust-lang.rust-analyzer

ENTRYPOINT ["/usr/bin/entrypoint.sh", "--bind-addr", "0.0.0.0:8080", "."]
