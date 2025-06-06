import os
import uuid
import random
import requests
import subprocess
import socket

import bcrypt
import docker

from .utils import gen_ed25519

def start_server(client: docker.DockerClient, host: str = "localhost", port_range: tuple[int, int] = (20000, 40000), gpu: bool = True):
    port = random.randint(port_range[0], port_range[1])
    while get_available(port):
        port = random.randint(port_range[0], port_range[1])

    password = uuid.uuid4().hex # [:8]
    private_key, public_key = gen_ed25519()
    deploy_code(
        client=client,
        project_dir=f"/var/tmp/docker-code-{str(port)}",
        host_port=port,
        ssh_port=port - 1,
        password=password,
        image_name="mlop-code-server:latest",
        gpu=gpu,
        authorized_keys=public_key,
        host=host,
    )
    print(f"Started code-server at port {port} with password {password}")
    return port, password, f"https://mlop:{password}@{host}:{port}/{password}/", private_key, port - 1


def stop_server(client: docker.DockerClient, port: int):
    client.containers.get(f"code-{str(port)}").stop()
    client.containers.get(f"caddy-{str(port)}").stop()
    client.containers.get(f"code-{str(port)}").remove()
    client.containers.get(f"caddy-{str(port)}").remove()
    client.networks.get(f"code-network-{port}").remove()


def stop_all(client: docker.DockerClient):
    containers = client.containers.list(all=True)
    for c in containers:
        networks = c.attrs['NetworkSettings']['Networks']
        c.stop()
        c.remove()
        for network_name in networks:
            try:
                network = client.networks.get(network_name)
                network.remove()
            except:
                pass


def get_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return False
        except socket.error:
            return True


def check_caddy(bin_path: str):
    if not os.path.exists(f"{bin_path}"):
        os.makedirs(os.path.dirname(bin_path), exist_ok=True)
        response = requests.get(
            f"https://caddyserver.com/api/download?os=linux&arch={subprocess.check_output(['dpkg', '--print-architecture']).decode().strip()}&p=github.com%2Fcaddy-dns%2Fcloudflare")
        with open(f"{bin_path}", "wb") as f:
            f.write(response.content)
        os.chmod(bin_path, 0o755)  # Make executable


def deploy_code(
    client: docker.DockerClient,
    project_dir: str,
    host_port: int = 8080,
    ssh_port: int = 2222,
    password: str = None,
    image_name: str = "codercom/code-server:latest",
    gpu: bool = True,
    authorized_keys: str = "",
    cache_dir: str = os.path.abspath(os.getcwd()),
    host: str = "localhost",
) -> dict:
    try:
        check_caddy(f"{cache_dir}/.mlop/caddy")
        network_name = f"code-network-{host_port}"
        try:
            network = client.networks.create(network_name, driver="bridge")
        except docker.errors.APIError:
            network = client.networks.get(network_name)

        code_container = client.containers.run(
            image_name,
            detach=True,
            name=f"code-{str(host_port)}",
            network=network_name,
            command=f"--disable-telemetry --auth none",
            environment={
                "AUTHORIZED_KEYS": authorized_keys,
                # "PASSWORD": password
            },
            ports={
                f"2222/tcp": ssh_port,
                # f"8080/tcp": 8080
            },
            # volumes={os.path.abspath(project_dir): {"bind": "/home/mlop/project", "mode": "rw"}},
            # tty=True, stdin_open=True,
            cpu_count=4,
            **({"device_requests": [
                docker.types.DeviceRequest(
                    device_ids=['all'], capabilities=[['gpu']]) # ['0', '2']
            ]} if gpu else {})
        )

        caddy_container = client.containers.run(
            "caddy:2",
            detach=True,
            name=f"caddy-{host_port}",
            network=network_name,
            ports={f"{host_port}/tcp": host_port},
            volumes={
                f"{cache_dir}/scripts/Caddyfile": {"bind": "/etc/caddy/Caddyfile", "mode": "ro"},
                f"{cache_dir}/.mlop/caddy": {"bind": "/usr/bin/caddy", "mode": "ro"},
                f"{cache_dir}/.mlop/caddy_data": {"bind": "/data", "mode": "rw"},
                f"{cache_dir}/.mlop/caddy_config": {"bind": "/config", "mode": "rw"},
            },
            environment={
                "PORT": host_port,
                "USERNAME": "mlop",
                "PASSWORD": password,
                "HASHED_PASSWORD": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                "ACME_AGREE": "true",
                "DOMAIN": host,
                "CLOUDFLARE_API_TOKEN": os.getenv("CLOUDFLARE_API_TOKEN", "nope")
            }
        )

        return f"{host_port}", code_container, caddy_container
    except Exception as e:
        print(f"Error starting containers: {e}")
        return None
