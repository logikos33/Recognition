# AGENT.md — apps/landing

**Aplicação:** Landing Page — Site público do Recognition com demo ONNX
**Stack:** Astro 4 + React (islands) + ONNX Runtime Web
**URL produção:** `https://landing-page-production-b659.up.railway.app`
**Railway SERVICE_TYPE:** `landing-page`

---

## Propósito

Site estático público para apresentação da plataforma Recognition. Inclui uma demo interativa de detecção YOLO rodando inteiramente no browser via ONNX Runtime Web — sem dependência de backend em runtime. O visitante pode fazer upload de uma imagem e ver bounding boxes gerados pelo modelo `yolov8n-demo.onnx` localmente.

---

## Stack

| Componente | Detalhe |
|-----------|---------|
| Framework | Astro 4 |
| UI islands | React (seletivo, apenas componentes interativos) |
| Inference | ONNX Runtime Web (`ort` package) |
| Modelo | `yolov8n-demo.onnx` (na raiz / `public/`) |
| Estilo | Tailwind CSS |
| Build | Astro build → `dist/` |
| Servidor | Nginx (Docker) |

---

## Estrutura de Diretórios

```
apps/landing/
├── src/
│   ├── components/
│   │   └── (componentes React/Astro para demo e marketing)
│   ├── layouts/
│   │   └── (layouts base Astro)
│   └── pages/
│       └── (rotas Astro: index.astro, demo.astro, etc.)
├── public/
│   └── yolov8n-demo.onnx         # Modelo ONNX para demo browser
├── astro.config.mjs               # Configuração Astro (integração React, Tailwind)
├── tailwind.config.mjs
├── package.json
├── nginx.conf                     # Nginx para servir dist/ em produção
├── start.sh                       # Entry point no container
├── Dockerfile
├── railway.toml
└── AGENT.md                       # Este arquivo
```

---

## Demo ONNX no Browser

A demo roda inferência YOLOv8 client-side:

```
Usuário seleciona imagem
  → React component carrega yolov8n-demo.onnx via ONNX Runtime Web
  → Pré-processa imagem (resize 640x640, normaliza)
  → ort.InferenceSession.run() — roda no browser (WebAssembly ou WebGL)
  → Pós-processa saída (bounding boxes + NMS)
  → Renderiza boxes no canvas HTML5
```

**Zero requests ao backend.** Tudo roda no dispositivo do visitante.

**Modelo:** `yolov8n-demo.onnx` — versão nano otimizada para browser (classes de EPI: helmet, vest, etc.)

---

## Deploy via `railway_start.py`

O `railway_start.py` na raiz do monorepo roteia com base em `SERVICE_TYPE`:

```python
# SERVICE_TYPE=landing-page
# → inicia Flask static server com endpoint /health
# → serve arquivos de apps/landing/dist/
```

Em produção, o Dockerfile usa Nginx diretamente (mais eficiente que Flask para estático).

---

## Sem Dependência de Backend

A landing page é completamente independente do backend em runtime:
- Sem chamadas para `api-v3`
- Sem autenticação JWT
- Sem PostgreSQL, Redis ou qualquer serviço externo
- `yolov8n-demo.onnx` é servido como asset estático

Isso significa que a landing page permanece acessível mesmo durante manutenção do backend.

---

## Variáveis de Ambiente

A landing page não requer variáveis de ambiente obrigatórias para funcionar.

Opcionais (para analytics ou contact form):
```bash
PUBLIC_ANALYTICS_ID=...    # ID de analytics (se configurado)
```

---

## Comandos

```bash
cd apps/landing
npm run dev       # desenvolvimento local (porta 4321 padrão Astro)
npm run build     # build para dist/
npm run preview   # preview do build em dist/
```

---

## Restrições

- Zero dependências de runtime para inferência — tudo via ONNX Runtime Web (browser)
- `public/yolov8n-demo.onnx` não deve ser substituído por modelos proprietários com dados de clientes
- Tailwind purge configurado — zero classes não usadas em produção
- Astro islands: usar `client:load` com parcimônia; preferir `client:visible` para componentes abaixo do fold
