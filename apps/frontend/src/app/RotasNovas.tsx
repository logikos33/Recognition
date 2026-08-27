/**
 * Rotas do front novo — as que montam o `Shell` Logikos Vision.
 *
 * COEXISTÊNCIA (decisão do Vitor, 27/08): estas rotas correm ao lado do front
 * antigo, que segue inteiro e de pé. O App monta assim:
 *
 *     <Routes>
 *       <Route path={PREFIXO_NOVO} element={<Shell />}>{ROTAS_NOVAS}</Route>
 *       <Route path="*" element={<AppLayout><AppRoutes/></AppLayout>} />
 *     </Routes>
 *
 * POR QUE UM PREFIXO, e não os caminhos do desenho direto:
 *
 * Metade das telas novas MUDA de endereço (`/epi/alerts` → `/epi/eventos`) e a
 * outra metade NÃO (`/epi/dashboard` continua `/epi/dashboard`). Sem prefixo, as
 * que não mudam colidiriam de frente com o front antigo, e a mesma URL teria de
 * servir duas telas — o que "coexistir" justamente não é. Com prefixo, cada
 * front tem endereço próprio, o antigo não muda de comportamento em nada, e o
 * tombamento vira uma operação pequena e reversível: tirar o prefixo e trocar
 * as rotas antigas por redirects (de-para em `docs/migration/DELTA-PRE-MIGRACAO.md`).
 *
 * ⛔ Não registre aqui tela que ainda não existe. Rota apontando para
 * placeholder é tela inventada — e tela sem desenho não se inventa.
 */
import type { ReactElement } from 'react'

/**
 * Prefixo do front novo enquanto os dois convivem. Sai no tombamento.
 *
 * As rotas abaixo são declaradas RELATIVAS de propósito: caminho relativo só
 * consegue existir DENTRO do prefixo, então nenhuma tela nova tem como cair em
 * cima do front antigo por descuido. Há teste que reprova caminho absoluto.
 */
export const PREFIXO_NOVO = '/novo'

/**
 * As telas entram aqui conforme forem migradas E PROVADAS, uma por uma.
 * Lista vazia = o front novo ainda não serve rota nenhuma, e o antigo atende
 * tudo. É o estado honesto até a primeira tela ficar de pé.
 */
export const ROTAS_NOVAS: ReactElement[] = []
