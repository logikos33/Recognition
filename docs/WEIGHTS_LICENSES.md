# Manifesto de pesos — licenças e integridade

**Relaciona:** task "treino não pode mentir" (deleção de simulação/Hub/legado Vast+Roboflow, guarda de
artefato verificável), ADR-0060, ADR-0061 (`docs/decisions/adr/0061-treino-nao-pode-mentir.md`),
`scripts/check_license_gate.py`, `docs/datasets/PPE_LICENSE.md`.

## Escopo

Todo peso pré-treinado (checkpoint de terceiro) que roda neste projeto — servido ou não — precisa estar
listado aqui, com licença conferida e, quando possível, `sha256` do arquivo real hospedado no nosso R2
(não do site do autor — o hash confere que o que ESTÁ no nosso bucket é de fato o que dizemos que é,
não uma cópia adulterada/trocada por engano). Zero peso AGPL/copyleft-forte ou de licença custom
restritiva a uso comercial entra nesta lista sem virar um VETADO explícito.

## Pesos ativos

| Modelo | Arquivo | sha256 | Licença | URL fonte | Data verificação | Verificado por |
|---|---|---|---|---|---|---|
| SAM ViT-B (Segment Anything) | `sam_vit_b_01ec64.pth` | `ec2df62732614e57411cdcf32a23ffdf28910380d03139ee0f4fcbe91eb8c912` | Apache 2.0 | github.com/facebookresearch/segment-anything | 2026-08-10 | Claude Code (download direto do R2 de produção, `models/sam_vit_b_01ec64.pth`, bucket API-V3) |
| GroundingDINO (SwinT-OGC) | `groundingdino_swint_ogc.pth` | `3b3ca2563c77c69f651d7bd133e97139c186df06231157a64c507099c52bc799` | Apache 2.0 | github.com/IDEA-Research/GroundingDINO | 2026-08-10 | Claude Code (download direto do R2 de produção, `models/groundingdino_swint_ogc.pth`, bucket API-V3) |
| DINOv2 ViT-S/14 (distilled, sem register tokens) | `dinov2_vits14_pretrain.pth` | `b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9` | Apache 2.0 | dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth (URL oficial linkada em github.com/facebookresearch/dinov2) | 2026-08-10 | Claude Code (download direto da URL oficial da Meta — `curl` + `shasum -a 256`, mesma metodologia do SAM/GroundingDINO acima; NÃO copiado de um mirror/terceiro) |
| OWLv2 base patch16 ensemble (zero-shot object detection) | `model.safetensors` (repo HF completo) | `e1e130b9e404cf91a75ad45644c1da9d7fa5284085eecc864266a6923efb99e7` (arquivo principal — repo tem múltiplos arquivos, ver nota) | Apache 2.0 | huggingface.co/google/owlv2-base-patch16-ensemble | 2026-08-11 | Claude Code (`GET https://huggingface.co/api/models/google/owlv2-base-patch16-ensemble` — `license: apache-2.0`; sha256 do `model.safetensors` via `.../tree/main`, LFS OID) |

**Nota sobre OWLv2:** usado só pela **busca por conteúdo** (`training/search_content.py`, RunPod, terceira carga do runner
genérico — `kind=JobKind.SEARCH`, sob o MESMO opt-in `training_third_party_cloud_enabled` da propagação, mais o guard
específico `SEARCH_CLOUD_ALLOWED_DATES`), fora do caminho de serving principal. Integridade: `revision` do commit HF
PINADA (`cfd3195ba4ea9592eec887ded089f4c08eff231d`, imutável — `from_pretrained(..., revision=...)`), não um sha256 de
arquivo único verificado manualmente como SAM/DINOv2: `from_pretrained` resolve VÁRIOS arquivos do repositório
(config, tokenizer, pesos) via o mecanismo de cache do `transformers`, não um único download por URL — pinar o commit
é o equivalente correto de "nunca resolver `main` às cegas" nesse mecanismo. O sha256 acima (do `model.safetensors`,
o arquivo de pesos propriamente dito) fica registrado por auditoria/paridade com a tabela, mas o executor NÃO faz
verificação manual desse hash antes de carregar (decisão registrada aqui — diferente do fluxo SAM/DINOv2, que baixa
por URL direta e por isso PRECISA verificar).

