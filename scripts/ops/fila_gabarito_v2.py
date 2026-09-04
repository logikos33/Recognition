#!/usr/bin/env python3
"""Fila de anotação do GABARITO v2 — quais 150 quadros o dono anota, e em que ordem.

O problema. O A/B das três variantes saiu não conclusivo porque o holdout tem ZERO
caixa de `Sem Luvas` e ZERO de `Sem mascara` (docs/quality/AB-HOLDOUT-V2.md). O que
desbloqueia não é treino, é GABARITO. Foram colhidos 440 quadros cheios 1920×1080 do
gravador do RVB (7 câmeras, 01/09 07h → 02/09 16h20, fábrica em operação). ~150 viram
gabarito. A hora do dono anotando é o recurso mais caro do projeto: 30-60 minutos.
Este script decide QUAIS e EM QUE ORDEM, para render o máximo por minuto.

⛔ RESTRIÇÃO INEGOCIÁVEL: nenhum CONTENDOR do A/B propõe caixa aqui. Nem para
pré-preencher, nem para ordenar. Contendores: variantes A (6ca25ee9), B (1deadfb0),
C (b9243540), baseline v10-ft (b3ae42b6) e o servido (46a30ed9). Gabarito
pré-preenchido pelo réu vira concordância medida, não verdade medida — o anotador
confirma a caixa que já está na tela. A saída deste script é LIMPA: só a ordem.

O detector de PESSOA (`yolox_nano`, COCO, classe `person`) NÃO é contendor: ele não
conhece nenhuma classe de EPI e não pode propor uma. Ele é usado só para SELECIONAR
e ORDENAR. É o mesmo objeto do caminho servido no edge (`PersonDetector` do
edge-sync-agent), com o ladrilhamento que o box usa.

O CRITÉRIO, declarado (ver `pontuar`):

  GATE (a) — anotável. Quadro sem pessoa enquadrada NÃO PODE conter ausência de EPI;
  é minuto perdido. Exige ≥1 pessoa com altura ≥ ALTURA_MINIMA px no quadro original.

  ORDEM (b) — probabilidade de conter ausência REAL, de sinais que não vêm de
  contendor:
    · VISIBILIDADE (peso 0,55) — altura em px da pessoa mais bem enquadrada. A mão
      é ~1/10 da altura da pessoa: com 420 px de pessoa a mão dá ~42 px, tamanho em
      que um humano separa luva de mão nua na tela. Caixa colada na borda SUPERIOR
      paga metade — cabeça cortada é rosto que não se julga (máscara, óculos).
    · DENSIDADE (peso 0,25) — mais gente no quadro, mais chances de alguém estar sem;
      e o minuto do dono rende mais caixas por quadro aberto. Retorno decrescente.
    · CONTEXTO (peso 0,20) — PRIOR DECLARADO, não medida: refeitório/convivência é
      onde máscara e luva SAEM (para comer, beber, fumar); porta de entrada é onde a
      pessoa ainda não colocou. Janelas de troca de turno e refeição idem. É palpite
      de domínio com peso pequeno de propósito, e as cotas por câmera (`--cota`)
      impedem que um prior errado sequestre o holdout.

  DEDUP POR RAJADA. Medido: a mediana do intervalo entre quadros consecutivos da
  mesma câmera é 0,5 s. Os 440 quadros são ~140 momentos distintos, não 440. Dois
  quadros da mesma rajada são quase o mesmo pixel: o segundo custa um minuto inteiro
  do dono e não acrescenta quase nada. Por isso a fila entrega PRIMEIRO um
  representante de cada rajada; só depois de esgotados os momentos distintos é que
  entra um segundo quadro de rajada (marcado `dup_rajada` na saída, para o dono poder
  parar antes deles sem perder nada).

Modos, na ordem em que se usa:

    --calibrar   mede a grade de ladrilhamento numa amostra (a grade errada
                 sub-detecta em silêncio e envenena toda a seleção)
    --pessoas    roda o detector de pessoa nos 440 e grava o JSONL
    --fila       pontua, ordena e grava o CSV + o relatório
    --autoteste  checa a lógica de pontuação/rajada/cota sem rede

    export DATABASE_URL=...
    eval "$(railway variables -s API-V3 -e Desenvolvimento --kv | grep ^R2_ | sed 's/^/export /')"
    python3 scripts/ops/fila_gabarito_v2.py --pessoas --modelo-pessoa <onnx> \\
        --jsonl docs/quality/evidence/gabarito-v2/pessoas-yolox-nano.jsonl
    python3 scripts/ops/fila_gabarito_v2.py --fila --jsonl <acima> \\
        --csv docs/quality/evidence/gabarito-v2/fila-gabarito-150.csv

Credenciais vêm do ambiente, nunca impressas, nunca escritas em arquivo.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

#: Gate (a). Altura em px, no quadro ORIGINAL, da menor pessoa que ainda vale abrir.
#: A mão é ~1/10 da altura: 200 px de pessoa → ~20 px de mão, o piso em que o humano
#: ainda separa luva de mão nua num JPEG de CFTV. Abaixo disso o dono não anota
#: `Sem Luvas` — ele ADIVINHA, e adivinhação no gabarito é pior que quadro nenhum.
ALTURA_MINIMA = 200

#: Altura em que a visibilidade satura (mão ≈ 42 px — leitura confortável).
ALTURA_PLENA = 420.0

#: Retorno decrescente da densidade: 1 pessoa → 0,45; 2 → 0,70; 3 → 0,83; 4 → 0,91.
BASE_DENSIDADE = 0.55

PESO_VISIBILIDADE = 0.55
PESO_DENSIDADE = 0.25
PESO_CONTEXTO = 0.20

#: Borda superior: caixa que começa a ≤ este y teve a cabeça cortada pelo quadro.
MARGEM_TOPO = 4

#: Fração da caixa MENOR que, se estiver dentro da maior, a torna a mesma pessoa.
#: Não é IoU: um FRAGMENTO (perna vista num ladrilho) tem IoU baixo com a pessoa
#: inteira e sobreviveria ao NMS, inflando a densidade. Contenção resolve.
CONTENCAO_MESMA_PESSOA = 0.70

#: Rajada: quadros da mesma câmera a menos disto um do outro são o mesmo momento.
#: 2 s é conservador — a mediana medida do acervo é 0,5 s e o segundo modo (5 s) já
#: agrupa quase igual (140 × 120 rajadas). Ver `--fila` no relatório.
SEGUNDOS_RAJADA = 2.0

#: PRIOR de contexto por câmera. Casado por substring no nome, minúsculo. É palpite
#: de domínio DECLARADO, com peso 0,20 — não é medida e não deve virar uma.
PRIOR_CAMERA = (
    ("convivência", 1.00),  # refeitório/descanso: máscara e luva saem aqui
    ("convivencia", 1.00),
    ("entrada", 0.60),      # porta: quem chega ainda não colocou
    ("expedição", 0.60),
    ("expedicao", 0.60),
)
PRIOR_CAMERA_PADRAO = 0.30

#: RENDIMENTO MEDIDO das três classes de CABEÇA (`Sem Óculos`, `Sem protetor de
#: ouvido`, `Uso incorreto de mascara`), por câmera. Diferente de PRIOR_CAMERA:
#: isto NÃO é palpite, é contagem. Entre os recortes de pessoa daquela câmera que
#: um humano já anotou à mão, a fração que recebeu pelo menos uma das três:
#:
#:   WITH crops AS (SELECT DISTINCT f.id, f.camera_id FROM training_frames f
#:                    JOIN frame_annotations a ON a.frame_id=f.id
#:                   WHERE f.tenant_id=:t AND f.width<1280 AND a.source='manual'),
#:        tot AS (SELECT camera_id, count(*) n FROM crops GROUP BY 1)
#:   SELECT c.name, t.n,
#:          100.0*count(DISTINCT a.frame_id) FILTER (WHERE a.class_name IN
#:            ('Sem protetor de ouvido','Uso incorreto de mascara','Sem Óculos'))/t.n
#:     FROM crops cr JOIN tot t USING (camera_id)
#:     LEFT JOIN cameras c ON c.id=cr.camera_id
#:     LEFT JOIN frame_annotations a ON a.frame_id=cr.id AND a.source='manual'
#:    GROUP BY 1, t.n HAVING t.n >= 20;
#:
#: Casa por nome EXATO normalizado, não por substring: "entrada expedicao" é
#: prefixo de "entrada expedicao 02", e uma tabela MEDIDA por câmera não pode
#: herdar em silêncio o número de outra. Câmera com menos de 20 recortes
#: anotados não tem medida e cai em RENDIMENTO_CABECA_PADRAO — a taxa global
#: (900/2705 recortes = 33,3%), que é o que se sabe quando não se sabe mais nada.
#: (n de recortes entre parênteses: é o que dá ou tira confiança de cada linha.)
RENDIMENTO_CABECA = {
    "espaco de convivencia": 0.862,              # (29)
    "entrada expedicao": 0.653,                  # (294)
    "corredor seguranca do trabalho": 0.634,     # (205)
    "entrada preparacao": 0.617,                 # (227)
    "qualidade 06": 0.458,                       # (107)
    "qualidade 05": 0.410,                       # (200)
    "sala de colagem": 0.228,                    # (254)
    "manutencao": 0.222,                         # (27)
    "entrada usinagem madeira 01": 0.218,        # (431)
    "entrada usinagem madeira 2": 0.154,         # (402)
    "corredor lateral usinagem madeira": 0.106,  # (293)
    "montagem artefatos madeira": 0.029,         # (35)
    "qualidade 02": 0.026,                       # (38)
    "entrada wc usinagem papelao": 0.011,        # (90)
    "qualidade 04": 0.000,                       # (35)
}
RENDIMENTO_CABECA_PADRAO = 0.333

#: O mesmo rendimento medido, aberto POR CLASSE — é o que permite dizer, antes
#: da sentada, quantos quadros devem trazer CADA uma das três. Mesma query do
#: RENDIMENTO_CABECA, com um FILTER por class_name em vez do IN das três.
#: Ordem da tupla: (Sem protetor de ouvido, Uso incorreto de mascara, Sem Óculos).
RENDIMENTO_POR_CLASSE = {
    "espaco de convivencia": (0.690, 0.000, 0.207),
    "entrada expedicao": (0.347, 0.031, 0.323),
    "corredor seguranca do trabalho": (0.424, 0.176, 0.063),
    "entrada preparacao": (0.458, 0.093, 0.093),
    "qualidade 06": (0.252, 0.009, 0.206),
    "qualidade 05": (0.350, 0.000, 0.060),
    "sala de colagem": (0.102, 0.138, 0.031),
    "manutencao": (0.074, 0.111, 0.037),
    "entrada usinagem madeira 01": (0.074, 0.135, 0.023),
    "entrada usinagem madeira 2": (0.030, 0.109, 0.020),
    "corredor lateral usinagem madeira": (0.003, 0.099, 0.003),
    "montagem artefatos madeira": (0.000, 0.000, 0.029),
    "qualidade 02": (0.026, 0.000, 0.000),
    "entrada wc usinagem papelao": (0.011, 0.000, 0.011),
    "qualidade 04": (0.000, 0.000, 0.000),
}
#: Taxa global, para câmera sem medida própria (2.705 recortes).
RENDIMENTO_POR_CLASSE_PADRAO = (0.187, 0.088, 0.076)

NOMES_CABECA = ("Sem protetor de ouvido", "Uso incorreto de mascara", "Sem Óculos")

#: Fração das vezes em que o dono CONSEGUIU decidir (respondeu `sim` ou `nao`,
#: não `nao_sei`), por altura da pessoa. Medido nos 246 vereditos de `Sem Luvas`
#: da sentada anterior — a classe FÁCIL, cuja evidência (a mão) é ~10% da altura
#: da pessoa:
#:     350-500 px : nao_sei 47,4% de 78  →  decide 52,6%
#:     500-750 px : nao_sei 32,1% de 53  →  decide 67,9%
#: É o desconto mais honesto disponível, e é EMPRESTADO: mede a mão, não a
#: orelha. Serve de âncora porque as regiões são da mesma ordem (orelha 8,8%,
#: máscara 12,2%, óculos 15,8% da altura da pessoa, contra ~10% da mão), mas
#: rosto exige a pessoa VOLTADA para a câmera e mão não — então para as três é
#: teto, não previsão. Por isso o relatório dá FAIXA (bruto → descontado), nunca
#: um número só.
DECIDE_POR_ALTURA = ((500, 0.679), (350, 0.526))

#: LEGIBILIDADE MEDIDA por câmera: a fração das respostas da sentada anterior em
#: que o dono CONSEGUIU decidir (não respondeu `nao_sei`), em quadro CHEIO
#: 1920x1080 — que é a tarefa real, não o recorte:
#:
#:   SELECT cam.name, count(*), count(*) FILTER (WHERE h.verdict='nao_sei')
#:     FROM holdout_verdicts h JOIN training_frames f ON f.id=h.frame_id
#:     LEFT JOIN cameras cam ON cam.id=f.camera_id
#:    WHERE h.tenant_id=:t AND h.class_id IN (5,100009) GROUP BY 1;
#:
#: ⛔ ISTO EXISTE PORQUE O RENDIMENTO POR RECORTE MENTE SOBRE O QUADRO CHEIO.
#: `Espaço de convivência` lidera o RENDIMENTO_CABECA com 86,2% — e produziu
#: **0 `sim` em 41 quadros** na sentada anterior, com 70 `nao_sei` em 82
#: respostas. O recorte de pessoa é um close: nele qualquer um vê a orelha. No
#: quadro cheio daquela câmera, ninguém vê. Prevalência e legibilidade são
#: coisas diferentes, e só a segunda depende do ENQUADRAMENTO.
#:
#: E não é só distância: `Corredor Lateral` tem pessoa mediana de 351 px e
#: legibilidade 0,962; `Espaço de convivência` tem 358 px e 0,146. Mesma altura,
#: oito vezes menos resposta. O que muda é o ângulo — por isso este fator é POR
#: CÂMERA e multiplica o score inteiro, em vez de virar mais uma parcela somada
#: (soma deixaria uma câmera ilegível compensar com prevalência alta, que é
#: exatamente o erro que gastaria 35 quadros da fila em convivência).
#:
#: Câmera sem medida usa a taxa agregada das 8 medidas (256 `nao_sei` em 491
#: respostas → 0,479): não é otimismo nem punição, é o que se sabe.
LEGIBILIDADE_CAMERA = {
    "corredor lateral usinagem madeira": 0.962,  # 26 respostas
    "entrada preparacao": 0.615,                 # 104
    "entrada expedicao 02": 0.544,               # 68
    "entrada usinagem madeira 2": 0.524,         # 84
    "entrada usinagem madeira 01": 0.500,        # 32
    "entrada expedicao": 0.500,                  # 36
    "entrada wc usinagem papelao": 0.322,        # 59
    "espaco de convivencia": 0.146,              # 82
}
LEGIBILIDADE_PADRAO = 0.479

#: Janelas (hora local do frame, UTC-3) de troca de turno e refeição — momentos em
#: que o EPI sai ou ainda não entrou. Fora delas o prior de contexto paga 0,7.
#:
#: ⚠️ NÃO se aplica ao perfil `cabeca`, e por medida: o rendimento das três
#: classes por HORA (mesma query do RENDIMENTO_CABECA, agrupada por
#: extract(hour from captured_at)) fica entre 15,5% e 34,0% ao longo de todo o
#: expediente, SEM acompanhar estas janelas — 12h, que está DENTRO, é a pior
#: hora medida (16,3%, n=796); 09h, também dentro, dá 17,5% (n=361); 19h, fora,
#: dá 28,3%. (07h marca 92,6%, mas com n=27 — um lote, não uma hora.) Um fator
#: que o dado contradiz não é prior conservador, é ruído com peso. No perfil
#: `cabeca` a hora vale 1,0 e a fila não paga por ela.
JANELAS_TRANSICAO = ((7, 9), (11, 14), (16, 18))
FATOR_FORA_DA_JANELA = 0.70

#: ⚠️ `captured_at` vem com tzinfo=UTC mas o VALOR é o relógio de parede da
#: fábrica — o gravador grava a hora local e o campo é rotulado UTC. Conferido
#: contra o relógio QUEIMADO NA IMAGEM: o frame cujo captured_at é
#: 2026-09-01T07:00:00+00:00 tem "01/09/2026 07:00:00" impresso no canto. Deslocar
#: por -3 h (o palpite óbvio) jogaria a janela do almoço nas 15 h e a colheita
#: inteira (07:00→16:20) viraria uma madrugada de 04:00→13:20 numa fábrica que
#: comprovadamente está operando. Zero, então — e medido, não suposto.
FUSO_FABRICA = timedelta(0)


class Perfil:
    """QUE ausência a fila está caçando — e, por consequência, o que é "anotável".

    Existe porque a evidência das cinco classes NÃO tem o mesmo tamanho, e isso
    é medido, não suposto. Nos 962 recortes anotados à mão (`width<1280`, que
    são recortes de pessoa), a altura da caixa como fração da altura do recorte:

        Sem Luvas                  p50 = 1,000   y_centro 0,500
        Sem mascara                p50 = 1,000   y_centro 0,500
        Sem Óculos                 p50 = 0,158   y_centro 0,358
        Uso incorreto de mascara   p50 = 0,122   y_centro 0,251
        Sem protetor de ouvido     p50 = 0,088   y_centro 0,213

    As duas primeiras são marcadas na PESSOA INTEIRA (caixa = recorte, centro no
    meio). As três últimas são marcadas na CABEÇA — 9% a 16% da altura da pessoa,
    no terço de cima. Numa pessoa de 322 px (a mediana do holdout atual) a região
    da orelha tem 28 px; numa de 536 px (a mediana dos quadros em que o dono
    respondeu `sim`) tem 47 px. É a MESMA imagem: muda o que se precisa enxergar
    nela. Um gate calibrado para a mão não serve para a orelha.

    `PERFIL_MAOS` é o comportamento histórico, intacto — é o default de todas as
    funções para que a fila de 02/09 continue reproduzível byte a byte.
    """

    def __init__(self, nome, altura_minima, pesos, rendimento=None,
                 usa_janela=True, legibilidade=None):
        self.nome = nome
        self.altura_minima = altura_minima
        self.peso_visibilidade, self.peso_densidade, self.peso_contexto = pesos
        self.rendimento = rendimento
        self.usa_janela = usa_janela
        self.legibilidade = legibilidade

    def legivel(self, camera_nome) -> float:
        """Quanto do que ESTÁ no quadro daquela câmera o dono consegue julgar."""
        if self.legibilidade is None:
            return 1.0
        return self.legibilidade.get(
            normalizar_nome(camera_nome), LEGIBILIDADE_PADRAO
        )


PERFIL_MAOS = Perfil(
    "maos",
    altura_minima=ALTURA_MINIMA,
    pesos=(PESO_VISIBILIDADE, PESO_DENSIDADE, PESO_CONTEXTO),
)

#: Gate do perfil `cabeca`. MEDIDO nos 246 vereditos que o dono já deu: abaixo de
#: 350 px de pessoa ele respondeu `sim` para `Sem Luvas` ZERO vezes em 53 quadros
#: (0-250 px: 0/15; 250-350 px: 0/38). A taxa de `sim` só existe acima disso
#: (350-500 px: 25,6%; 500-750 px: 60,4%). E `Sem Luvas` é a classe FÁCIL — a mão
#: aparece de qualquer ângulo, a orelha só aparece se a cabeça estiver legível.
#: Manter 200 px aqui seria encher a fila de quadro que já se sabe que não rende.
ALTURA_MINIMA_CABECA = 350

PERFIL_CABECA = Perfil(
    "cabeca",
    altura_minima=ALTURA_MINIMA_CABECA,
    # Visibilidade cede peso para o CONTEXTO porque, no perfil cabeça, contexto
    # deixou de ser palpite: é o rendimento contado por câmera (RENDIMENTO_CABECA,
    # 15 câmeras, 2.705 recortes). Peso pequeno se dá a palpite, não a medida.
    pesos=(0.45, 0.20, 0.35),
    rendimento=RENDIMENTO_CABECA,
    usa_janela=False,
    legibilidade=LEGIBILIDADE_CAMERA,
)

PERFIS = {p.nome: p for p in (PERFIL_MAOS, PERFIL_CABECA)}

#: Pool do gabarito: quadro CHEIO que ainda não é holdout, nunca foi julgado e
#: — o ponto que quase passou — NUNCA FOI TREINADO.
#:
#: ⛔ `is_annotated = false` NÃO é filtro de conveniência, é a trava de
#: contaminação. O export de treino seleciona exatamente
#: `is_annotated = TRUE AND dataset_role = 'pool'` (versioning_v2.
#: _snapshot_labeled_frames, migration 133): todo quadro anotado que está no
#: pool JÁ FOI para dentro das dataset_versions (vv17*, vv18-multiescala). Medir
#: o modelo num quadro que ele treinou é medir memorização, e o A/B sairia
#: melhor do que a realidade sem nada acusar. `dataset_versions.split_membership`
#: está NULL em todas as versões deste tenant, então não dá para provar caso a
#: caso quais entraram — e por isso a regra tem de ser a conservadora.
#: (Custou 57 dos 197 quadros da primeira montagem da fila v3. Vale os 57.)
#:
#: `dataset_role='pool'` exclui os 246 já julgados por construção (eles são
#: 'holdout'), e o NOT EXISTS é o cinto de segurança — reapresentar um quadro já
#: julgado gastaria o minuto mais caro do projeto para reconfirmar o que já se
#: sabe. Sem janela de tempo: o acervo cheio vai de 10/08 a 02/09 e a colheita
#: nova não é diária.
_SQL_POOL = """
SELECT f.id::text AS frame_id, f.r2_key, f.camera_id::text AS camera_id,
       c.name AS camera_name, f.captured_at, f.created_at, f.width, f.height
  FROM public.training_frames f
  LEFT JOIN public.cameras c ON c.id = f.camera_id
 WHERE f.tenant_id = %(tenant)s
   AND f.width >= %(largura_min)s
   AND f.dataset_role = 'pool'
   AND f.is_annotated = false
   AND NOT EXISTS (SELECT 1 FROM public.holdout_verdicts h
                    WHERE h.frame_id = f.id AND h.tenant_id = %(tenant)s)
   AND (%(cameras)s::text[] IS NULL OR c.name = ANY(%(cameras)s::text[]))
 ORDER BY f.captured_at, f.id
