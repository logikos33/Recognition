#!/usr/bin/env bash
# Vast.ai training orchestrator — PR B2
#
# Provisiona GPU spot, envia scripts, treina YOLOX-s e RF-DETR,
# baixa ONNX e registra no registry.
#
# Uso:
#   export VAST_API_KEY=...
#   export ROBOFLOW_API_KEY=...
#   export DATABASE_URL=postgresql://...
#   export R2_ENDPOINT_URL=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET_NAME=...
#   ./training/vast/provision_and_train.sh [--model yolox|rfdetr|both] [--epochs 50]
#
# Requer: vastai CLI  (pip install vastai)
#         ssh acessível com chave ~/.ssh/id_rsa (ou SSH_KEY_PATH)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${MODEL:-both}"
EPOCHS="${EPOCHS:-50}"
BATCH="${BATCH:-16}"
IMGSZ="${IMGSZ:-640}"
DISK_GB="${DISK_GB:-60}"
GPU_MIN_VRAM="${GPU_MIN_VRAM:-10}"    # GiB mínimo de VRAM
MAX_PRICE="${MAX_PRICE:-0.40}"        # USD/h máximo
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"
OUTPUT_DIR="${OUTPUT_DIR:-$SCRIPT_DIR/runs/$(date +%Y%m%d_%H%M%S)}"

# Dataset Roboflow — configure ROBOFLOW_WORKSPACE + ROBOFLOW_PROJECT + ROBOFLOW_VERSION
# Default: dataset PPE público CC BY 4.0 (Hard Hat Workers — Roboflow)
ROBOFLOW_WORKSPACE="${ROBOFLOW_WORKSPACE:-roboflow-100}"
ROBOFLOW_PROJECT="${ROBOFLOW_PROJECT:-hard-hat-workers}"
ROBOFLOW_VERSION="${ROBOFLOW_VERSION:-2}"
ROBOFLOW_FORMAT="${ROBOFLOW_FORMAT:-yolov8}"  # yolox usa mesmo formato

: "${VAST_API_KEY:?VAST_API_KEY não definido}"
: "${ROBOFLOW_API_KEY:?ROBOFLOW_API_KEY não definido}"
: "${DATABASE_URL:?DATABASE_URL não definido}"
: "${R2_BUCKET_NAME:?R2_BUCKET_NAME não definido}"

mkdir -p "$OUTPUT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "=== Vast.ai Training — modelo=$MODEL épocas=$EPOCHS ==="