**Nota sobre SAM/GroundingDINO/DINOv2:** SAM e GroundingDINO são usados só pelo `pre-annotation-service`
(flag OFF por padrão — ver `app/domain/services/pre_annotation/`, `apps/frontend/src/AGENTS.md`), nunca
no caminho de serving principal (`services/api`, `services/inference`). Os dois já estavam hospedados em
`models/` no R2 de produção antes desta task; o `sha256` acima é a primeira verificação formal
registrada, calculada baixando o objeto real do bucket (não um valor copiado de terceiro). DINOv2 é usado
pela **propagação semeada** (`training/propagate_seeded.py`, RunPod — pré-anotação em GPU sob opt-in
`training_third_party_cloud_enabled`), também fora do caminho de serving: o pod baixa o checkpoint DIRETO
da URL oficial da Meta (nunca passa pelo nosso R2) e verifica o sha256 acima ANTES de carregar
(`download_and_verify_weight`, fail-closed — mismatch ou hash ausente aborta o job). O sha256 do SAM ViT-B
usado por essa mesma pipeline é o já pinado na linha acima (mesmo arquivo, mesma verificação).

**Edge (task "propagação no edge", D-93 em `docs/REGISTRO_DE_DECISOES.md`):** a propagação semeada passou a
rodar também no Jetson do site (`gpu_provider='edge'`, migration 116), além do RunPod — mas o executor é o
**MESMO** `training/propagate_seeded.py`, sem nenhuma linha alterada pro caminho onsite. `download_and_
verify_weight` roda idêntico nos dois destinos: o box baixa SAM (nosso R2, presigned) e DINOv2 (URL oficial
da Meta) e verifica os DOIS sha256 acima ANTES de carregar, exatamente como no RunPod — não existe um
caminho de carregamento de peso que pule essa verificação em nenhum dos dois provedores.

**Escolha do checkpoint DINOv2:** `vits14` (ViT-Small, 21M parâmetros, ~84MB) — o menor checkpoint oficial
da família DINOv2, sem os register tokens da variante `_reg` (arquitetura mais simples de carregar via
`torch.hub`, suficiente para embeddings de similaridade por classe no v1 da propagação — não é um
detector, só compara recortes). Se o v1 mostrar recall insuficiente em classes pequenas/distantes, um
checkpoint maior (`vitb14`/`vitl14`) pode ser reavaliado — mesmo processo de pinagem abaixo.

## Vetados — nunca empacotar

| Modelo | Motivo do veto |
|---|---|
| **DINOv3** | Licença custom da Meta (não Apache/MIT/BSD) — termos restritivos e histórico de disputa/litígio sobre uso comercial. **Não usar em nenhuma capacidade**, servida ou de treino, enquanto a licença não mudar. |
| **SAM2 (checkpoints oficiais)** | O peso oficial do SAM2 depende de `cc_torch`/componentes licenciados **CC BY-NC** (non-commercial) na distribuição padrão da Meta — incompatível com o produto comercial. Se o SAM2 for reavaliado no futuro, confirmar que o caminho de build/checkpoint usado não arrasta nenhum componente NC antes de empacotar (o SAM1/ViT-B usado hoje, Apache 2.0, não tem esse problema). |

## Processo pra adicionar um peso novo

1. Confirmar a licença na fonte oficial (repo do autor, não terceiros/mirrors) — Apache 2.0/MIT/BSD only,
   mesmo padrão do `AGPL_PACKAGES` de `scripts/check_license_gate.py` (zero copyleft forte).
2. Calcular `sha256` do arquivo que será de fato hospedado no nosso R2 (baixar do R2, não do site do
   autor — o hash é sobre o que RODA aqui, não sobre o que deveria rodar).
3. Adicionar uma linha nesta tabela antes do peso entrar em qualquer ambiente que não seja
   desenvolvimento local.
4. Se a licença for incerta ou restritiva (custom, NC, copyleft), listar em "Vetados" em vez de
   "Pesos ativos" e não integrar.
