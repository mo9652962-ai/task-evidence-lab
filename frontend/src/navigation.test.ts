import { describe, expect, it } from 'vitest'
import { parseTaskHash } from './navigation'

describe('task detail navigation', () => {
  it('parses a task hash and ignores unrelated routes', () => {
    expect(parseTaskHash('#task/42')).toBe(42)
    expect(parseTaskHash('#compare')).toBeNull()
    expect(parseTaskHash('#task/not-a-number')).toBeNull()
  })
})
