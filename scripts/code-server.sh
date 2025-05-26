#!/bin/bash

cd $(dirname $0)
WORKDIR="$(realpath .)/.ci"
mkdir -p $WORKDIR
cd $WORKDIR

# docker container prune -f

VERSION=$(curl -s https://api.github.com/repos/coder/code-server/releases/latest | grep -Po '"tag_name": "v\K[^"]*')
wget "https://github.com/coder/code-server/releases/download/v${VERSION}/code-server_${VERSION}_$(dpkg --print-architecture).deb"
wget "https://github.com/coder/code-server/raw/refs/heads/main/ci/release-image/entrypoint.sh"
sed -i 's/coder/mlop/g' entrypoint.sh
chmod +x entrypoint.sh

DOCKER_BUILDKIT=1 docker build -t mlop-code-server:latest -f ../Dockerfile .

