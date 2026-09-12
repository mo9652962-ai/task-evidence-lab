export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly details?: unknown) {
    super(message)
    this.name = 'ApiError'
  }
}

async function fetchWithTimeout(path: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('请求超时，请稍后重试', 408)
    throw new ApiError('网络请求失败，请检查本地服务是否已启动', 0, error)
  } finally {
    clearTimeout(timer)
  }
}

async function responseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null
  const detail = typeof body?.detail === 'string' ? body.detail : `请求失败（${response.status}）`
  return new ApiError(detail, response.status, body ?? undefined)
}

export async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 10000): Promise<T> {
  const response = await fetchWithTimeout(path, init, timeoutMs)
  if (!response.ok) throw await responseError(response)
  return await response.json() as T
}

export async function requestText(path: string, init: RequestInit = {}, timeoutMs = 10000): Promise<string> {
  const response = await fetchWithTimeout(path, init, timeoutMs)
  if (!response.ok) throw await responseError(response)
  return await response.text()
}
