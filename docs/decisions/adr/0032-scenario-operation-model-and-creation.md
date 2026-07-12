# ADR-0032 — Cenário/Operação: modelo de dados e fluxo de criação

**Status:** Aceita (aprovada 2026-07-07) · **Data:** 2026-07-07
**Estende:** ADR-0024 (reuso do canvas para config de modelo) · **Relaciona:** ADR-0031 (Training Studio),
`screens/epi-scenario-editor.md`, `screens/epi-operations.md`

## Contexto

A ADR-0024 decidiu **reutilizar o canvas de desenho** (`DrawingCanvas`/`ScenarioEditor`/`RoiDrawer`) em
dois fluxos (cenário e config de modelo), mas **não especifica o CENÁRIO/OPERAÇÃO como entidade** — o
"classe de cenário". Sem esse contrato claro, o design fica adivinhando o que criar. O editor visual já
foi construído (design Onda 3 P2), mas falta: (a) a especificação da **entidade** e do **ciclo de
criação completo**; (b) a **gestão** (listar/editar/ativar/excluir cenários); (c) a **conexão com o
Training Studio** (associar um modelo treinado a uma câmera via cenário — ADR-0024). Precisa entrar na
próxima rodada do design.

## Decisão

Especificar o **Cenário/Operação** como entidade de domínio e o fluxo de criação, para o design
implementar por completo.

### A "classe de cenário" (modelo de dados)

Uma **Operação** (cenário) é uma **regra de monitoramento presa a uma câmera** que diz O QUÊ detectar
(classes), ONDE (geometria), COMO (tipo) e com QUE sensibilidade (threshold). Campos:

```
Operação (cenário)
├── id
├── camera_id           # a qual câmera pertence
├── module_id           # qual módulo (data-driven; nome humano na UI, não "epi" cru)
├── type_id             # tipo de operação (ver abaixo)
├── name                # nome humano (ex.: "Zona Estoque Químico")
├── config
│   ├── geometry        # UMA das três, conforme o tipo (coordenadas NORMALIZADAS 0..1):
│   │   ├── roi_points  #   zona/polígono (≥3 pontos)
│   │   ├── line_points #   linha de cruzamento (exatamente 2 pontos)
│   │   └── point       #   ponto de interesse (1 ponto)
│   ├── target_classes  # quais CLASSES do modelo do cliente monitorar (data-driven)
│   └── threshold       # limiar de alerta/confiança
├── status              # active | inactive | error (dot verde/vermelho na lista)
└── created_at / created_by
```

### Tipos de operação (data-driven, vêm de `/api/scenarios/operation-types?module=`)

| Tipo | Ferramenta (geometria) | O que faz |
|---|---|---|
| Contagem estática | Zona | Conta objetos de uma classe dentro da área |
| Posição | Zona | Detecta se objetos de uma classe estão dentro da área |
| Sobreposição dinâmica | Zona | Detecta interação entre dois tipos de objeto em movimento |
| Sobreposição área fixa | Zona | Mede tempo/cobertura/eventos de entrada-saída em área fixa |
| Linha de contagem | Linha (2 pts) | Conta objetos que cruzam uma linha virtual |
| Ponto de interesse | Ponto (1 pt) | Monitora presença de classe em um ponto fixo |

A **ferramenta de desenho é inferida do tipo** (via `config_schema`: `roi_points`→Zona, `line_points`→
Linha, `point`→Ponto). Não deixar o usuário escolher ferramenta incompatível com o tipo.

### Fluxo de criação (o editor + a gestão)

1. **Módulo** → carrega os tipos e as operações existentes daquele módulo.
2. **Tipo de operação** → infere a ferramenta e revela Nome/Classes/Threshold/Salvar.
3. **Desenhar a geometria** no canvas sobre o vídeo da câmera (coords normalizadas; undo/redo/limpar;
   zona fecha clicando no 1º ponto; linha = 2 cliques; ponto = 1 clique).
4. **Nome** da operação.
5. **Classes a monitorar** (das classes do modelo do cliente).
6. **Threshold** de alerta.
7. **Salvar** → cria a operação (POST `/cameras/{id}/operations`), renderiza a ROI sobre o vídeo, e
   entra na lista "Operações (N)". Habilitar Salvar só com tipo + nome + geometria válida.
8. **Gestão** (a completar): listar cenários por câmera, **editar** (pré-carregar geometria — ADR-0024
   `initialGeometry`), **ativar/desativar**, **excluir**. Estado de cada um (ativo/erro).

### Conexão com o Training Studio (ADR-0031) e config de modelo (ADR-0024)

- O estágio **Promover/Implantar** do Training Studio associa um **modelo treinado** a câmeras. Ao
  configurar o modelo numa câmera, reusa-se este mesmo canvas (ADR-0024): definir **ROI de inferência**,
  **linha de cruzamento**, **classes ativas** e **threshold por classe**.
- Ou seja: **cenário/operação** (regra de negócio) e **config de modelo** (onde/como o modelo roda na
  câmera) compartilham a ferramenta de desenho e o conceito de geometria+classes+threshold. Manter
  consistência de UX entre os dois.

## Consequências

- O design passa a ter o **contrato claro** do cenário — implementa a criação + gestão sem adivinhar.
- Data-driven inegociável: tipos, classes e módulos vêm da configuração/treino do cliente; nomes humanos
  na UI (nada de `module_code`/chave técnica).
- Débito herdado (ADR-0024): dois `RoiDrawer` coexistem — unificar em sprint de limpeza.

## Referências

- ADR-0024 (reuso do canvas), ADR-0031 (Training Studio), `screens/epi-scenario-editor.md`,
  `screens/epi-operations.md`.
