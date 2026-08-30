# Lista para o design — pista F5 (Estúdio + Admin + Acesso + Kiosk/TV)

> Irmão de `LISTA-PARA-O-DESIGN.md` (aquele é **gerado** por
> `tools/build_migration_map.py design` — não editar à mão). Este é o
> apêndice manual da pista F5: itens que a prancha `Estúdio.dc.html` e o
> bundle de handoff não resolveram, ou resolveram diferente do que o produto
> construiu. Achados durante SR1 (Estúdio, PRs #572–#586).

1. **Re-skin do canvas de anotação.** `AnnotationStudio` e `CropClassifier`
   (`components/annotation/`) são INFRA compartilhada, congelada nesta pista —
   os wrappers novos (`app/estudio/Dados.tsx`, `Classificar.tsx`) os chamam
   sem tocar no visual interno. O canvas ainda usa a identidade visual antiga;
   falta desenho para portá-lo à identidade `lk.*` sem reescrever a lógica de
   caixa/zoom/pan/undo por baixo.

2. **Áreas "IA" e "Dataset" da prancha.** A prancha de 6 áreas do
   `Estúdio.dc.html` desenha "IA" e "Dataset" como áreas próprias; as rotas de
   backend para isso existem (jobs de propagação/busca por conteúdo, datasets
   e versões — domínio 6/7 do `LISTA-PARA-O-DESIGN.md`), mas não há tela
   nenhuma ainda. Ficam pendentes de desenho antes de qualquer PR de código.

3. **R4 — catálogo de modelos.** Tela de registry MLOps (lista por
   módulo/status, linhagem dataset→job→modelo→deployments, avaliação
   campeão×desafiante) aguarda desenho; hoje `app/estudio/Modelo.tsx` cobre só
   o modelo ativo + ativar, não o catálogo completo.

4. **Admin — visão geral sem aba própria.** O detalhe de tenant no admin não
   tem uma aba "Visão geral" desenhada (câmeras por status/módulo, alertas
   24h, jobs de treino) — pendente também no backend (whitelist de schemas
   quebrada, ver `LISTA-PARA-O-DESIGN.md` domínio 3, item 6).

5. **Troca obrigatória / esqueci / redefinir — hi-fi.** As 3 telas de Acesso
   (F5 SR2) foram implementadas com o wireframe do bundle; falta hi-fi do
   design para a versão final (estados de erro, copy, ilustração).

6. **Kiosk RVB — re-skin.** `/novo/tablet/:station` reusa a máquina de
   estados verbatim (SR3); falta desenho da identidade visual nova para o
   tablet físico da bancada.

7. **Parede TV.** O bundle desenha um "Modo TV" (grade full-screen, sem
   menu). Não construído nesta pista (registrado também em
   `PEDIDOS-AO-BACKEND-F5.md` item 5) — falta desenho de layout antes do
   backend agregado por site.

8. **CTA "Solicitar acesso" do `SemPermissao`.** A tela de bloqueio por gate
   (`frames:annotate` etc.) desenha um botão "Solicitar acesso" no bundle;
   sem backend (não há fluxo de pedido/aprovação de permissão) — não
   implementado, só o texto estático hoje.

9. **Divergência registrada: Cobertura e Classificar como sub-rotas extras.**
   A prancha `Estúdio.dc.html` desenha 6 áreas (Dados/Classes/IA/Dataset/
   Treinos/Modelos); Cobertura e Classificar não têm área própria nela. Como
   as duas são função real do `TrainingPage.tsx` antigo (matriz de cobertura
   classe×câmera; classificação por recorte), entraram como sub-rotas extras
   da lateral do Estúdio em vez de forçadas dentro de uma área onde não cabem
   — decisão de PR-A, registrada para o design reconciliar quando desenhar
   "Dataset"/"IA".
