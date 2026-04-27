import { Suspense } from 'react'
import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteMatching } from '../cache'
import { useQuery } from '../useQuery'

type Deferred<T> = {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function QueryValue({
  id,
  resources,
  initialValue,
}: {
  id: string
  resources: Record<string, Deferred<number>>
  initialValue?: number
}) {
  const value = useQuery(['demo', id] as const, () => resources[id].promise, {
    initialValue,
  })
  return <div>{`value:${value}`}</div>
}

beforeEach(() => {
  deleteMatching(() => true)
  vi.clearAllMocks()
})

describe('useQuery', () => {
  it('suspends on first load when there is no prior value', () => {
    const resources = { first: deferred<number>() }
    render(
      <Suspense fallback={<div>loading</div>}>
        <QueryValue id="first" resources={resources} />
      </Suspense>,
    )
    expect(screen.getByText('loading')).toBeInTheDocument()
  })

  it('keeps prior value visible while a new key is loading', async () => {
    const resources = {
      first: deferred<number>(),
      second: deferred<number>(),
    }

    const { rerender } = render(
      <Suspense fallback={<div>loading</div>}>
        <QueryValue id="first" resources={resources} />
      </Suspense>,
    )

    expect(screen.getByText('loading')).toBeInTheDocument()

    await act(async () => {
      resources.first.resolve(1)
      await resources.first.promise
    })
    expect(await screen.findByText('value:1')).toBeInTheDocument()

    rerender(
      <Suspense fallback={<div>loading</div>}>
        <QueryValue id="second" resources={resources} />
      </Suspense>,
    )
    expect(screen.queryByText('loading')).not.toBeInTheDocument()
    expect(screen.getByText('value:1')).toBeInTheDocument()

    await act(async () => {
      resources.second.resolve(2)
      await resources.second.promise
    })
    expect(await screen.findByText('value:2')).toBeInTheDocument()
  })

  it('uses initialValue on first pending fetch without suspending', () => {
    const resources = { first: deferred<number>() }
    render(
      <Suspense fallback={<div>loading</div>}>
        <QueryValue id="first" resources={resources} initialValue={0} />
      </Suspense>,
    )
    expect(screen.queryByText('loading')).not.toBeInTheDocument()
    expect(screen.getByText('value:0')).toBeInTheDocument()
  })
})
