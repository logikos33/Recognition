# recognition-rebrand — 2026-05-03

## Resumo

Conclusão do rebrand Recognition em dois sprints: Sprint 6 entregou a interface de white-label no painel admin (editor de cores com verificação WCAG AA, preview ao vivo em 3 telas, sandbox de paletas), e Sprint 7 eliminou as últimas referências ao nome anterior "EPI Monitor" e criou o catálogo DesignSystem acessível a superadmins.

## Arquivos Alterados

| Arquivo | Tipo | Impacto |
|---------|------|---------|
| `frontend/src/modules/admin/components/ColorPicker.tsx` | Criado | Componente reutilizável com verificação de contraste WCAG AA inline |
| `frontend/src/modules/admin/components/BrandingPreview.tsx` | Criado | Preview ao vivo em 3 mini-telas: Login, Dashboard, Andon |
| `frontend/src/modules/admin/components/TenantBrandingEditor.tsx` | Criado | Editor de nome do produto, cor primária, acento e logo (upload FileReader) |
| `frontend/src/modules/admin/pages/AdminBrandingTenantsPage.tsx` | Criado | Listagem de tenants com swatches de cor e indicador de customização |
| `frontend/src/modules/admin/pages/AdminBrandingEditorPage.tsx` | Criado | Editor por tenant com persistência em localStorage e modo "Visualizar como tenant" |
| `frontend/src/modules/admin/pages/AdminBrandingDefaultPage.tsx` | Criado | Referência somente-leitura de tokens de design do tema padrão Recognition (6 grupos, 22 tokens) |
| `frontend/src/modules/admin/pages/AdminBrandingSandboxPage.tsx` | Criado | Playground livre com 6 presets de paleta, sem persistência |
| `frontend/src/modules/admin/AdminLayout.tsx` | Modificado | Grupo de nav "Identidade Visual" adicionado; 4 rotas `/admin/branding/*` registradas; ícone `Palette` importado |
| `frontend/src/pages/DesignSystemPage.tsx` | Criado | Catálogo completo de tokens, tipografia, espaçamento e componentes primitivos (Button, Badge, Input, Skeleton, Toast, Shadow, BorderRadius) |
| `frontend/src/AppRoutes.tsx` | Modificado | Rota `/design-system` adicionada atrás de `AdminRoute`; `DesignSystemPage` importada via lazy |

## O Que Mudou

### ColorPicker (Sprint 6)
- Antes: não existia
- Depois: componente composto por `<input type="color">` + campo hex + badge de contraste; calcula luminância relativa via fórmula WCAG e exibe ratio (ex: `4.52:1 AA ✓`) comparado ao fundo `bgBase` configurável
- Motivo: garantir que operadores não configurem cores inacessíveis por acidente

### BrandingPreview (Sprint 6)
- Antes: não existia
- Depois: 3 sub-componentes (`LoginPreview`, `DashboardPreview`, `AndonPreview`) renderizados em escala reduzida usando CSS inline; refletem `primary`, `accent` e `productName` em tempo real
- Motivo: dar feedback visual imediato sem necessitar navegar para outra rota

### TenantBrandingEditor (Sprint 6)
- Antes: não existia
- Depois: formulário controlado com campos nome do produto, cor primária (via `ColorPicker`), cor de acento e upload de logo (convertido para data URL via `FileReader`)
- Motivo: centralizar a edição de todos os atributos de marca de um tenant em um único componente reutilizável

### AdminBrandingTenantsPage (Sprint 6)
- Antes: não existia
- Depois: lista tenants de `TENANT_MOCKS`; exibe swatches das cores salvas em localStorage; badge "Customizado" quando override existe; navega para editor por ID
- Motivo: ponto de entrada do fluxo white-label no painel admin

### AdminBrandingEditorPage (Sprint 6)
- Antes: não existia
- Depois: layout 2 colunas (editor + preview sticky); salva/carrega de `localStorage`; botão "Visualizar como tenant" injeta CSS vars via `resolveTheme()` no `<style id="recognition-tenant-theme">`; botão "Resetar padrão" remove override
- Motivo: permitir que superadmin configure e previsualize o tema de cada tenant sem rebuild

