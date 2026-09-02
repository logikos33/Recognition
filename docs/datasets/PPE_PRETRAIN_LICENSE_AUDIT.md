# Auditoria de licença — datasets públicos de EPI para pré-treino

**Data:** 2026-09-02 · **Escopo:** gate de licença para o estágio de pré-treino
(COCO → PPE público → fino no dado RVB), variantes A/B/C do detector.

**Relaciona:** `scripts/check_license_gate.py` (padrão da casa: zero copyleft forte no servido),
`docs/WEIGHTS_LICENSES.md` (mesmo processo, para pesos), `docs/datasets/PPE_LICENSE.md`
(documento anterior — ver "Correção" no fim).

**Regra aplicada:** licença não confirmada com fonte = **NÃO PODE**. Nunca assumir permissivo.

---

## Método e sua limitação

`universe.roboflow.com` responde **HTTP 403** a `curl`/WebFetch diretos (Cloudflare) e
`api.roboflow.com` responde **401** sem API key. As páginas foram lidas via proxy de texto
(`r.jina.ai`), e a licença extraída do bloco canônico de metadados da página
(`License[<nome>](<url creativecommons>)`), não do resumo do cabeçalho — os dois foram
conferidos e batem em 100% dos casos auditados.

**O que isto prova e o que não prova.** Prova a licença **declarada na página** de cada dataset.
**Não prova** que quem subiu tinha direito de declará-la: no Roboflow Universe o campo de licença
é preenchido pelo *uploader*, que pode ter raspado imagens de terceiros. Não confundir os dois.

---

## 1. SH17 — VETADO

| Item | Valor |
|---|---|
| Tamanho | 8.099 imagens / 75.994 instâncias |
| Classes (17) | Person, Head, Face, Glasses, Face-mask-medical, Face-guard, Ear, Earmuffs, Hands, Gloves, Foot, Shoes, Safety-vest, Tools, Helmet, Medical-suit, Safety-suit |
| **Licença** | **CC BY-NC-SA 4.0** |
| Veredito | **NÃO PODE** — `NC` = NonCommercial |

Fontes (três, concordantes):
- README oficial, verbatim: *"The SH17 dataset is released under CC BY-NC-SA 4.0 license."*
  — https://github.com/ahmadmughees/SH17dataset
- Paper: https://arxiv.org/abs/2407.04590 (CC BY-NC-SA 4.0)
- Página de download (Kaggle): https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection

Dois impedimentos independentes, não um: **NC** barra o uso comercial, e **SA** (ShareAlike)
contaminaria derivados. Basta o NC para reprovar.

> **Nuance que não salva o dataset.** As imagens vêm do Pexels, cuja licença própria permite uso
> comercial. Mas o que se baixa do SH17 é a **compilação anotada**, e é ela que está sob CC BY-NC-SA
> 4.0. O README ainda restringe explicitamente: *"intended for educational, research, and analysis
> purposes only."* Não usar.

> **O que É reaproveitável do SH17: a taxonomia.** Um esquema de classes é ideia, não expressão
> protegida pela licença dos dados. A VARIANTE C pode adotar o desenho parte-do-corpo+EPI
> (Person/Head/Face/Ear/Hands/Foot × Glasses/Earmuffs/Gloves/Shoes) **sem tocar nas imagens**.
> O que a licença nega é o dado, e é justamente o dado que a Variante C precisaria (ver §4).

---

## 2. Roboflow Universe — auditados um a um

Licença lida na página de cada dataset. `PODE` = permite uso comercial.

