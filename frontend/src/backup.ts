export interface BackupPayload {
  schema_version: number
  exported_at?: string
  tables: Record<string, unknown[]>
}

export function isBackupPayload(value: unknown): value is BackupPayload {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<BackupPayload>
  return candidate.schema_version === 1
    && !!candidate.tables
    && typeof candidate.tables === 'object'
    && !Array.isArray(candidate.tables)
}
