---
title: "Integrações & Segredos no painel admin (conectar R2/GPU/DB/notificação pela UI, sem env/código)"
pr_title: "feat(admin): área de integrações & segredos (R2, GPU/treino, DB, notificação) pela UI"
commit_message: "feat(admin): integrações self-service (credenciais cifradas via painel)"
risk: security
status: AUTO (cloud)
---

# Tarefa 058 — Integrações & Segredos no painel admin (self-service)

## Por quê
Regra do FRONTEND_OPERABILITY_STANDARD.md + AUTOADMIN_STUDY.md: o app se auto-serve. Hoje as
credenciais (R2, Vast, etc.) são env no Railway — o usuário teria que abrir infra/código. Precisa de
uma **área de Integrações no painel** onde se digita a API/credencial e o sistema passa a usar, sem
tocar em env nem código. Substitui as "PENDÊNCIAS DE ACESSO" por configuração na própria plataforma.

## Contrato de Operabilidade
- Tela **Administração → Integrações**: cards por integração com estado (conectado/desconectado),
  formulário pra inserir a credencial, botão **"Testar conexão"** (valida antes de salvar, estilo
  probe), e status (última verificação, ok/erro). Campos mascarados (mostra só `••••last4`).
- Integrações-alvo:
  - **Storage (Cloudflare R2 / S3-compat):** bucket, account/endpoint, access key, secret.
  - **Provedor de GPU/Treino:** Vast.ai (API key) + genérico (provider + key/endpoint) — pra trocar de
    GPU/provedor sem código ("troquei de placa/serviço de treino").
  - **Notificação:** canais (webhook/e-mail/WhatsApp) — API/endpoint.
  - **(Avançado) Banco/Storage por tenant (BYO):** cliente que quer os dados dele em outro banco/bucket
    — connection string/credenciais próprias, escopadas ao tenant.

## Segurança (obrigatório — risk:security)
- Segredos **cifrados at rest** (Fernet, reusar CAMERA_SECRET_KEY/padrão de cifra existente).
- **Write-only / masked:** a API NUNCA devolve o segredo em plaintext pro front (só `last4` + permite
  substituir). Nada de "ver a chave".
- **Role-gated:** integrações de PLATAFORMA (R2/GPU/notificação global) = superadmin; integrações
  ESCOPADAS ao tenant (BYO-DB/bucket) = admin do tenant. Isolamento por tenant inegociável.
- **Auditoria:** toda mudança de integração no audit_log (quem, quando, qual).
- **Precedência definida:** valor do painel sobrepõe o env; documentar a ordem.

## Ressalva técnica (honesta)
- Segredos de **bootstrap** (o `DATABASE_URL` PRIMÁRIO da aplicação e a chave de cifra) permanecem no
  env — não dá pra guardar a conexão do banco DENTRO do banco que ela conecta (ovo-galinha). O
  "trocar de banco" self-service se aplica a **BYO-DB por tenant / bancos secundários**, não ao
  Postgres primário da plataforma.

## Aceite
- Superadmin conecta **R2 e Vast pela UI** (Testar conexão OK) e o sistema passa a usar — sem env/código.
- Segredo cifrado, mascarado (não retorna plaintext), role-gated, auditado. Isolamento por escopo/tenant.
- As features que dependiam de acesso (evidência→R2 task-051, treino task-054) passam a ler a credencial
  do store de integrações. Testes: cifra, mascaramento, test-connection, isolamento, precedência env×painel.

## Risco
security — armazena/usa credenciais + isolamento por tenant. Review C2.
