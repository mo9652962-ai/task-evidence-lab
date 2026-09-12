import { describe, expect, it } from 'vitest'
import { isBackupPayload } from './backup'

describe('backup payload validation', () => {
  it('accepts a versioned table backup', () => {
    expect(isBackupPayload({ schema_version: 1, tables: { tasks: [] } })).toBe(true)
  })

  it('rejects an unknown backup version or malformed tables', () => {
    expect(isBackupPayload({ schema_version: 2, tables: {} })).toBe(false)
    expect(isBackupPayload({ schema_version: 1, tables: [] })).toBe(false)
  })
})