"""

_SQL_FRAMES = """
SELECT f.id::text AS frame_id, f.r2_key, f.camera_id::text AS camera_id,
       c.name AS camera_name, f.captured_at, f.created_at, f.width, f.height
  FROM public.training_frames f
  LEFT JOIN public.cameras c ON c.id = f.camera_id
 WHERE f.tenant_id = %(tenant)s
   AND f.created_at > now() - (%(horas)s || ' hours')::interval
   AND f.width >= %(largura_min)s
   AND f.is_annotated = false
 ORDER BY f.captured_at, f.id
"""


# ── Pontuação (sem rede, sem banco — é o que o autoteste exercita) ────────────

def fundir(caixas: list[dict]) -> list[dict]:
    """União de grades: fica a MAIOR caixa de cada pessoa.

    Por que duas grades (medido em 40 quadros, `--calibrar`): o quadro inteiro em
    416×416 encolhe a pessoa distante até o YOLOX perdê-la (26/40 quadros com
    pessoa contra 33/40); mas o ladrilho RECORTA quem é alto — a maior caixa da
    grade 3×3 mede exatamente 432 px, que é a altura do ladrilho, não da pessoa.
    Uma grade só erra de um dos dois lados. A altura é justamente o sinal que
    ordena a fila, então medir errado ordenaria errado.

    (A grade 2×2 do edge foi descartada aqui: acusa pessoa em 40/40 quadros,
    inclusive no pátio comprovadamente vazio — foi calibrada para 704×480.)
    """
    ordenadas = sorted(caixas, key=lambda c: -(c["w"] * c["h"]))
    mantidas: list[dict] = []
    for c in ordenadas:
        area = max(1, c["w"] * c["h"])
        engolida = False
        for m in mantidas:
            ix = max(0, min(c["x"] + c["w"], m["x"] + m["w"]) - max(c["x"], m["x"]))
            iy = max(0, min(c["y"] + c["h"], m["y"] + m["h"]) - max(c["y"], m["y"]))
            if (ix * iy) / area >= CONTENCAO_MESMA_PESSOA:
                engolida = True
                break
        if not engolida:
            mantidas.append(c)
    return mantidas


def pessoa_anotavel(caixa: dict, perfil: Perfil = PERFIL_MAOS) -> bool:
    """A pessoa é grande o bastante para o dono julgar a evidência deste perfil?"""
    return caixa["h"] >= perfil.altura_minima


def visibilidade(caixas: list[dict], perfil: Perfil = PERFIL_MAOS) -> float:
    """0..1 da MELHOR pessoa do quadro. Cabeça cortada pela borda paga metade."""
    melhor = 0.0
    for c in caixas:
        if not pessoa_anotavel(c, perfil):
            continue
        v = min(1.0, c["h"] / ALTURA_PLENA)
        if c["y"] <= MARGEM_TOPO:
            v *= 0.5
        melhor = max(melhor, v)
    return melhor


def densidade(caixas: list[dict], perfil: Perfil = PERFIL_MAOS) -> float:
    n = sum(1 for c in caixas if pessoa_anotavel(c, perfil))
    return 0.0 if n == 0 else 1.0 - BASE_DENSIDADE**n


def contexto(
    camera_nome: str | None,
    captured_at: datetime | None,
    perfil: Perfil = PERFIL_MAOS,
) -> float:
    """Quanto o CONTEXTO do quadro promete — e de onde vem essa promessa.

    Perfil `maos`: PRIOR declarado, casado por substring. Não é medida.
    Perfil `cabeca`: RENDIMENTO CONTADO por câmera, casado por nome exato
    normalizado, sem fator de hora (ver JANELAS_TRANSICAO).
    """
    if perfil.rendimento is not None:
        return perfil.rendimento.get(
            normalizar_nome(camera_nome), RENDIMENTO_CABECA_PADRAO
        )
    nome = (camera_nome or "").lower()
    base = PRIOR_CAMERA_PADRAO
    for chave, valor in PRIOR_CAMERA:
        if chave in nome:
            base = max(base, valor)
    if not perfil.usa_janela:
        return base
    if captured_at is None:
        return base * FATOR_FORA_DA_JANELA
    hora = (captured_at + FUSO_FABRICA).hour
    dentro = any(ini <= hora < fim for ini, fim in JANELAS_TRANSICAO)
    return base if dentro else base * FATOR_FORA_DA_JANELA


def pontuar(registro: dict, perfil: Perfil = PERFIL_MAOS) -> dict:
    """Score do quadro + as três parcelas, para o relatório poder ser auditado."""
    caixas = registro.get("pessoas") or []
    v = visibilidade(caixas, perfil)
    d = densidade(caixas, perfil)
    c = contexto(registro.get("camera_name"), _quando(registro), perfil)
    # MULTIPLICA, não soma: o que está no quadro (v, d, c) só vira gabarito se
    # for legível ali. Somar deixaria prevalência alta compensar enquadramento
    # ruim — ver LEGIBILIDADE_CAMERA e os 0 `sim` em 41 quadros da convivência.
    legivel = perfil.legivel(registro.get("camera_name"))
    return {
        "visibilidade": round(v, 4),
        "densidade": round(d, 4),
        "contexto": round(c, 4),
        "legibilidade": round(legivel, 4),
        "score": round(
            (
                perfil.peso_visibilidade * v
                + perfil.peso_densidade * d
                + perfil.peso_contexto * c
            )
            * legivel,
            4,
        ),
        "n_pessoas": len(caixas),
        "n_anotaveis": sum(1 for x in caixas if pessoa_anotavel(x, perfil)),
        "altura_max": max((x["h"] for x in caixas), default=0),
    }


def _quando(registro: dict) -> datetime | None:
    bruto = registro.get("captured_at")
    if isinstance(bruto, datetime):
        return bruto
    if not bruto:
        return None
    return datetime.fromisoformat(bruto)


def rajadas(registros: list[dict], segundos: float = SEGUNDOS_RAJADA) -> dict[str, int]:
    """frame_id → id da rajada. Mesma câmera + intervalo ≤ `segundos` = mesmo momento."""
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_camera[r.get("camera_id") or "?"].append(r)
    saida: dict[str, int] = {}
    proxima = 0
    for camera in sorted(por_camera):
        anterior: datetime | None = None
        atual = -1
        for r in sorted(por_camera[camera], key=lambda x: (_quando(x) or datetime.min, x["frame_id"])):
            quando = _quando(r)
            novo = (
                anterior is None
                or quando is None
                or (quando - anterior).total_seconds() > segundos
            )
            if novo:
                proxima += 1
                atual = proxima
            saida[r["frame_id"]] = atual
            anterior = quando
    return saida


def normalizar_nome(nome: str | None) -> str:
    """Nome de câmera comparável: sem acento, sem caixa, sem espaço sobrando.

    O dono escreve "corredor lateral usinagem" e o cadastro diz "Corredor
    Lateral usinagem Madeira". Exigir grafia exata faria a prioridade dele
    falhar em silêncio — que é pior que não ter prioridade nenhuma.
    """
    puro = unicodedata.normalize("NFKD", str(nome or ""))
    return "".join(c for c in puro if not unicodedata.combining(c)).lower().strip()


def montar_fila(
    registros: list[dict],
    alvo: int,
    cota: float,
    prioritarias: set[str] | None = None,
) -> list[dict]:
    """A fila, na ordem em que o dono anota.

    Passe 1 — um representante por rajada (o de maior score), rajadas em ordem de
    score. É onde está TODO o ganho por minuto: 440 quadros são ~140 momentos.
    Passe 2 — só se faltar vaga, o segundo melhor quadro das melhores rajadas,
    marcado `dup_rajada=True` para o dono poder parar antes deles.

    `cota` é a fração máxima de UMA câmera na fila (diversidade: um prior de
    contexto errado não pode sequestrar o holdout). Excedente vai para o fim da
    fila, marcado `acima_da_cota=True` — nunca é descartado, só despriorizado.

    `prioritarias` é conhecimento do DONO sobre a fábrica, e ele vence o score:
    a pontuação mede o que a imagem mostra (pessoa grande, mão visível), não
    onde o EPI é exigido. Medido em 02/09: a colheita rendeu 113 quadros do
    "Espaço de convivência" e ZERO do "Corredor Lateral usinagem", e o dono
    apontou que as entradas de produção é que geram protetor auricular. Câmera
    fora da lista NÃO é descartada — vai para depois de todas as prioritárias,
    marcada `fora_da_prioridade=True`, porque um dia com pouca gente numa
    entrada não pode deixar o dono sem nada para anotar.
    Casa por substring, sem acento e sem caixa: o dono escreve "corredor
    lateral usinagem" e o cadastro diz "Corredor Lateral usinagem Madeira".
    """
    aptos = [r for r in registros if r["_p"]["n_anotaveis"] > 0]
    grupo = rajadas(aptos)
    por_rajada: dict[int, list[dict]] = defaultdict(list)
    for r in aptos:
        por_rajada[grupo[r["frame_id"]]].append(r)
    for lista in por_rajada.values():
        lista.sort(key=lambda r: (-r["_p"]["score"], r["frame_id"]))

    def e_prioritaria(r: dict) -> bool:
        if not prioritarias:
            return True
        nome = normalizar_nome(r.get("camera_name"))
        return any(p in nome for p in prioritarias)

    # A prioridade do dono entra ANTES do score na ordenação — não como filtro.
    ordem_rajadas = sorted(
        por_rajada,
        key=lambda g: (
            not e_prioritaria(por_rajada[g][0]),
            -por_rajada[g][0]["_p"]["score"],
            g,
        ),
    )

    teto = max(1, int(alvo * cota))
    fila: list[dict] = []
    excedente: list[dict] = []
    usados: Counter = Counter()

    def empurrar(r: dict, dup: bool, rodada: int) -> None:
        item = dict(r)
        item["dup_rajada"] = dup
        item["rajada"] = grupo[r["frame_id"]]
        item["acima_da_cota"] = False
        item["fora_da_prioridade"] = not e_prioritaria(r)
        if usados[r["camera_id"]] >= teto:
            item["acima_da_cota"] = True
            excedente.append(item)
            return
        usados[r["camera_id"]] += 1
        item["passe"] = rodada
        fila.append(item)

    for g in ordem_rajadas:
        empurrar(por_rajada[g][0], dup=False, rodada=1)

    rodada = 2
    while len(fila) < alvo:
        restou = False
        for g in ordem_rajadas:
            if len(por_rajada[g]) >= rodada:
                restou = True
                empurrar(por_rajada[g][rodada - 1], dup=True, rodada=rodada)
                if len(fila) >= alvo:
                    break
        if not restou:
            break
        rodada += 1

    for item in excedente:
        item["passe"] = 99
    fila.extend(excedente)
    for i, item in enumerate(fila, 1):
        item["posicao"] = i
    return fila[:alvo] if alvo else fila


# ── Modo --pessoas ────────────────────────────────────────────────────────────

def _cliente_r2():
    from amostra_variante_c_fotos import _cliente_r2 as fabrica  # noqa: PLC0415

    return fabrica()


def _detector(caminho: str, grade: tuple[int, int], limiar: float):
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "services" / "edge-sync-agent")
    )
    from app.collector.person_detector import PersonDetector  # noqa: PLC0415

    det = PersonDetector(
        model_path=caminho, confidence=limiar, tile_grid=grade
    )
    if not det.is_ready:
        raise RuntimeError(
            f"detector de pessoa não carregou de {caminho} — sem substituto silencioso"
        )
    return det


def _frames_do_banco(args) -> list[dict]:
    import psycopg2  # noqa: PLC0415
    from psycopg2.extras import RealDictCursor  # noqa: PLC0415

    # `--pool` troca a janela de tempo ("o que chegou nas últimas N horas") pelo
    # emprego do quadro ("o que ainda não é gabarito"). A colheita nova não é
    # diária: com --horas, um acervo de 10/08 a 02/09 devolve zero linha hoje.
    if args.pool:
        sql, params = _SQL_POOL, {
            "tenant": args.tenant,
            "largura_min": args.largura_min,
            "cameras": args.cameras or None,
        }
    else:
        sql, params = _SQL_FRAMES, {
            "tenant": args.tenant,
            "horas": str(args.horas),
            "largura_min": args.largura_min,
        }
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def _bytes_do_frame(s3, cache: Path, fr: dict) -> bytes:
    local = cache / f"{fr['frame_id']}.jpg"
    if local.exists():
        return local.read_bytes()
    bruto = s3.get_object(Bucket=os.environ["R2_BUCKET"], Key=fr["r2_key"])["Body"].read()
    local.write_bytes(bruto)
    return bruto


def pessoas(args) -> int:
    frames = _frames_do_banco(args)
    print(f"frames: {len(frames)}")
    if not frames:
        print("ERRO: nenhum frame casou com o filtro. Parando.")
        return 1

    s3 = _cliente_r2()
    args.cache.mkdir(parents=True, exist_ok=True)
    dets = [(g, _detector(args.modelo_pessoa, g, args.limiar_pessoa)) for g in args.grades]
    grades_txt = "+".join(f"{nx}x{ny}" for nx, ny in args.grades)
    print(f"detector: {args.modelo_pessoa}  grades={grades_txt}  "
          f"limiar={args.limiar_pessoa}")

    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    falhas = 0
    with args.jsonl.open("w") as out:
        for i, fr in enumerate(frames, 1):
            try:
                bruto = _bytes_do_frame(s3, args.cache, fr)
                cruas: list[dict] = []
                for grade, det in dets:
                    res = det.detect(bruto)
                    if res.undetermined:
                        raise RuntimeError("detector indeterminado (erro de inferência)")
                    cruas.extend(
                        {"x": b.x, "y": b.y, "w": b.w, "h": b.h,
                         "conf": b.confidence, "grade": f"{grade[0]}x{grade[1]}"}
                        for b in res.boxes
                    )
                caixas = fundir(cruas)
            except Exception as exc:  # noqa: BLE001
                falhas += 1
                print(f"  FALHA {fr['frame_id']}: {exc}")
                continue
            out.write(
                json.dumps(
                    {
                        "frame_id": fr["frame_id"],
                        "r2_key": fr["r2_key"],
                        "camera_id": fr["camera_id"],
                        "camera_name": fr["camera_name"],
                        "captured_at": fr["captured_at"].isoformat()
                        if fr["captured_at"]
                        else None,
                        "created_at": fr["created_at"].isoformat()
                        if fr["created_at"]
                        else None,
                        "width": fr["width"],
                        "height": fr["height"],
                        "detector_pessoa": Path(args.modelo_pessoa).name,
                        "grades": grades_txt,
                        "limiar_pessoa": args.limiar_pessoa,
                        "pessoas": caixas,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            if i % 50 == 0:
                print(f"  {i}/{len(frames)}")
    print(f"gravado: {args.jsonl}  ({len(frames) - falhas} ok, {falhas} falhas)")
    return 1 if falhas else 0


def calibrar(args) -> int:
    """A grade de ladrilhamento é o joelho da medição — 2x2 foi calibrado para
    704×480 no edge, e aqui o quadro é 1920×1080. Grade errada sub-detecta em
    SILÊNCIO, e a seleção inteira sai envenenada. Então mede-se."""
    frames = _frames_do_banco(args)[: args.amostra]
    s3 = _cliente_r2()
    args.cache.mkdir(parents=True, exist_ok=True)
    brutos = [_bytes_do_frame(s3, args.cache, fr) for fr in frames]
    print(f"amostra: {len(brutos)} frames  limiar={args.limiar_pessoa}")
    print(f"{'grade':>7} {'frames c/ pessoa':>17} {'pessoas':>8} "
          f"{'pessoas ≥200px':>15} {'seg':>6}")
    import time  # noqa: PLC0415

    for grade in ((1, 1), (2, 2), (3, 3), (4, 3), (5, 3)):
        det = _detector(args.modelo_pessoa, grade, args.limiar_pessoa)
        t0 = time.time()
        com, total, grandes = 0, 0, 0
        for b in brutos:
            res = det.detect(b)
            if res.boxes:
                com += 1
            total += len(res.boxes)
            grandes += sum(1 for x in res.boxes if x.h >= ALTURA_MINIMA)
        print(f"{grade[0]}x{grade[1]:>5} {com:>17} {total:>8} {grandes:>15} "
              f"{time.time() - t0:>6.1f}")
    return 0


# ── Modo --fila ───────────────────────────────────────────────────────────────

def carregar(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.open() if l.strip()]


def posicoes_na_galeria(registros: list[dict]) -> dict[str, int]:
    """frame_id → posição do card na galeria do Estúdio, contando de 1 por câmera.

    A galeria ordena por `created_at DESC, id DESC` (FrameRepository.
    list_frames_paginated, `ordem_sql`) e o Estúdio de anotação anda por essa
    MESMA lista, mostrando "N de M" no cabeçalho (AnnotationStudio.tsx:968). Com
    o filtro Origem=Câmera/NVR + Status=Não anotadas + a câmera, os 440 quadros
    desta colheita são os MAIS NOVOS do tenant — logo ocupam o PREFIXO da lista,
    e esta posição é literalmente o número que ele vê na tela.

    Conferido no banco: nas últimas 12 h existem exatamente 440 linhas, todas
    `source='nvr'`, todas `curation_status='active'`, todas `width>=1280` — nada
    se intercala no prefixo.
    """
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_camera[r.get("camera_id") or "?"].append(r)
    saida: dict[str, int] = {}
    for lista in por_camera.values():
        lista.sort(key=lambda r: (r.get("created_at") or "", r["frame_id"]), reverse=True)
        for i, r in enumerate(lista, 1):
            saida[r["frame_id"]] = i
    return saida


def fila(args) -> int:
    perfil = PERFIS[args.perfil]
    registros = carregar(args.jsonl)
    if args.cameras:
        registros = [r for r in registros if r.get("camera_name") in args.cameras]
    for r in registros:
        r["_p"] = pontuar(r, perfil)

    prioritarias = {
        normalizar_nome(p) for p in args.prioritarias.split(";") if p.strip()
    }
    if prioritarias:
        # Prioridade que não casa com câmera nenhuma é erro de digitação, e
        # falharia em silêncio devolvendo a fila na ordem antiga.
        nomes = {normalizar_nome(r.get("camera_name")) for r in registros}
        orfas = [p for p in prioritarias if not any(p in n for n in nomes)]
        if orfas:
            print(f"[fila] AVISO: prioridade sem câmera correspondente: {orfas}",
                  file=sys.stderr)
    escolhidos = montar_fila(registros, args.alvo, args.cota, prioritarias or None)
    galeria = posicoes_na_galeria(registros)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "frame_id", "posicao", "score", "camera_id", "camera_name",
                "posicao_na_galeria", "captured_at", "r2_key", "visibilidade",
                "densidade", "contexto", "legibilidade", "n_pessoas", "n_anotaveis",
                "altura_max_px", "rajada", "dup_rajada", "acima_da_cota",
                "fora_da_prioridade", "criterio",
            ]
        )
        for it in escolhidos:
            p = it["_p"]
            w.writerow([
                it["frame_id"], it["posicao"], f"{p['score']:.4f}", it["camera_id"],
                it["camera_name"], galeria[it["frame_id"]], it["captured_at"],
                it["r2_key"],
                f"{p['visibilidade']:.4f}", f"{p['densidade']:.4f}",
                f"{p['contexto']:.4f}", f"{p['legibilidade']:.4f}",
                p["n_pessoas"], p["n_anotaveis"],
                p["altura_max"], it["rajada"],
                "sim" if it["dup_rajada"] else "nao",
                "sim" if it["acima_da_cota"] else "nao",
                "sim" if it.get("fora_da_prioridade") else "nao",
                f"{perfil.nome}:vis{perfil.peso_visibilidade}"
                f"+den{perfil.peso_densidade}+ctx{perfil.peso_contexto}"
                f"@{perfil.altura_minima}px",
            ])
    print(f"gravado: {args.csv}  ({len(escolhidos)} quadros)")

    if args.roteiro:
        if args.via == "gabarito":
            _roteiro_gabarito(escolhidos, args.roteiro, perfil, args.ja_julgados)
        else:
            _roteiro(escolhidos, galeria, args.roteiro)
        print(f"gravado: {args.roteiro}")

    _medir(registros, escolhidos, perfil)
    return 0


_URL_ESTUDIO = "/novo/estudio/dados?camera={cid}&status=nao_anotado"

#: `PAGE_SIZE` da galeria (TrainingGallery.tsx). Clicar no card abre o Estúdio já
#: naquele índice — é o que evita 160 setas para chegar ao card 161.
TAMANHO_PAGINA = 60


def _roteiro(escolhidos: list[dict], galeria: dict[str, int], saida: Path) -> None:
    """A folha da sentada: por câmera, quais posições da galeria abrir.

    O Estúdio NÃO aceita ordem arbitrária nem lista de ids (conferido: a galeria
    monta o filtro em TrainingGallery.tsx:244-255 — page, page_size,
    curation_status, is_annotated, pending_review, camera_ids, source — e o
    Estúdio anda pelo array que ela entregou). Então o atalho não é uma feature
    nova: é o filtro que já existe + o número que o cabeçalho já mostra.
    """
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for it in escolhidos:
        por_camera[it["camera_name"]].append(it)
    ordem = sorted(
        por_camera,
        key=lambda nome: -sum(
            1 for it in por_camera[nome] if not it["dup_rajada"]
        ),
    )
    linhas = [
        "# Roteiro da sentada — gabarito v2",
        "",
        "Gerado por `scripts/ops/fila_gabarito_v2.py --fila`. Não editar à mão.",
        "",
        "**Como usar.** Abra o link da câmera. Deixe **Status = Não anotadas** (o link",
        f"já manda). A galeria mostra **{TAMANHO_PAGINA} cards por página**, do mais",
        "novo para o mais velho — e os quadros desta colheita são os mais novos do",
        "acervo, então ocupam o começo da lista. Vá até a página indicada e **clique no",
        "card**: o Estúdio abre exatamente nele, e o contador do cabeçalho (`N de"
        f" {TAMANHO_PAGINA}`) confirma que é o card certo. `→` anda para o próximo.",
        "",
        "As câmeras estão na ordem em que rendem mais por minuto. Dentro de cada",
        "câmera, anote os cards da lista **instantes**; os de **repetições** são o",
        "mesmo momento meio segundo depois — só valem se sobrar tempo.",
        "",
        "⚠️ Anote uma câmera de uma vez só. Ao sair e voltar, o quadro já anotado sai",
        "do filtro *Não anotadas* e a numeração dos cards anda para trás.",
        "",
    ]
    for nome in ordem:
        itens = sorted(por_camera[nome], key=lambda it: galeria[it["frame_id"]])
        cid = itens[0]["camera_id"]
        momentos = [it for it in itens if not it["dup_rajada"]]
        linhas += [
            f"## {nome}",
            "",
            f"`{_URL_ESTUDIO.format(cid=cid)}`",
            "",
            f"{len(momentos)} instantes distintos + "
            f"{len(itens) - len(momentos)} repetições de rajada.",
            "",
        ]
        for rotulo, grupo in (("instantes", momentos),
                              ("repetições (opcional)", [i for i in itens if i["dup_rajada"]])):
            if not grupo:
                continue
            paginas: dict[int, list[int]] = defaultdict(list)
            for it in grupo:
                pos = galeria[it["frame_id"]]
                paginas[(pos - 1) // TAMANHO_PAGINA + 1].append(
                    (pos - 1) % TAMANHO_PAGINA + 1
                )
            linhas.append(f"**{rotulo}** — ")
            linhas.append(
                "; ".join(
                    f"pág {pg}: cards " + ", ".join(str(c) for c in sorted(cards))
                    for pg, cards in sorted(paginas.items())
                )
            )
            linhas.append("")
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas))


def expectativa(escolhidos: list[dict]) -> dict:
    """Quantos quadros da fila devem trazer CADA uma das três — antes da sentada.

    Modelo, declarado: para um quadro com `k` pessoas julgáveis numa câmera de
    rendimento `y` para aquela classe, P(pelo menos uma pessoa sem o EPI) =
    1 - (1-y)^k. `y` é CONTADO (RENDIMENTO_POR_CLASSE), `k` é MEDIDO (detector de
    pessoa), e a independência entre as pessoas do mesmo quadro é a única
    suposição — ela infla o número quando a equipe inteira usa (ou não usa) o
    mesmo EPI, que é justamente o que acontece numa fábrica. Daí a faixa.

    `bruto` = quantos quadros CONTÊM a ausência.
    `decidivel` = quantos o dono deve conseguir JULGAR. O desconto vem da
    LEGIBILIDADE MEDIDA DAQUELA CÂMERA (LEGIBILIDADE_CAMERA) quando existe, e só
    cai na faixa de altura (DECIDE_POR_ALTURA) para câmera nunca julgada. A
    ordem é essa porque a medida por câmera captura o ENQUADRAMENTO, que a
    altura sozinha não vê: `Corredor Lateral` e `Espaço de convivência` têm
    pessoa da mesma altura (351 e 358 px) e legibilidade de 0,962 contra 0,146.

    O que rende `sim` no gabarito é `decidivel`, e ele segue OTIMISTA: foi medido
    em `Sem Luvas`/`Sem mascara` — a mão e o rosto inteiro, que se veem de mais
    ângulos do que a orelha.
    """
    bruto = [0.0, 0.0, 0.0]
    decidivel = [0.0, 0.0, 0.0]
    qualquer = 0.0
    for it in escolhidos:
        k = it["_p"]["n_anotaveis"]
        if k == 0:
            continue
        nome = normalizar_nome(it.get("camera_name"))
        y = RENDIMENTO_POR_CLASSE.get(nome, RENDIMENTO_POR_CLASSE_PADRAO)
        altura = it["_p"]["altura_max"]
        decide = LEGIBILIDADE_CAMERA.get(
            nome,
            next((taxa for piso, taxa in DECIDE_POR_ALTURA if altura >= piso), 0.0),
        )
        for i in range(3):
            p = 1.0 - (1.0 - y[i]) ** k
            bruto[i] += p
            decidivel[i] += p * decide
        yq = RENDIMENTO_CABECA.get(nome, RENDIMENTO_CABECA_PADRAO)
        qualquer += 1.0 - (1.0 - yq) ** k
    return {"bruto": bruto, "decidivel": decidivel, "qualquer": qualquer}


def _roteiro_gabarito(
    escolhidos: list[dict], saida: Path, perfil: Perfil, ja_julgados: int
) -> None:
    """A folha da sentada quando a entrega é a tela `/novo/estudio/gabarito`.

    Diferente de `_roteiro`: ali o dono navegava a GALERIA, e por isso a folha
    tinha de traduzir cada quadro em "página tal, card tal". Aqui a tela serve a
    própria fila (`GabaritoRepository.list_fila`, ORDER BY priority_rank ASC
    NULLS LAST) — a ordem JÁ É a deste arquivo, gravada em `priority_rank` por
    `marcar_gabarito.py --ordem`. Repetir número de card seria inventar uma
    navegação que a tela não tem.
    """
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for it in escolhidos:
        por_camera[it["camera_name"]].append(it)
    momentos = sum(1 for it in escolhidos if not it["dup_rajada"])
    total = len(escolhidos) + ja_julgados

    linhas = [
        "# Roteiro da sentada — gabarito v3 (as três classes de cabeça)",
        "",
        "Gerado por `scripts/ops/fila_gabarito_v2.py --fila --perfil cabeca`.",
        "Não editar à mão.",
        "",
        "## Por que esta fila existe",
        "",
        "As três classes abaixo continuam **não conclusivas** — o gabarito tem",
        "ZERO `sim` nelas. Isso mediu a AMOSTRA, não a fábrica:",
        "",
        "- elas foram perguntadas em **51 dos 246** quadros da sentada anterior",
        "  (20,7%), porque moram atrás do acordeão *Mais 3 classes*;",
        "- e esses 51 são justamente os de pessoa **menor** — mediana 322 px,",
        "  contra 536 px nos quadros que renderam `sim`. Abaixo de 350 px de",
        "  pessoa, NENHUMA classe rendeu `sim` na sentada anterior (0 em 53),",
        "  nem as duas que estavam em foco.",
        "",
        "Nesta rodada as três estão **à vista** (foco) e `Sem Luvas`/`Sem mascara`",
        "foram para trás do acordeão. E a fila só traz quadro com pessoa de",
        f"**≥ {perfil.altura_minima} px**, ordenado por duas medidas e não por",
        "palpite: quanto aquela câmera RENDE destas três (contado nos 2.705",
        "recortes já anotados) **vezes** quanto dela você CONSEGUIU julgar na",
        "sentada anterior (as duas colunas da tabela abaixo).",
        "",
        "## Como usar",
        "",
        "Abra **`/novo/estudio/gabarito`**. Não há link por câmera nem número de",
        f"card: os **{len(escolhidos)} quadros** desta fila ocupam as primeiras",
        f"posições (`priority_rank` 1..{len(escolhidos)}) e os {ja_julgados} já",
        "julgados foram empurrados para trás.",
        "",
        f"⚠️ O cabeçalho deve dizer **`1 de {total}`**. Se abrir num número",
        "diferente, o aparelho guardou a posição da sentada anterior — toque `←`",
        "até chegar em 1, ou abra numa aba anônima.",
        "",
        "Três perguntas por quadro, e o atalho **não há pessoa** responde as",
        "cinco de uma vez. Não desenhe caixa: o gabarito é resposta por imagem.",
        "",
        "## Composição da fila",
        "",
        "| câmera | momentos | repetições | tem uma das 3 | ele consegue julgar |",
        "|---|---:|---:|---:|---:|",
    ]
    ordem = sorted(
        por_camera,
        key=lambda n: -sum(1 for it in por_camera[n] if not it["dup_rajada"]),
    )
    for nome in ordem:
        itens = por_camera[nome]
        m = sum(1 for it in itens if not it["dup_rajada"])
        rend = (perfil.rendimento or {}).get(
            normalizar_nome(nome), RENDIMENTO_CABECA_PADRAO
        )
        linhas.append(
            f"| {nome} | {m} | {len(itens) - m} | {100*rend:.1f}% | "
            f"{100*perfil.legivel(nome):.1f}% |"
        )
    linhas += [
        f"| **total** | **{momentos}** | **{len(escolhidos) - momentos}** | | |",
        "",
        f"São **{momentos} momentos distintos** (rajada de 0,5 s conta como um)",
        f"mais {len(escolhidos) - momentos} repetições de rajada, que ficam no fim",
        "e podem ser puladas sem perder nada.",
        "",
        "## Quanto isto deve render — e o que pode dar errado",
        "",
        f"{sum(it['_p']['n_anotaveis'] for it in escolhidos)} pessoas julgáveis em",
        f"{len(escolhidos)} quadros (média "
        f"{sum(it['_p']['n_anotaveis'] for it in escolhidos)/len(escolhidos):.2f}"
        " por quadro). Do rendimento contado por câmera:",
        "",
        "| classe | quadros que devem CONTER | que ele deve conseguir JULGAR |",
        "|---|---:|---:|",
    ]
    exp = expectativa(escolhidos)
    for i, nome in enumerate(NOMES_CABECA):
        linhas.append(
            f"| {nome} | {exp['bruto'][i]:.0f} | **{exp['decidivel'][i]:.0f}** |"
        )
    linhas += [
        f"| *≥1 das três* | *{exp['qualquer']:.0f}* | |",
        "",
        "A coluna da direita é a que vira `sim`, e segue **otimista**: o desconto",
        "de legibilidade foi medido nas suas respostas de `Sem Luvas`/`Sem mascara`",
        "— a mão e o rosto inteiro, que se veem de mais ângulos do que a orelha.",
        "Se na hora o `não sei` vier bem mais do que isto, o problema deixa de ser",
        "fila e passa a ser **enquadramento de câmera** — e aí a saída é",
        "lente/posição, não anotação.",
        "",
        "O piso do que desbloqueia é **1 `sim` por classe**: já tira as três do",
        "não-conclusivo. A mais magra da fila é "
        f"*{NOMES_CABECA[min(range(3), key=lambda i: exp['decidivel'][i])]}*, com "
        f"**{min(exp['decidivel']):.0f}** — ainda uma ordem de grandeza acima do",
        "piso, mas é ela que se perde primeiro se a legibilidade real for pior",
        "do que a medida.",
        "",
    ]
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas))


def _medir(
    registros: list[dict], escolhidos: list[dict], perfil: Perfil = PERFIL_MAOS
) -> None:
    """Os números do item 5 do pedido. Tudo contado, nada estimado."""
    total = len(registros)
    com_pessoa = sum(1 for r in registros if r["_p"]["n_pessoas"] > 0)
    anotaveis = sum(1 for r in registros if r["_p"]["n_anotaveis"] > 0)
    print()
    print(f"perfil                     : {perfil.nome} "
          f"(gate {perfil.altura_minima}px)")
    print(f"quadros medidos            : {total}")
    print(f"com QUALQUER pessoa        : {com_pessoa} ({100*com_pessoa/total:.1f}%)")
    print(f"com pessoa ≥{perfil.altura_minima}px (gate) : "
          f"{anotaveis} ({100*anotaveis/total:.1f}%)")
    print(f"rajadas distintas (aptos)  : {len(set(rajadas([r for r in registros if r['_p']['n_anotaveis']>0]).values()))}")
    print()
    print("distribuição do score (todos os aptos):")
    scores = sorted(r["_p"]["score"] for r in registros if r["_p"]["n_anotaveis"] > 0)
    if scores:
        for rot, idx in (("min", 0), ("p25", len(scores)//4), ("mediana", len(scores)//2),
                         ("p75", 3*len(scores)//4), ("max", len(scores)-1)):
            print(f"  {rot:>8}: {scores[idx]:.4f}")
    print()
    print("quadros por câmera na fila:")
    por_cam = Counter(it["camera_name"] for it in escolhidos)
    for nome, n in por_cam.most_common():
        print(f"  {n:>4}  {nome}")
    dups = sum(1 for it in escolhidos if it["dup_rajada"])
    print()
    print(f"na fila: {len(escolhidos)}  |  momentos distintos: {len(escolhidos)-dups}"
          f"  |  segundo-quadro-de-rajada: {dups}")

    if perfil.rendimento is not None:
        exp = expectativa(escolhidos)
        print()
        print("expectativa (contém → deve conseguir julgar):")
        for i, nome in enumerate(NOMES_CABECA):
            print(f"  {nome:<26} {exp['bruto'][i]:>6.1f} → {exp['decidivel'][i]:>6.1f}")
        print(f"  {'≥1 das três':<26} {exp['qualquer']:>6.1f}")


# ── Autoteste ─────────────────────────────────────────────────────────────────

def autoteste(_args) -> int:
    def caixa(h, y=100, x=10, w=50, conf=0.9):
        return {"x": x, "y": y, "w": w, "h": h, "conf": conf}

    # Fusão de grades: fragmento engolido pela pessoa inteira some; pessoa ao lado fica.
    inteira = {"x": 100, "y": 100, "w": 100, "h": 400}
    fragmento = {"x": 110, "y": 300, "w": 80, "h": 180}   # dentro da inteira
    vizinha = {"x": 400, "y": 100, "w": 100, "h": 400}    # sem sobreposição
    encostada = {"x": 180, "y": 100, "w": 100, "h": 400}  # 20% sobreposta
    assert fundir([inteira, fragmento]) == [inteira]
    assert fundir([fragmento, inteira]) == [inteira], "ordem de entrada não importa"
    assert len(fundir([inteira, vizinha])) == 2
    assert len(fundir([inteira, encostada])) == 2, "encostar não é ser a mesma pessoa"
    assert fundir([]) == []

    # Gate: pessoa pequena não é anotável.
    assert not pessoa_anotavel(caixa(ALTURA_MINIMA - 1))
    assert pessoa_anotavel(caixa(ALTURA_MINIMA))

    # Visibilidade satura e cabeça cortada paga metade.
    assert visibilidade([caixa(ALTURA_PLENA * 2)]) == 1.0
    assert visibilidade([caixa(int(ALTURA_PLENA), y=0)]) == 0.5
    assert visibilidade([caixa(ALTURA_MINIMA - 1)]) == 0.0, "pequena não pontua"
    assert visibilidade([caixa(300), caixa(500)]) == 1.0, "vale a MELHOR pessoa"

    # Densidade cresce e satura.
    assert densidade([]) == 0.0
    d1, d2 = densidade([caixa(300)]), densidade([caixa(300), caixa(300)])
    assert 0 < d1 < d2 < 1.0
    assert densidade([caixa(300), caixa(10)]) == d1, "pequena não conta densidade"

    # Contexto: prior declarado, refeitório > entrada > resto; fora da janela paga menos.
    # captured_at é relógio de parede da fábrica (ver FUSO_FABRICA).
    dentro = datetime.fromisoformat("2026-09-01T12:00:00+00:00")  # almoço
    fora = datetime.fromisoformat("2026-09-01T17:00:00+00:00")    # saída de turno
    madrugada = datetime.fromisoformat("2026-09-01T03:00:00+00:00")
    assert contexto("Espaço de convivência", dentro) > contexto("Entrada Expedição", dentro)
    assert contexto("Entrada Expedição", dentro) > contexto("Corredor", dentro)
    assert contexto("Espaço de convivência", madrugada) < contexto("Espaço de convivência", dentro)
    assert contexto("Espaço de convivência", fora) == contexto("Espaço de convivência", dentro)

    # Rajada: mesma câmera, 0,5 s de intervalo = um momento; 10 s = dois.
    def reg(fid, cam, seg, h=300):
        return {
            "frame_id": fid, "camera_id": cam, "camera_name": cam,
            "captured_at": (datetime.fromisoformat("2026-09-01T10:00:00+00:00")
                            + timedelta(seconds=seg)).isoformat(),
            "pessoas": [caixa(h)],
        }

    juntos = [reg("a", "c1", 0), reg("b", "c1", 0.5), reg("c", "c1", 1.0)]
    g = rajadas(juntos)
    assert len({g["a"], g["b"], g["c"]}) == 1, g
    separados = [reg("a", "c1", 0), reg("b", "c1", 30)]
    g = rajadas(separados)
    assert g["a"] != g["b"]
    # Câmeras diferentes no MESMO instante nunca são a mesma rajada.
    g = rajadas([reg("a", "c1", 0), reg("b", "c2", 0)])
    assert g["a"] != g["b"]

    # Fila: passe 1 é um por rajada; duplicata só depois, e marcada.
    regs = [reg("a", "c1", 0, 400), reg("b", "c1", 0.5, 300), reg("c", "c2", 0, 250)]
    for r in regs:
        r["_p"] = pontuar(r)
    f = montar_fila(regs, alvo=3, cota=1.0)
    assert [x["frame_id"] for x in f[:2]] == ["a", "c"], [x["frame_id"] for x in f]
    assert f[0]["dup_rajada"] is False and f[2]["dup_rajada"] is True
    assert f[2]["frame_id"] == "b"

    # Quadro sem pessoa anotável NUNCA entra na fila (gate (a)).
    vazio = reg("z", "c3", 0, h=10)
    vazio["_p"] = pontuar(vazio)
    f = montar_fila([vazio], alvo=10, cota=1.0)
    assert f == [], f

    # Cota: câmera dominante não sequestra a fila; excedente vai pro fim, não some.
    muitos = []
    for i in range(10):
        r = reg(f"m{i}", "c1", i * 60, 400)
        r["_p"] = pontuar(r)
        muitos.append(r)
    outro = reg("outro", "c2", 0, 210)
    outro["_p"] = pontuar(outro)
    f = montar_fila(muitos + [outro], alvo=11, cota=0.3)
    assert sum(1 for x in f[:3] if x["camera_id"] == "c1") == 3
    assert any(x["frame_id"] == "outro" and not x["acima_da_cota"] for x in f)

    # Prioridade do dono vence o SCORE — o caso real de 02/09: a câmera com a
    # pessoa maior era "Espaço de convivência", e o dono quer as entradas de
    # produção. A não-prioritária não some: vai para o fim, marcada.
    def nomeada(fid, nome, h):
        r = reg(fid, fid, 0, h)
        r["camera_name"] = nome
        r["_p"] = pontuar(r)
        return r

    conviv = nomeada("conv", "Espaço de convivência", 500)   # score MAIOR
    corredor = nomeada("corr", "Corredor Lateral usinagem Madeira", 220)
    fp = montar_fila([conviv, corredor], alvo=2, cota=1.0,
                     prioritarias={"corredor lateral usinagem"})
    assert fp[0]["frame_id"] == "corr", [x["frame_id"] for x in fp]
    assert fp[0]["fora_da_prioridade"] is False
    assert fp[1]["frame_id"] == "conv" and fp[1]["fora_da_prioridade"] is True

    # Casa sem acento e sem caixa — o dono digita como fala.
    assert normalizar_nome("Espaço de Convivência") == "espaco de convivencia"
    fp = montar_fila([conviv, corredor], alvo=2, cota=1.0,
                     prioritarias={"espaco de convivencia"})
    assert fp[0]["frame_id"] == "conv"

    # Sem prioridade nenhuma, a ordem é a do score — não-regressão.
    fp = montar_fila([conviv, corredor], alvo=2, cota=1.0)
    assert fp[0]["frame_id"] == "conv"
    assert len(f) == 11, "excedente é despriorizado, nunca descartado"
    assert all(x["acima_da_cota"] for x in f[4:]), [x["frame_id"] for x in f]

    # ── Perfil `cabeca` ───────────────────────────────────────────────────────
    # O default NÃO mudou: o perfil novo não pode reescrever a fila de 02/09.
    assert pontuar(conviv)["score"] == pontuar(conviv, PERFIL_MAOS)["score"]

    # Gate de 350 px: a pessoa que servia para a MÃO não serve para a ORELHA.
    # (medido: 0 `sim` em 53 quadros com pessoa < 350 px)
    p300 = caixa(300)
    assert pessoa_anotavel(p300, PERFIL_MAOS)
    assert not pessoa_anotavel(p300, PERFIL_CABECA)
    assert pessoa_anotavel(caixa(ALTURA_MINIMA_CABECA), PERFIL_CABECA)

    # Quadro só com pessoa de 300 px some da fila no perfil cabeça — e é o
    # ponto todo: ele entraria na fila antiga e renderia zero.
    so300 = reg("p300", "c9", 0, 300)
    so300["_p"] = pontuar(so300, PERFIL_CABECA)
    assert montar_fila([so300], alvo=10, cota=1.0) == []

    # Contexto do perfil cabeça é a tabela MEDIDA, casada por nome EXATO.
    assert contexto("Entrada Expedição", None, PERFIL_CABECA) == 0.653
    # "entrada expedicao" é PREFIXO de "entrada expedicao 02": casamento por
    # substring faria a 02 herdar 0,653 sem ter sido medida. Não pode.
    assert contexto("Entrada Expedição 02", None, PERFIL_CABECA) == RENDIMENTO_CABECA_PADRAO
    assert contexto("Câmera Que Não Existe", None, PERFIL_CABECA) == RENDIMENTO_CABECA_PADRAO
    # Sem fator de hora: a medida por hora não sustenta as janelas (ver constante).
    meia_noite = datetime.fromisoformat("2026-09-01T03:00:00+00:00")
    assert contexto("Qualidade 06", meia_noite, PERFIL_CABECA) == contexto(
        "Qualidade 06", dentro, PERFIL_CABECA
    )
    # E o rendimento medido ORDENA: WC (1,1%) perde de Preparação (61,7%) mesmo
    # com a MESMA pessoa no quadro — que é o erro que a fila de 02/09 cometeu.
    wc = nomeada("wc", "Entrada WC Usinagem Papelão", 600)
    prep = nomeada("prep", "Entrada Preparação", 600)
    for r in (wc, prep):
        r["_p"] = pontuar(r, PERFIL_CABECA)
    fc = montar_fila([wc, prep], alvo=2, cota=1.0)
    assert [x["frame_id"] for x in fc] == ["prep", "wc"], [x["frame_id"] for x in fc]

    # LEGIBILIDADE multiplica — e é o que impede a convivência de sequestrar a
    # fila: prevalência 86,2% (a MAIOR) mas legibilidade 0,146 (0 `sim` em 41
    # quadros reais). Com a mesma pessoa no quadro, ela perde de Preparação.
    conv2 = nomeada("conv2", "Espaço de convivência", 600)
    prep2 = nomeada("prep2", "Entrada Preparação", 600)
    for r in (conv2, prep2):
        r["_p"] = pontuar(r, PERFIL_CABECA)
    assert conv2["_p"]["contexto"] > prep2["_p"]["contexto"], "prevalência: conv ganha"
    assert conv2["_p"]["score"] < prep2["_p"]["score"], "legibilidade: conv perde"
    fl = montar_fila([conv2, prep2], alvo=2, cota=1.0)
    assert [x["frame_id"] for x in fl] == ["prep2", "conv2"], [x["frame_id"] for x in fl]
    # No perfil `maos` a legibilidade não existe e o score é o de sempre.
    assert pontuar(conv2, PERFIL_MAOS)["legibilidade"] == 1.0

    # Expectativa: aritmética declarada, e o número tem de cair onde se espera.
    um = nomeada("um", "Entrada Preparação", 600)  # ouvido 45,8%; legível 0,615
    um["_p"] = pontuar(um, PERFIL_CABECA)
    e = expectativa([um])
    assert abs(e["bruto"][0] - 0.458) < 1e-9, e["bruto"]
    assert abs(e["decidivel"][0] - 0.458 * 0.615) < 1e-9, e["decidivel"]
    # Duas pessoas no quadro: 1-(1-y)^2, não 2y.
    dois = dict(um, pessoas=[caixa(600), caixa(600, x=900)])
    dois["_p"] = pontuar(dois, PERFIL_CABECA)
    assert abs(expectativa([dois])["bruto"][0] - (1 - 0.542**2)) < 1e-9
    # Câmera NUNCA julgada cai na faixa de altura, não em zero nem em 1,0.
    novacam = nomeada("nc", "Qualidade 06", 400)  # sem medida de legibilidade
    novacam["_p"] = pontuar(novacam, PERFIL_CABECA)
    assert abs(expectativa([novacam])["decidivel"][0] - 0.252 * 0.526) < 1e-9
    # Abaixo do gate não entra na conta.
    fora = nomeada("fora", "Entrada Preparação", 100)
    fora["_p"] = pontuar(fora, PERFIL_CABECA)
    assert expectativa([fora])["bruto"] == [0.0, 0.0, 0.0]
    # Câmera sem medida própria cai na taxa global, não em zero silencioso.
    nova = nomeada("nova", "Câmera Recém-Instalada", 600)
    nova["_p"] = pontuar(nova, PERFIL_CABECA)
    assert abs(expectativa([nova])["bruto"][0] - RENDIMENTO_POR_CLASSE_PADRAO[0]) < 1e-9

    print("autoteste OK")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def _grade(bruto: str) -> tuple[int, int]:
    nx, _, ny = bruto.lower().partition("x")
    return int(nx), int(ny)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--pessoas", action="store_true")
    modo.add_argument("--calibrar", action="store_true")
    modo.add_argument("--fila", action="store_true")
    modo.add_argument("--autoteste", action="store_true")

    ap.add_argument("--tenant", default=TENANT_RVB)
    ap.add_argument("--horas", type=int, default=12)
    ap.add_argument("--largura-min", type=int, default=1280)
    ap.add_argument("--perfil", choices=sorted(PERFIS), default="maos",
                    help="que ausência a fila caça. 'maos' (default) = Sem Luvas/"
                         "Sem mascara, marcadas na pessoa inteira. 'cabeca' = Sem "
                         "Óculos/Sem protetor de ouvido/Uso incorreto de mascara, "
                         "marcadas em 9-16%% da altura da pessoa: gate 350px e "
                         "rendimento MEDIDO por câmera no lugar do prior. Ver Perfil.")
    ap.add_argument("--pool", action="store_true",
                    help="fonte = quadros cheios que ainda NÃO são gabarito "
                         "(dataset_role='pool', nunca julgados), sem janela de "
                         "tempo. Sem isto a fonte são as últimas --horas.")
    ap.add_argument("--cameras", type=lambda s: [p.strip() for p in s.split(";") if p.strip()],
                    default=None,
                    help="restringe a NOMES EXATOS de câmera, separados por ';'. "
                         "Diferente de --prioritarias (que ordena sem descartar): "
                         "isto é filtro, e serve para não gastar inferência em "
                         "câmera de rendimento medido baixo.")
    ap.add_argument("--modelo-pessoa",
                    default="/Users/vitoremanuel/Logikos-mutirao/modelos-servidos/"
                            "yolox_nano_SERVIDO.onnx")
    ap.add_argument("--grades", type=lambda s: [_grade(p) for p in s.split("+")],
                    default=[(1, 1), (3, 3)],
                    help="ladrilhamentos unidos por '+' (ver --calibrar e `fundir`). "
                         "1x1 mede quem está perto sem cortar; 3x3 acha quem está "
                         "longe. 2x2 (default do edge) foi calibrado p/ 704x480 e "
                         "aqui acusa pessoa em pátio vazio.")
    ap.add_argument("--limiar-pessoa", type=float, default=0.35,
                    help="o mesmo default do coletor do edge")
    ap.add_argument("--amostra", type=int, default=40, help="frames em --calibrar")
    ap.add_argument("--cache", type=Path,
                    default=Path("/tmp/gabarito-v2-frames"))  # noqa: S108
    ap.add_argument("--jsonl", type=Path,
                    default=Path("docs/quality/evidence/gabarito-v2/"
                                 "pessoas-yolox-nano.jsonl"))
    ap.add_argument("--csv", type=Path,
                    default=Path("docs/quality/evidence/gabarito-v2/"
                                 "fila-gabarito-150.csv"))
    ap.add_argument("--roteiro", type=Path,
                    default=Path("docs/quality/evidence/gabarito-v2/"
                                 "ROTEIRO-DA-SENTADA.md"))
    ap.add_argument("--via", choices=("galeria", "gabarito"), default="galeria",
                    help="por onde o dono vai anotar. 'galeria' (default) = a "
                         "folha traduz cada quadro em página/card do Estúdio. "
                         "'gabarito' = a tela /novo/estudio/gabarito serve a "
                         "própria fila por priority_rank, e a folha não precisa "
                         "(nem pode) dar número de card.")
    ap.add_argument("--ja-julgados", type=int, default=0,
                    help="quantos quadros já julgados continuam na fila da tela, "
                         "atrás desta. Só entra no texto do roteiro, para o "
                         "contador do cabeçalho bater com o que ele vê.")
    ap.add_argument("--alvo", type=int, default=150)
    ap.add_argument("--cota", type=float, default=0.30,
                    help="fração máxima de UMA câmera na fila")
    ap.add_argument("--prioritarias", default="",
                    help="câmeras que vêm primeiro, separadas por ';'. Casa por "
                         "substring, sem acento e sem caixa. Conhecimento do dono "
                         "sobre onde o EPI é exigido — vence o score, que só sabe "
                         "o que a imagem mostra. As demais NÃO são descartadas: "
                         "vão para o fim, marcadas fora_da_prioridade.")
    args = ap.parse_args()

    if args.autoteste:
        return autoteste(args)
    if args.calibrar:
        return calibrar(args)
    if args.pessoas:
        return pessoas(args)
    return fila(args)


if __name__ == "__main__":
    raise SystemExit(main())
