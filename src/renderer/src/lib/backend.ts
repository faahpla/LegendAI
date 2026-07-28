export function request<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  return window.legendAI.request<T>(path, method, data)
}
