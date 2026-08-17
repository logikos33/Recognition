import { describe, expect, it } from 'vitest'
import { ConcurrencyQueue } from '../concurrencyQueue'

function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

describe('ConcurrencyQueue', () => {
  it('runs tasks up to the limit concurrently', async () => {
    const queue = new ConcurrencyQueue(2)
    const d1 = deferred<number>()
    const d2 = deferred<number>()
    const started: number[] = []

    const p1 = queue.run(() => {
      started.push(1)
      return d1.promise
    })
    const p2 = queue.run(() => {
      started.push(2)
      return d2.promise
    })

    // Both start immediately — limit is 2, exactly 2 tasks queued.
    expect(started).toEqual([1, 2])

    d1.resolve(10)
    d2.resolve(20)
    expect(await p1).toBe(10)
    expect(await p2).toBe(20)
  })

  it('queues extra tasks beyond the limit until a slot frees up', async () => {
    const queue = new ConcurrencyQueue(1)
    const started: number[] = []
    const d1 = deferred<void>()

    const p1 = queue.run(async () => {
      started.push(1)
      await d1.promise
    })
    const p2 = queue.run(async () => {
      started.push(2)
    })

    // Task 2 must NOT have started yet — task 1 still holds the only slot.
    await Promise.resolve()
    expect(started).toEqual([1])

    d1.resolve()
    await p1
    await p2
    expect(started).toEqual([1, 2])
  })

  it('propagates rejection without blocking the queue', async () => {
    const queue = new ConcurrencyQueue(1)
    const failing = queue.run(() => Promise.reject(new Error('boom')))
    await expect(failing).rejects.toThrow('boom')

    const ok = await queue.run(() => Promise.resolve('after-failure'))
    expect(ok).toBe('after-failure')
  })

  it('never runs more than `limit` tasks at once, even with many callers', async () => {
    const queue = new ConcurrencyQueue(2)
    let concurrent = 0
    let maxConcurrent = 0

    const tasks = Array.from({ length: 10 }, () =>
      queue.run(async () => {
        concurrent += 1
        maxConcurrent = Math.max(maxConcurrent, concurrent)
        await new Promise((r) => setTimeout(r, 5))
        concurrent -= 1
      }),
    )

    await Promise.all(tasks)
    expect(maxConcurrent).toBeLessThanOrEqual(2)
  })
})
