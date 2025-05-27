#!/bin/bash

cd $(dirname $0)
WORKDIR="$(realpath .)/.ci"
mkdir -p $WORKDIR
cd $WORKDIR

# setup
sudo apt purge -y awscli python3-awscrt amazon-ec2-utils cloud-guest-utils cloud-image-utils cloud-init cloud-utils
sudo apt autoremove -y
sudo rm -rf /etc/cloud /var/lib/cloud/

sudo sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update; sudo apt install -y docker-compose rsync nvidia-detect nvidia-driver nvidia-container-toolkit linux-headers-$(uname -r)
sudo sed -i 's/#no-cgroups/no-cgroups/g' /etc/nvidia-container-runtime/config.toml

export VERSION=$(curl -s https://api.github.com/repos/coder/code-server/releases/latest | grep -Po '"tag_name": "v\K[^"]*')
wget "https://github.com/coder/code-server/releases/download/v${VERSION}/code-server_${VERSION}_$(dpkg --print-architecture).deb"
fakeroot sh -c '
mkdir .work
dpkg-deb -R code-server_*.deb .work
rm -rf .work/DEBIAN/conffiles
wget https://github.com/mlop-ai/mlop/raw/refs/heads/main/design/favicon.ico -O .work/usr/lib/code-server/src/browser/media/favicon.ico
wget https://github.com/mlop-ai/mlop/raw/refs/heads/main/design/favicon.svg -O .work/usr/lib/code-server/src/browser/media/favicon.svg
wget https://github.com/microsoft/vscode/raw/refs/heads/main/resources/server/code-192.png -O .work/usr/lib/code-server/src/browser/media/pwa-icon-192.png
wget https://github.com/microsoft/vscode/raw/refs/heads/main/resources/server/code-512.png -O .work/usr/lib/code-server/src/browser/media/pwa-icon-512.png
sed -i 's/{{app}}/mlop/g' .work/usr/lib/code-server/out/node/i18n/locales/en.json
dpkg-deb -b .work code-server_${VERSION}_$(dpkg --print-architecture).deb
'
wget "https://caddyserver.com/api/download?os=linux&arch=$(dpkg --print-architecture)&p=github.com%2Fcaddy-dns%2Fcloudflare" -O caddy; chmod +x caddy
# wget "https://github.com/coder/code-server/raw/refs/heads/main/ci/release-image/entrypoint.sh"
# sed -i 's/coder/mlop/g' entrypoint.sh; chmod +x entrypoint.sh
cp ../settings.json ../entrypoint.sh .

DOCKER_BUILDKIT=1 docker build -t mlop-code-server:latest -f ../Dockerfile .
# docker container prune -f; docker builder prune -a
# docker run --rm --gpus '"device=0,2"' debian:12 nvidia-smi