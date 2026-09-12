export function parseTaskHash(hash: string): number | null {
  const match = hash.match(/^#task\/(\d+)$/)
  if (!match) return null
  const taskId = Number(match[1])
  return Number.isSafeInteger(taskId) && taskId > 0 ? taskId : null
}
