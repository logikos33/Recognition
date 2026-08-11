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
| DINOv2 | *(checkpoint exato a definir)* | PENDENTE — checkpoint exato será pinado no PR da propagação | Apache 2.0 | github.com/facebookresearch/dinov2 | — | — |

**Nota sobre SAM/GroundingDINO:** usados só pelo `pre-annotation-service` (flag OFF por padrão — ver
`app/domain/services/pre_annotation/`, `apps/frontend/src/AGENTS.md`), nunca no caminho de serving
principal (`services/api`, `services/inference`). Os dois já estavam hospedados em `models/` no R2 de
produção antes desta task; o `sha256` acima é a primeira verificação formal registrada, calculada
baixando o objeto real do bucket (não um valor copiado de terceiro).

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
