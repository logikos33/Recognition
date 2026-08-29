# Decisões de design — rodada v2 · 29/08/2026

Respostas do Vitor à lista v2. Valem como decisão registrada; nada aqui é proposta.

1. **Ordem de desenho** (10 itens → 3 primeiras): `/modules` (porta de entrada de quem tem 2+ módulos) · `/epi/cameras/:id/operations` (motor em produção) · `/epi/cameras/:id/scenario` (editor de zonas — a matriz de classes por zona aterrissa aqui; estratégico). As 4 telas de saúde: **família única com variações**, não 4 desenhos.
2. **Parede do kiosk: POR SITE** (posto de trabalho é ativo compartilhado). Pedido-ao-backend novo (pequeno): endpoint de configuração de parede por site.
3. **White-label escuro**: cliente troca **só a cor de marca**; superfícies (`--lk-preto`/`--lk-grafite`) intocáveis — o shell escuro é a identidade do produto. Piso: contraste ≥4,5:1 contra as superfícies; cor reprovada sofre **clamp de luminância automático** com aviso no admin. Cadastro ganha campo **logo-para-fundo-escuro**; sem ele, fallback = monograma neutro.
4. **Chat flutuante: sai do shell novo** (fura a lei do ciano ≤10%). Suporte, se ficar, vira item do menu de ajuda/⌘K — desenhar só se ficar.
5. **Relatórios: os 4 são requisito**, faseados — digest por e-mail + ações vencidas = **setembro** (Fase 1 do Roadmap de Valor); taxa de conformidade sobre **detecções totais** = requisito (heurística atual morre; backend na fila); seleção de conteúdo do export = fase seguinte. Os 4 registrados como pedidos-ao-backend com fase.
6. **trainer**: navegação por permissão **como está** — decisão consciente; trainer é a persona do Estúdio e o home dele chega na F5. Mudança de permissão (ex. `events:read`) é rodada de papéis, não de tela.

**Adições à lista antes de encaminhar**: Catálogo de Modelos (R4, spec em `docs/product/REQUISITOS-PRODUTO-2026-08-20.md`) entra como item de desenho **pré-F5** · 4 telas de saúde marcadas como família única.

## Pedidos-ao-backend novos desta rodada
- Config de parede do kiosk **por site** (endpoint novo, pequeno)
- Taxa de conformidade sobre detecções totais (substitui a heurística) — requisito
- Envio real do digest por e-mail (Fase 1 · setembro)
- Seleção de conteúdo do export (fase seguinte)