| # | Dataset | Tam. | Classes | Licença exata | Fonte (URL) | Veredito |
|---|---|---|---|---|---|---|
| R1 | **Detector_EPP_Earmuff_Gloves_Mask** (Priscilas Workspace) | 17.359 img | mask, earmuff, gloves, no earmuff, no glove, no mask | **CC BY 4.0** | https://universe.roboflow.com/priscilas-workspace-6zp93/detector_epp_earmuff_gloves_mask | **PODE** |
| R2 | **Safety_PPE** (Safety) | 6.6k img | Helmet, Glove, Goggles, Person, Shoe, Safety_Harness, No_Glove, No_Goggles, No_Shoe, No_Helmet, No_Harness, No_BreathingApparatus | **CC BY 4.0** | https://universe.roboflow.com/safety-jmser/safety_ppe | **PODE** |
| R3 | **Safety Gloves** (Roboflow Universe Projects) | 3.4k img | Gloves, NO-Gloves | **CC BY 4.0** | https://universe.roboflow.com/roboflow-universe-projects/safety-gloves-xbnf8 | **PODE** |
| R4 | **Earmuffs** (big-dataset-ppe) | 790 img | earmuff | **CC BY 4.0** | https://universe.roboflow.com/big-dataset-ppe/earmuffs-znwwu | **PODE** |
| R5 | **Construction Site Safety** (Roboflow Universe Projects) | 717 img | 25 cls: Hardhat, NO-Hardhat, Mask, NO-Mask, Safety Vest, NO-Safety Vest, Gloves, Person, Ladder, Safety Cone, + veículos | **CC BY 4.0** | https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety | **PODE** |
| R6 | **HAND NO GLOVES** (harami) | 200 img | vest, glasses, goggles, person, boots, shoes, face_mask, face_nomask, hand_glove, hand_noglove, head_helmet, head_nohelmet | **Public Domain (CC0 1.0)** | https://universe.roboflow.com/harami-rdknl/hand-no-gloves | **PODE** |
| R7 | **chvg+pictor** (ppe) | 2.5k img | head, glass, vest, person, red/yellow/blue/white (cor de capacete) | **CC BY 4.0** | https://universe.roboflow.com/ppe-mqz3t/chvg-pictor | **PODE** |
| R8 | **PPE Dataset for Workplace Safety** (SiaBar) | 1.6k img | *declara* Helmet, Mask, Glass, Vest, Glove, Person, Boots, Ear-protection | **CC BY 4.0** | https://universe.roboflow.com/siabar/ppe-dataset-for-workplace-safety | **PODE**, mas ver ⚠️ |
| R9 | **Earmuff Detector 2** (IIUM) | 154 img | earmuff, headset | **CC BY 4.0** | https://universe.roboflow.com/international-islamic-university-malaysia-msamv/earmuff-detector-2 | **PODE** (pequeno) |
| R10 | **ppe detection public** (ppe-wqipw) | 1.7k img | 48 classes | **CC BY 4.0** | https://universe.roboflow.com/ppe-wqipw/ppe-detection-public | PODE, **não recomendado** |

### Reprovados por encaixe (licença OK, dado imprestável)

| Dataset | Licença | Por que não serve |
|---|---|---|
| Gloves and bare hands detection | CC BY 4.0 | Classes reais = `paper`, `gloverotation`, `surgical-gloves` — luva **cirúrgica**, não é mão-vs-luva industrial |
| Body Parts Detection (kishans) | CC BY 4.0 | 35 classes de **anatomia médica** (Brain, Kidney, Liver, Pancreas...), não pessoas em cena |
| PPE Detection (school-cekug), PPE detection (augmented-startups), PPE_Detection (project-uyrxf) | CC BY 4.0 | Classes numéricas sem mapa (`0..6`) ou ruído (`rokok`, `kf80`) |
| ppe detection public (R10) | CC BY 4.0 | 48 classes com duplicata de caixa/grafia (`head`/`helmet`/`Helmet`, `glove`/`Gloves`/`hand_glove`) — despejo de vários datasets, exigiria remapeamento manual |

### ⚠️ R8 (SiaBar) — a lista de classes **mente** sobre a cobertura

A página declara 8 classes, mas a própria descrição diz, verbatim:

> "The dataset comprises annotated images spanning **four primary PPE categories**: Boots / Helmet /
> Person / Vest"
> `_Ear-protection_: adding images` · `_Mask_: Respiratory masks adding images` ·
> `_Glass_: Safety glasses adding images` · `_Glove_: Safety Gloves adding images`

Ou seja: **Ear-protection, Mask, Glass e Glove estão declaradas e vazias.** Todas as amostras da
página mostram só `Boots, Helmet, Person, Vest`. Das nossas 5 classes, R8 entrega **só Botas**.

> Este é o erro clássico da casa em forma nova: *lista de classes ≠ contagem de instâncias*. Nenhum
> número por classe desta tabela foi medido (ver "Não medido").

