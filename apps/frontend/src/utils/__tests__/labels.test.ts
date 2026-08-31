/**
 * labelForVerificationReason — sem teste que exercite a tradução, um bug que
 * volta a mostrar a chave crua (`epi_presente`) na tela passa despercebido:
 * Eventos.test.tsx só usa motivo LIVRE, que cai no fallback e sai igual dos
 * dois jeitos (achado do veredito, ver Verificacao.test.tsx).
 */
import { describe, expect, it } from 'vitest'
import { labelForVerificationReason, MOTIVOS_VERIFICACAO } from '../labels'

describe('labelForVerificationReason', () => {
  it('traduz toda chave estruturada para o rótulo em pt-BR', () => {
    for (const { valor, rotulo } of MOTIVOS_VERIFICACAO) {
      expect(labelForVerificationReason(valor)).toBe(rotulo)
    }
  })

  it('motivo livre (legado, fora do mapa) volta como veio — nunca some', () => {
    expect(labelForVerificationReason('A caixa pegou a luva do outro operador')).toBe(
      'A caixa pegou a luva do outro operador',
    )
  })
})
