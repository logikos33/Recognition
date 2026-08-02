# Redis dos segmentos de vídeo — separação da instância de segurança

Item 1.6 do mutirão. Relacionado: `docs/decisions/adr/` (ADR-0017, tenant sem
fallback; sessões/blocklist em `app/domain/services/session_service.py`).

## Problema

O Redis de produção roda `maxmemory=0` + `maxmemory-policy=noeviction`.

Duas categorias de tráfego muito diferentes compartilham essa MESMA
instância:

1. **Segmentos de vídeo do live view** — `epi:edge_hls:{camera_id}:{filename}`
   (o edge empurra playlist `.m3u8` + segmentos `.ts` via
   `POST /api/v1/edge/live-view/<camera_id>/segment`, TTL ~20s) e
   `epi:stream:{camera_id}:active` / `:ffmpeg_lock` (estado "tem espectador
   agora" e lock de FFmpeg). Volume alto, TTL curto, tráfego que cresce
   linearmente com câmeras × espectadores.
2. **Estado de segurança** — `revoked_jti:{jti}` (blocklist de JWT revogado,
   `app/domain/services/session_service.py`), TTL = vida restante do token
   (até `JWT_EXPIRY_HOURS`, default 24h).

Com `noeviction`, se o volume de segmento encher a instância, as escritas
adicionais falham — **incluindo as de segurança**. Um pico de câmeras/
espectadores pode impedir a revogação de um token (ex.: suspensão de tenant,
force-logout) de ser persistida.

## Decisão

- **`allkeys-lru` está descartado.** Despejaria `revoked_jti:*` sob pressão de
  memória — um token revogado voltaria a valer silenciosamente. Isso é pior
  que o problema original.
- **Separação real**: os segmentos de vídeo vão para uma instância/DB Redis
  **distinta** da instância de segurança, via env opcional
  `SEGMENTS_REDIS_URL`.
  - `SEGMENTS_REDIS_URL` **setada** → todo leitor/escritor de
    `epi:edge_hls:*` e `epi:stream:*` usa essa URL.
  - `SEGMENTS_REDIS_URL` **não setada** → comportamento atual inalterado
    (tudo na mesma instância `REDIS_URL` de sempre — zero mudança silenciosa
    de default).

## Implementação

Helper central: `app/core/segments_redis.py` —
`get_segments_redis()` / `get_segments_redis_binary()` (binário para os
segmentos `.ts`, que não são UTF-8). Todo call site das chaves de segmento
passa por eles (direto ou delegando, ex.: `_get_binary_redis()` em
`app/api/v1/cameras/helpers.py`, `_get_redis_client()` em
`local_stream_manager.py`).

Boot-check informativo em `app/__init__.py::_check_redis_segments_config`:
se `SEGMENTS_REDIS_URL` não está setada e o Redis principal responde
`maxmemory-policy=noeviction` (ou `maxmemory=0`) a um `CONFIG GET`, loga um
`logger.warning` com `degraded_config=true`. Best-effort — Redis gerenciado
pode bloquear `CONFIG GET`; a checagem silencia com debug log e nunca
impede o boot.

## Como provisionar no Railway

Duas opções, em ordem de preferência:

### Opção A — segunda instância Redis (recomendado)

1. Adicionar um segundo plugin Redis no ambiente Railway (`Redis-segments`
   ou nome equivalente).
2. Setar `SEGMENTS_REDIS_URL` no serviço `api` (e no `worker`/
   `celery-worker`, se algum consumidor rodar lá) apontando pra essa
   instância.
3. Configurar nela:
   - `maxmemory` dimensionado para o volume real de segmento (ex.: câmeras
     × espectadores simultâneos × ~200KB por segmento × alguns segundos de
     margem — folgado, é tráfego pequeno por natureza).
   - `maxmemory-policy=volatile-ttl` (ver fallback abaixo — mesmo raciocínio
     se aplica mesmo numa instância dedicada, como segunda camada de defesa).

### Opção B — mesmo Redis, DB index separado (fallback de infra)

Se a infra não permitir uma segunda instância:

```
SEGMENTS_REDIS_URL=${REDIS_URL}/1
```

(troca o DB index — Redis padrão tem 16 DBs lógicos, índice 0 é o default).
Isola os KEYSPACES (um `FLUSHDB`/estouro de memória por-DB ainda pode
existir dependendo de como o provedor mede `maxmemory`, mas ao menos
`SCAN`/`KEYS`/eviction não colidem entre os dois usos). Preferir Opção A
sempre que possível — DB index no MESMO processo Redis não isola memória
física nem `CONFIG` (o `maxmemory` é da instância inteira, não por-DB).

## Fallback — se nem Opção A nem B forem possíveis

Se por alguma razão os segmentos tiverem que continuar na MESMA instância
que a blocklist de segurança:

1. `maxmemory-policy=volatile-ttl` na instância (**nunca** `allkeys-lru` —
   ver decisão acima). `volatile-ttl` só despeja chaves COM TTL, priorizando
   as de TTL mais próximo de expirar — os segmentos (`TTL~20s`) morrem
   primeiro, naturalmente, antes de qualquer `revoked_jti:*` de TTL mais
   longo (até 24h) ser candidato a despejo.
2. **Garantir que o TTL do `revoked_jti:*` é sempre ≥ vida restante do
   token** — se essa invariante quebrar (ex.: alguém trocar por um TTL fixo
   menor que `JWT_EXPIRY_HOURS`), o fallback `volatile-ttl` deixa de proteger
   a segurança (uma chave de segurança com TTL mais curto que os segmentos
   vira candidata a despejo ANTES deles). Verificado em
   `app/domain/services/session_service.py::blocklist_jtis` — TTL deriva de
   `expires_at - now` (o `exp` real do JWT, setado em
   `app/api/v1/auth/routes.py::_register_session`), com fallback de 24h
   apenas se `expires_at` não for um datetime válido. Ver testes em
   `tests/unit/domain/test_session_service.py`.
3. Mesmo com `volatile-ttl` certo, prefira migrar para a Opção A/B assim que
   possível — o fallback reduz o risco, não o elimina (ainda existe uma
   janela onde `noeviction`→`volatile-ttl` é a única rede de proteção contra
   um pico de segmento).