---

## 3. Fora do Roboflow

| Dataset | Tam. | Classes | Licença exata | Fonte | Veredito |
|---|---|---|---|---|---|
| **CPPE-5** | 1.029 img | Coverall, Face_Shield, Gloves, Goggles, Mask | **Anotações: Apache 2.0.** Imagens: **não são dos autores** — Flickr Terms of Use | https://sites.google.com/view/cppe5 · LICENSE do repo = Apache 2.0 (https://github.com/Rishit-dagli/CPPE-Dataset) | **PODE com ressalva** |
| **SH17** | 8.099 img | 17 (ver §1) | CC BY-NC-SA 4.0 | §1 | **NÃO PODE** |

**Ressalva do CPPE-5:** a licença é *split*. As anotações são Apache 2.0 (limpo). As imagens são de
terceiros no Flickr, e cada uma tem a licença que o fotógrafo escolheu — os autores do dataset
declaram não deter o copyright. Verbatim do site oficial: *"The annotations in this dataset are
licensed under the Apache 2.0 License"* / *"Use of the images must abide by the Flickr Terms of
Use."* Treinar um modelo com elas é defensável, redistribuí-las não é. **Não subir as imagens do
CPPE-5 para o nosso R2.** Domínio é médico/hospitalar, encaixe fraco (ver §4).

---

## 4. Encaixe com o problema RVB

Nossas 5 classes de presença, com o volume anotado hoje, contra o que o público cobre:

| Nossa classe | Caixas RVB | Melhor fonte pública **aprovada** | Ganho |
|---|---|---|---|
| **Luvas** | **304** (a mais pobre) | R1 (`gloves`/`no glove`, 17k) + R3 (`Gloves`/`NO-Gloves`, 3.4k) + R2 (`Glove`/`No_Glove`, 6.6k) | **Enorme** — a classe mais pobre é a mais bem coberta publicamente |
| Óculos | 635 | R2 (`Goggles`/`No_Goggles`), R7 (`glass`), R6 (`glasses`,`goggles`) | Bom |
| Máscara | 972 | R1 (`mask`/`no mask`, 17k), R5 (`Mask`/`NO-Mask`), R6 (`face_mask`/`face_nomask`) | Bom |
| Botas | 829 | R2 (`Shoe`/`No_Shoe`), R8 (`Boots`), R6 (`boots`,`shoes`) | Médio |
| **Protetor auditivo** | **3.087** (a mais rica) | R1 (`earmuff`/`no earmuff`), R4 (`earmuff`, 790) | Pouco necessário |

**A simetria é favorável e vale registrar:** o público é forte exatamente onde somos fracos (Luvas,
304 caixas) e é escasso exatamente onde já somos ricos (Protetor auditivo, 3.087). O pré-treino
público ataca o nosso gargalo real.

**Domínio.** R1/R2/R8 são industriais (R1 é `EPP` — nomenclatura hispanófona, provável indústria
LatAm). R5/R7 são **construção civil**, com foco em capacete e colete — que estão **FORA** da nossa
taxonomia de 6 classes. Todos são foto, não CFTV: ângulo alto, baixa resolução e motion blur da
câmera fixa continuam sendo lacuna que só o dado RVB fecha. Pré-treino ajuda a aprender o objeto,
não o nosso ponto de vista.

**Anotação de parte do corpo (decisivo para a VARIANTE C).** Procurei ativamente e **não existe**
fonte pública com licença comercial que anote mão / rosto / orelha como classe própria em pessoas
reais de cena industrial:
- SH17 tem exatamente isso (`Hands`, `Face`, `Ear`, `Head`, `Foot`) e é **NC** — vetado;
- o candidato "Body Parts Detection" é anatomia médica, não serve;
- R6 tem `hand_glove`/`hand_noglove`, que é **rótulo de estado da mão**, não a parte do corpo
  separada da luva — não dá para derivar ausência por sobreposição a partir dele.

> **Consequência direta para a decisão A/B/C:** a Variante C não tem pré-treino público disponível.
> Ou o corpo é anotado internamente, ou C entra no A/B **sem** a vantagem de pré-treino que A e B
> teriam — o que enviesaria o A/B contra ela por um motivo que não é o mérito da arquitetura.

