---
title: "Qualidade multi-atributo por ROI + cronômetro por etapa (esqueleto)"
risk: default
adr: 0053
---

# Task 109 — Qualidade multi-atributo (ADR-0053)

## Objetivo
- Inspeção por **ROI dos pontos de atenção** da peça (lista = input do cliente, **configurável**,
  não hard-coded) sobre as câmeras de Qualidade principal (2×4MP, alta-res por ROI).
- **Rastreio + cronômetro por etapa** nas câmeras auxiliares (2×2MP, YOLOX leve + NvDCF):
  tempo entre entrada e saída da peça na zona da etapa.

## Regras
- Pontos de atenção plugáveis (config por câmera/cenário); ausência do input do cliente NÃO trava.
- Resultado por atributo (OK/falha) alimenta o outbound da task-108.

## Critérios de aceitação
- [ ] Config de ROIs por câmera (persistida) + avaliação por atributo com resultado estruturado.
- [ ] Cronômetro por etapa derivado do tracker (ID persistente NvDCF).
- [ ] Simulável no stress (task-111) sem contrato real.
