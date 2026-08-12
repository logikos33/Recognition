/**
 * ConcurrencyQueue — limita quantas tarefas assíncronas rodam ao mesmo
 * tempo, mesmo quando N chamadores independentes decidem disparar juntos
 * (ex.: 29 miniaturas de câmera entrando na viewport de uma vez em
 * CameraTriagePage — nunca as 29 de uma vez, ver ADR de triagem).
 *
 * Uso: `snapshotQueue.run(() => cameraService.getSnapshot(id))` — a chamada
 * só executa quando houver uma "vaga"; até lá fica numa fila FIFO.
 */
type Task<T> = () => Promise<T>

export class ConcurrencyQueue {
  private active = 0
  private readonly waiting: Array<() => void> = []

  constructor(private readonly limit: number) {}

  run<T>(task: Task<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const attempt = () => {
        this.active += 1
        task()
          .then(resolve, reject)
          .finally(() => {
            this.active -= 1
            const next = this.waiting.shift()
            if (next) next()
          })
      }
      if (this.active < this.limit) attempt()
      else this.waiting.push(attempt)
    })
  }
}

/** Fila compartilhada por TODAS as miniaturas de snapshot da página de
 * triagem — concorrência 1-2 (⛔ nunca as 29 de uma vez). */
export const snapshotQueue = new ConcurrencyQueue(2)