---

## 5. Recomendação

**Ordem do pré-treino:** `COCO → [R1 + R3 + R2] → (opcional R5/R6) → fino no RVB`

1. **R1 — Detector_EPP_Earmuff_Gloves_Mask** (17.359 img, CC BY 4.0). Primeiro e principal: é o
   maior, é industrial, e cobre 3 das nossas 5 classes **com as duas polaridades** — serve à
   Variante A (presença) e à B (presença+ausência) sem reanotação.
2. **R3 — Safety Gloves** (3.4k, CC BY 4.0). Reforço dirigido ao gargalo (Luvas, 304 caixas).
3. **R2 — Safety_PPE** (6.6k, CC BY 4.0). Acrescenta Óculos e Botas com polaridade, e `Person`
   (útil ao estágio 1 da Variante A).
4. **Opcionais, só se sobrar orçamento:** R5 (máscara com polaridade, 717) e R6 (200 img, **CC0** —
   sem obrigação de atribuição, e é a única com as duas polaridades em 4 classes ao mesmo tempo).
5. **Não usar:** SH17 (NC). **Não usar em produção:** CPPE-5 (domínio médico; imagens não
   redistribuíveis) — no máximo experimento local que não sai da máquina.

**Variante C:** decidir antes do A/B se o corpo será anotado internamente. Sem isso, C compete em
desvantagem artificial. A taxonomia do SH17 pode ser copiada; o dado dele, não.

### Gate obrigatório antes de qualquer download entrar no treino

1. Exportar via SDK `roboflow` com API key. O zip traz `README.dataset.txt` / `README.roboflow.txt`
   **com a licença dentro** — conferir que bate com esta tabela. É a única verificação que enxerga
   o dado real, e não só a página.
2. Registrar a licença + `sha256` do zip exportado, no mesmo padrão de `docs/WEIGHTS_LICENSES.md`.
3. **Medir instâncias por classe após o export** (`R8` prova por que: lista de classes ≠ cobertura).
   Descartar dataset cuja classe-alvo venha vazia.
4. Emitir a atribuição CC BY 4.0 (R1–R5, R7–R10) em `THIRD_PARTY_NOTICES.txt`. **CC BY exige
   crédito** — é obrigação contratual, não cortesia. R6 é CC0 e dispensa.

> **Risco residual, declarado:** em todos os R*, a licença é *declarada pelo uploader*. Nenhum tem
> paper ou proveniência documentada; R1 tem 0 estrelas, 0 modelos e nenhuma descrição. Para um
> pré-treino que nunca é redistribuído (os pesos são derivados, não o dataset) o risco é baixo e
> aceitável. Se algum dia o **dataset** for redistribuído, ou se um cliente exigir cadeia de
> proveniência, isto precisa ser reexaminado.

---

## Não medido (declarado, não estimado)

- **Instâncias por classe** de qualquer dataset R1–R10. A página do Universe só mostra a lista de
  classes; a `/health` (distribuição real) exige autenticação — devolveu vazio sem API key.
- **Split train/val/test** e se o total exibido já inclui augmentação de versão.
- **Proveniência real das imagens** de qualquer dataset Roboflow (nenhum publica origem).
- **Sobreposição entre datasets** — R1/R2/R3/R10 podem compartilhar imagens; não verificado.
- **Ganho de mAP do pré-treino.** Nada aqui mede utilidade; só mede licença e encaixe declarado.

## Correção a `docs/datasets/PPE_LICENSE.md`

Aquele documento afirma CC BY 4.0 para *"'Construction Site Safety' ou 'HardHat & SafetyVest'"* —
**sem URL**, e com um "ou" que deixa o dataset indefinido. A licença lá **está correta** para o
Construction Site Safety (confirmado aqui como R5, com URL), mas o registro não passaria no próprio
gate: dataset sem identificador não é auditável. Duas correções pendentes:
- fixar a URL do R5 naquele doc;
- registrar que R5 tem só **717 imagens** e é de **construção civil** (capacete/colete), portanto
  encaixe fraco com a taxonomia RVB de 6 classes — não é a melhor escolha de bootstrap que o
  documento sugere. R1/R2/R3 são melhores.