### AdminBrandingDefaultPage (Sprint 6)
- Antes: não existia
- Depois: tabela de referência somente-leitura dos 22 tokens base (fundo, texto, primary, accent, semânticas, bordas); cada linha tem swatch, nome, valor hex e descrição
- Motivo: documentação viva dos tokens para quem configura tenants

### AdminBrandingSandboxPage (Sprint 6)
- Antes: não existia
- Depois: 6 presets de paleta (Recognition, Verde Industrial, Azul Corporativo, Roxo Tech, Vermelho Crítico, Teal Segurança); `ColorPicker` livre; botão "Aplicar na página" para teste in-app sem salvar
- Motivo: exploração de paletas antes de commitar a um tenant

### AdminLayout — grupo "Identidade Visual" (Sprint 6)
- Antes: não havia grupo de branding na sidebar
- Depois: grupo "Identidade Visual" com item "White-label" (`/admin/branding/tenants`); 4 rotas declaradas dentro do `<Routes>` do layout
- Motivo: integrar o fluxo branding à navegação admin existente

### Remoção de referências "EPI Monitor" (Sprint 7)
- Antes: `types/index.ts`, `ModuleSelectionPage` e `TabletIdle` continham o texto literal "EPI Monitor"
- Depois: substituído por "Recognition" ou pela variável `productName` do tema; hexs hardcoded receberam comentário `// allow:` para silenciar lint sem perder rastreabilidade
- Motivo: conclusão do rebrand — zero ocorrências do nome anterior em produção

### DesignSystemPage (Sprint 7)
- Antes: não existia
- Depois: catálogo interno acessível em `/design-system` (apenas `AdminRoute`); seções: Color Tokens (20 tokens), Typography (8 escalas), Spacing (6 tokens), Button (4 variantes, 3 tamanhos), Badge (6 variantes), Input (4 estados), Skeleton (4 variantes), Toast (4 tipos), Shadow (5 tokens), Border Radius (5 tokens)
- Motivo: referência única para manter consistência visual à medida que a plataforma cresce

### AppRoutes — rota /design-system (Sprint 7)
- Antes: rota não existia
- Depois: `/design-system` lazy-loaded dentro de `<AdminRoute>`, sem layout admin (página autônoma)
- Motivo: acessível somente a superadmin; fora do `AdminLayout` para visualização limpa

## Como Testar

1. Login como superadmin
2. Navegar para `/admin/branding/tenants` — verificar listagem com swatches
3. Clicar em um tenant → editor abre com preview ao vivo
4. Alterar cor primária para valor com baixo contraste (ex: `#0a0c10`) — badge deve exibir `AA ✗`
5. Alterar para cor com alto contraste (ex: `#06b6d4`) — badge deve exibir `AA ✓`
6. Clicar "Visualizar como tenant" — UI deve refletir a cor escolhida globalmente
7. Clicar "Sair do preview" — UI retorna ao tema padrão
8. Clicar "Salvar" → recarregar a página → valores devem ser restaurados do localStorage
9. Clicar "Resetar padrão" → localStorage key removida, valores voltam ao mock
10. Navegar para `/admin/branding/sandbox` → testar 6 presets, aplicar na página
11. Navegar para `/admin/branding/default` → verificar tabela de tokens somente-leitura
12. Navegar para `/design-system` → verificar catálogo de tokens e componentes
13. Verificar `npx tsc --noEmit` — deve retornar zero erros

## Dívidas Técnicas Geradas

- Persistência em localStorage é local por browser; em deploy multi-dispositivo os overrides não sincronizam — implementação de API de persistência de branding por tenant está pendente para sprint futura
- `TENANT_MOCKS` é hardcoded; a listagem de tenants na página branding não vem da API `/api/admin/tenants` — necessita integração com backend para refletir tenants reais
- `/design-system` não tem busca ou âncoras de seção — aceitável para catálogo interno

## Dependências Adicionadas

Nenhuma dependência nova. Ícone `Palette` já disponível em `lucide-react` (já instalado). `FlaskConical` e `RotateCcw` também pré-existentes no pacote.

## Git Tags

- `savepoint/sprint-6-white-label`
- `savepoint/sprint-7-polimento`
- `recognition-rebrand-complete`

---
*Gerado automaticamente em 2026-05-03T00:00:00-03:00*
