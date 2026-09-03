/**
 * O nome de cada módulo em PORTUGUÊS DE GENTE — a fonte única.
 *
 * Existe porque duas telas precisam falar do mesmo módulo com a mesma palavra:
 * `Modulos.tsx` (o cartão em `/novo/modules`) e `CamerasPorModulo.tsx` (a
 * atribuição de câmeras no Estúdio). Quem usa é o dono da fábrica — se um
 * lugar disser "Carga" e o outro "counting", ele tem de adivinhar que são a
 * mesma coisa.
 *
 * O CATÁLOGO de `Modulos.tsx` continua lá e continua sendo dele: ele carrega
 * ícone e destino de navegação, e só lista módulo que TEM tela (por isso
 * `basic` e `analytics` não viram cartão). Aqui é o oposto — `basic` e
 * `analytics` PRECISAM aparecer, porque o tenant pode ter câmera atribuída a
 * eles mesmo sem tela própria. Dois conjuntos, um vocabulário.
 */

/** Nome que aparece na tela. Nunca o código. */
export const ROTULO_MODULO: Record<string, string> = {
  epi: 'EPI · Segurança',
  quality: 'Qualidade',
  counting: 'Carga',
  basic: 'Monitoramento simples',
  analytics: 'Análises',
}

/** Uma linha dizendo o que o módulo faz com a imagem daquela câmera. */
export const DESCRICAO_MODULO: Record<string, string> = {
  epi: 'Confere capacete, óculos, luva e protetor em quem aparece na imagem',
  quality: 'Inspeciona a peça: aprova, reprova e manda para retrabalho',
  counting: 'Conta o que entra e o que sai na expedição',
  basic: 'Só guarda a imagem, sem análise automática',
  analytics: 'Relatórios e indicadores a partir do que as outras áreas veem',
}

/**
 * Rótulo de um código, com plano B honesto.
 *
 * Um módulo que a plataforma ligar e ninguém traduzir aqui cai no próprio
 * código. É jargão, sim — e ainda assim melhor que a alternativa: esconder a
 * opção deixaria o dono sem conseguir atribuir a câmera a um módulo que ele
 * comprou. Aparecer feio é recuperável; sumir não é.
 */
export function rotuloModulo(codigo: string): string {
  return ROTULO_MODULO[codigo] ?? codigo
}
