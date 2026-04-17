# Worker On-Premise — EPI Monitor V2

Containeriza o Celery worker de inferência YOLO em um servidor físico com GPU NVIDIA.
O worker consome a fila `inference_{TENANT_SCHEMA}` no Redis do Railway via Tailscale.

---

## Pré-requisitos

| Componente | Versão mínima | Instalação |
|------------|---------------|------------|
| Docker Engine | 24.0+ | `curl -fsSL https://get.docker.com | sh` |
| NVIDIA Driver | 525+ | Instalar via gerenciador da distro |
| nvidia-container-toolkit | Latest | Ver abaixo |
| Tailscale | Latest | Ver abaixo |

### nvidia-container-toolkit

```bash
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | \
    sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verificar
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

---

## Tailscale (conectar ao Redis Railway)

O Redis Railway não é acessível diretamente pela internet. Use Tailscale para criar
um túnel seguro entre o servidor físico e a rede Railway.

```bash
# Instalar Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Conectar à sua tailnet (autenticar no browser)
tailscale up

# Verificar conectividade com o Redis Railway
# (substitua pelo hostname do seu Redis Railway)
tailscale ping containers-us-west-xxx.railway.app

# Testar conexão Redis
redis-cli -u "redis://default:PASSWORD@containers-us-west-xxx.railway.app:6379" ping
```

> **Nota:** O REDIS_URL no `.env` deve usar o hostname Tailscale ou o hostname público
> do Railway com a senha correta.

---

## Configuração

```bash
cd backend/worker_onpremise

# 1. Copiar e editar variáveis de ambiente
cp .env.example .env
nano .env  # Preencher REDIS_URL, DATABASE_URL, TENANT_SCHEMA, JWT_SECRET_KEY

# 2. Criar diretórios de volume
mkdir -p models hls
```

### Variáveis obrigatórias no `.env`

| Variável | Descrição |
|----------|-----------|
| `REDIS_URL` | URL do Redis Railway (obter via `railway variables`) |
| `DATABASE_URL` | URL do PostgreSQL Railway |
| `TENANT_SCHEMA` | Schema do tenant (ex: `rvb`) |
| `JWT_SECRET_KEY` | **Igual ao do api-v3 Railway** |

---

## Iniciar o Worker

```bash
# Build e start em background
docker-compose up -d --build

# Acompanhar logs
docker-compose logs -f worker-onpremise

# Verificar se o worker está registrado no Celery
docker-compose exec worker-onpremise \
    celery -A app.infrastructure.queue.celery_app:celery inspect ping

# Parar
docker-compose down
```

---

## Heartbeat Redis

O worker publica automaticamente um heartbeat a cada 30s em:

```
Redis KEY: worker:heartbeat:{TENANT_SCHEMA}
TTL: 90 segundos
```

Se o heartbeat expirar, o painel admin mostrará o badge **🔴 Offline** e o sistema
fará fallback automático para o worker Railway.

Para verificar o status pelo Redis:

```bash
redis-cli -u "$REDIS_URL" GET "worker:heartbeat:rvb"
```

---

## Filas Consumidas

| Fila | Descrição |
|------|-----------|
| `inference_{TENANT_SCHEMA}` | Inferência dedicada deste tenant |
| `inference` | Fila fallback Railway |
| `training` | Jobs de treinamento |
| `extraction` | Extração de frames de vídeo |

---

## Monitoramento

```bash
# Status das filas
docker-compose exec worker-onpremise \
    celery -A app.infrastructure.queue.celery_app:celery inspect active_queues

# Tasks em execução
docker-compose exec worker-onpremise \
    celery -A app.infrastructure.queue.celery_app:celery inspect active

# Estatísticas
docker-compose exec worker-onpremise \
    celery -A app.infrastructure.queue.celery_app:celery inspect stats
```

---

## Atualizar o Worker

```bash
git pull origin staging
docker-compose up -d --build
# Zero-downtime: novo container sobe antes do antigo parar
```

---

## Troubleshooting

**Worker não conecta ao Redis**
```bash
# Testar conectividade
redis-cli -u "$REDIS_URL" ping
# Se falhar: verificar Tailscale + firewall + senha no REDIS_URL
```

**GPU não detectada**
```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
# Se falhar: reiniciar docker após instalar nvidia-container-toolkit
sudo systemctl restart docker
```

**Worker aparece como Offline no painel admin**
```bash
# Verificar heartbeat
redis-cli -u "$REDIS_URL" GET "worker:heartbeat:rvb"
# Se vazio: worker não está rodando ou TENANT_SCHEMA está errado no .env
```