# ── 1. Selecionar oferta mais barata com GPU suficiente ────────────────────────
log "Buscando ofertas GPU (VRAM>=${GPU_MIN_VRAM}GiB, max \$${MAX_PRICE}/h)..."
OFFER_ID=$(vastai search offers \
    --raw \
    "gpu_ram>=${GPU_MIN_VRAM} num_gpus=1 rentable=true" \
    --type on-demand \
    --order dph_total \
    --limit 5 \
  | python3 -c "
import json, sys
offers = json.load(sys.stdin)
cheap = [o for o in offers if o.get('dph_total', 999) <= float('${MAX_PRICE}')]
if not cheap:
    sys.exit('Nenhuma oferta abaixo de \$${MAX_PRICE}/h encontrada')
print(cheap[0]['id'])
")
log "Oferta selecionada: $OFFER_ID"

# ── 2. Criar instância ─────────────────────────────────────────────────────────
log "Provisionando instância..."
INSTANCE_JSON=$(vastai create instance "$OFFER_ID" \
    --image pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime \
    --disk "$DISK_GB" \
    --ssh \
    --env '-e DEBIAN_FRONTEND=noninteractive' \
    --raw)
INSTANCE_ID=$(echo "$INSTANCE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['new_contract'])")
log "Instância criada: $INSTANCE_ID"

# ── 3. Aguardar SSH ficar disponível ──────────────────────────────────────────
log "Aguardando SSH (máx 5 min)..."
for i in $(seq 1 30); do
    SSH_INFO=$(vastai show instance "$INSTANCE_ID" --raw 2>/dev/null || echo "{}")
    SSH_HOST=$(echo "$SSH_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('ssh_host',''))" 2>/dev/null || true)
    SSH_PORT=$(echo "$SSH_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('ssh_port','22'))" 2>/dev/null || true)
    STATUS=$(echo "$SSH_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('actual_status',''))" 2>/dev/null || true)
    if [ "$STATUS" = "running" ] && [ -n "$SSH_HOST" ]; then
        log "SSH disponível: $SSH_HOST:$SSH_PORT"
        break
    fi
    log "  status=$STATUS (tentativa $i/30)..."
    sleep 10
done

SSH_CMD="ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no -p $SSH_PORT root@$SSH_HOST"
SCP_CMD="scp -i $SSH_KEY_PATH -o StrictHostKeyChecking=no -P $SSH_PORT"

# ── 4. Enviar scripts de treinamento ──────────────────────────────────────────
log "Enviando scripts..."
$SCP_CMD "$SCRIPT_DIR/train_yolox.py"  "root@$SSH_HOST:/root/train_yolox.py"
$SCP_CMD "$SCRIPT_DIR/train_rfdetr.py" "root@$SSH_HOST:/root/train_rfdetr.py"

# ── 5. Instalar dependências na instância ────────────────────────────────────
log "Instalando dependências..."
$SSH_CMD <<'REMOTE'
pip install -q --upgrade pip
pip install -q roboflow onnx onnxruntime boto3 psycopg2-binary
REMOTE

# ── 6. Treinar ───────────────────────────────────────────────────────────────
log "Iniciando treinamento (modelo=$MODEL)..."
$SSH_CMD "bash -lc '
export ROBOFLOW_API_KEY=${ROBOFLOW_API_KEY}
export ROBOFLOW_WORKSPACE=${ROBOFLOW_WORKSPACE}
export ROBOFLOW_PROJECT=${ROBOFLOW_PROJECT}
export ROBOFLOW_VERSION=${ROBOFLOW_VERSION}
export ROBOFLOW_FORMAT=${ROBOFLOW_FORMAT}
export EPOCHS=${EPOCHS}
export BATCH=${BATCH}
export IMGSZ=${IMGSZ}

if [ \"${MODEL}\" = \"yolox\" ] || [ \"${MODEL}\" = \"both\" ]; then
    python3 /root/train_yolox.py 2>&1 | tee /root/yolox_train.log
fi

if [ \"${MODEL}\" = \"rfdetr\" ] || [ \"${MODEL}\" = \"both\" ]; then
    python3 /root/train_rfdetr.py 2>&1 | tee /root/rfdetr_train.log
fi
'"

# ── 7. Baixar resultados ──────────────────────────────────────────────────────
log "Baixando resultados para $OUTPUT_DIR..."
$SCP_CMD "root@$SSH_HOST:/root/runs/*.onnx" "$OUTPUT_DIR/" 2>/dev/null || true
$SCP_CMD "root@$SSH_HOST:/root/yolox_train.log" "$OUTPUT_DIR/" 2>/dev/null || true
$SCP_CMD "root@$SSH_HOST:/root/rfdetr_train.log" "$OUTPUT_DIR/" 2>/dev/null || true
$SCP_CMD "root@$SSH_HOST:/root/metrics.json" "$OUTPUT_DIR/" 2>/dev/null || true

# ── 8. Destruir instância ─────────────────────────────────────────────────────
log "Destruindo instância $INSTANCE_ID..."
vastai destroy instance "$INSTANCE_ID"
log "Instância destruída."

# ── 9. Registrar modelos no registry ─────────────────────────────────────────
log "Registrando modelos no registry..."
python3 "$SCRIPT_DIR/upload_and_register.py" --runs-dir "$OUTPUT_DIR"

log "=== Treinamento concluído. Artefatos em $OUTPUT_DIR ==="
