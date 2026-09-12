import { afterEach, describe, expect, it, vi } from 'vitest'
import { request, requestText } from './http'

describe('http request helpers', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('returns JSON for successful responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 })))

    await expect(request<{ ok: boolean }>('/api/health')).resolves.toEqual({ ok: true })
  })

  it('normalizes backend errors while preserving status and details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: '请求参数校验失败', errors: [{ loc: ['body', 'title'] }] }), { status: 422 })))

    await expect(request('/api/tasks', { method: 'POST' })).rejects.toMatchObject({ message: '请求参数校验失败', status: 422, details: { errors: [{ loc: ['body', 'title'] }] } })
  })

  it('returns text responses for report downloads', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('# 报告', { status: 200 })))

    await expect(requestText('/api/tasks/1/report/markdown')).resolves.toBe('# 报告')
  })

  it('turns an aborted request into a timeout error', async () => {
    vi.stubGlobal('fetch', vi.fn((_path: string, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })))

    await expect(request('/api/slow', {}, 5)).rejects.toMatchObject({ message: '请求超时，请稍后重试' })
  })
})
