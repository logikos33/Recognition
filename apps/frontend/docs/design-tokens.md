# Recognition — Design Tokens

Paleta escolhida: **Proposta B (Shop Floor)**
Industrial vívido · Preto profundo + Ciano elétrico + Laranja-Segurança

---

## Cores

### Backgrounds
| Token | Valor | Uso |
|-------|-------|-----|
| `bgBase` | `#0a0c10` | Fundo da aplicação |
| `bgSurface` | `#111318` | Sidebar, topbar, painéis |
| `bgCard` | `#161a20` | Cards e células de tabela |
| `bgHover` | `#1a1f27` | Estado hover de linhas e itens |
| `bgElevated` | `#1e2330` | Modais, dropdowns elevados |

### Texto
| Token | Valor | Contraste WCAG |
|-------|-------|----------------|
| `textPrimary` | `#f0f4f8` | AA sobre bgBase |
| `textSecondary` | `#8ba3bc` | AA sobre bgCard |
| `textMuted` | `#435060` | Uso em labels secundários |
| `textDim` | `#2a3a4a` | Uso em separadores/hints |

### Primário (Ciano Industrial)
| Token | Valor | Uso |
|-------|-------|-----|
| `primary` | `#06b6d4` | Botões, links, itens ativos |
| `primaryLight` | `#22d3ee` | Hover em primário |
| `primaryDark` | `#0891b2` | Pressed/active em primário |
| `primaryAlpha` | `rgba(6, 182, 212, 0.1)` | Backgrounds de estado ativo, focus rings |

### Acento (Laranja-Segurança)
| Token | Valor | Uso |
|-------|-------|-----|
| `accent` | `#ea580c` | Alertas altos, indicadores críticos |
| `accentLight` | `#f97316` | Hover em acento |
| `accentDark` | `#c2410c` | Pressed/active em acento |
| `accentAlpha` | `rgba(234, 88, 12, 0.12)` | Backgrounds de alerta |

### Semânticos
| Token | Valor | Uso |
|-------|-------|-----|
| `success` | `#10b981` | Conformidade, câmera ativa, ok |
| `successMuted` | `rgba(16, 185, 129, 0.1)` | Background de badge success |
| `warning` | `#f59e0b` | Alertas médios |
| `warningMuted` | `rgba(245, 158, 11, 0.1)` | Background de badge warning |
| `danger` | `#ef4444` | Erros, alertas altos |
| `dangerMuted` | `rgba(239, 68, 68, 0.1)` | Background de badge danger |

### Bordas
| Token | Valor | Uso |
|-------|-------|-----|
| `borderSubtle` | `#161c24` | Separadores internos suaves |
| `borderDefault` | `#1e2730` | Bordas de cards e inputs |
| `borderStrong` | `#2a3545` | Bordas em hover ou foco |

---

## Tipografia

| Token | Valor |
|-------|-------|
| `font.sans` | `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` |
| `font.mono` | `'JetBrains Mono', 'Fira Code', monospace` |

**Escala tipográfica:**
- `10px` — labels de seção (UPPERCASE, tracking 0.08em)
- `11px` — badges, versão, metadados
- `12px` — texto auxiliar, datas
- `13px` — texto de navegação, descrições
- `14px` — corpo padrão
- `16px` — subtítulos de card
- `18–20px` — títulos de página
- `24–72px` — valores de KPI/Andon (JetBrains Mono)

---

## Espaçamento (escala 4px)

| Token | Valor |
|-------|-------|
| `space.xs` | `4px` |
| `space.sm` | `8px` |
| `space.md` | `16px` |
| `space.lg` | `24px` |
| `space.xl` | `32px` |
| `space.xxl` | `48px` |

---

## Border Radius

| Token | Valor | Uso |
|-------|-------|-----|
| `radius.sm` | `4px` | Badges, chips pequenos |
| `radius.md` | `6px` | Inputs, botões |
| `radius.lg` | `10px` | Cards |
| `radius.xl` | `16px` | Modais, painéis grandes |
| `radius.full` | `9999px` | Pills, avatars |

---

## Sombras

| Token | Valor |
|-------|-------|
| `shadow.sm` | `0 2px 8px rgba(0,0,0,0.5)` |
| `shadow.md` | `0 4px 16px rgba(0,0,0,0.6)` |
| `shadow.lg` | `0 8px 40px rgba(0,0,0,0.7)` |
| `shadow.glow` | `0 0 0 3px rgba(6,182,212,0.12)` (focus ring) |
| `shadow.glowCyan` | `0 0 12px rgba(6,182,212,0.3)` |
| `shadow.glowDanger` | `0 0 12px rgba(239,68,68,0.3)` |

---

## Animação

| Token | Recognition Dark | Legacy Professional |
|-------|-----------------|---------------------|
| `animation.enabled` | `'1'` | `'0'` |
| `animation.duration` | `'0.2s'` | `'0s'` |
| `animation.durationSlow` | `'0.4s'` | `'0s'` |
| `animation.easing` | `'cubic-bezier(0.4, 0, 0.2, 1)'` | `'linear'` |

---

## Tom de Marca (Do / Don't)

**Faça:**
- Usar ciano (`primary`) para ações, links e estados ativos
- Usar laranja-segurança (`accent`) exclusivamente para alertas de alta severidade
- Usar `textMuted` para labels secundários, nunca para texto de ação

**Não faça:**
- Usar hex hardcoded em componentes — sempre referenciar tokens
- Usar `accent` como cor decorativa fora de contexto de alerta
- Glow em elementos que não sejam interativos com foco
- Exclamação em mensagens corporativas
- Emojis em interface de produção
