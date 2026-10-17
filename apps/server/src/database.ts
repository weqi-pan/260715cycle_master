import DatabaseFactory from 'better-sqlite3'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import type { GameState } from '@cycle-master/api-contract'
import { STATE_SCHEMA_VERSION } from '@cycle-master/api-contract'

export interface SaveRow {
  id: string
  name: string
  story_revision: string
  state_schema_version: number
  current_node_id: string
  cycle_count: number
  state_json: string
  created_at: string
  updated_at: string
}

export class GameDatabase {
  private readonly database: InstanceType<typeof DatabaseFactory>

  constructor(file: string) {
    mkdirSync(path.dirname(file), { recursive: true })
    this.database = new DatabaseFactory(file)
    this.database.pragma('journal_mode = WAL')
    this.database.pragma('foreign_keys = ON')
    this.database.pragma('busy_timeout = 5000')
    this.migrate()
  }

  private migrate(): void {
    this.database.exec(`
      CREATE TABLE IF NOT EXISTS saves (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        story_revision TEXT NOT NULL,
        state_schema_version INTEGER NOT NULL,
        current_node_id TEXT NOT NULL,
        cycle_count INTEGER NOT NULL,
        state_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS persistent_nodes (
        save_id TEXT NOT NULL,
        node_id TEXT NOT NULL,
        data_json TEXT NOT NULL,
        PRIMARY KEY (save_id, node_id),
        FOREIGN KEY (save_id) REFERENCES saves(id) ON DELETE CASCADE
      );
    `)
  }

  listSaves(): SaveRow[] {
    return this.database.prepare('SELECT * FROM saves ORDER BY updated_at DESC').all() as SaveRow[]
  }

  getSave(id: string): SaveRow | null {
    const row = this.database.prepare('SELECT * FROM saves WHERE id = ?').get(id) as SaveRow | undefined
    return row ?? null
  }

  createSave(input: { id: string; name: string; revision: string; state: GameState; now: string }): void {
    this.database.transaction(() => {
      this.database.prepare(`
        INSERT INTO saves
          (id, name, story_revision, state_schema_version, current_node_id, cycle_count, state_json, created_at, updated_at)
        VALUES (@id, @name, @revision, @stateSchemaVersion, @currentNodeId, @cycleCount, @stateJson, @now, @now)
      `).run({
        id: input.id,
        name: input.name,
        revision: input.revision,
        stateSchemaVersion: STATE_SCHEMA_VERSION,
        currentNodeId: input.state.currentNodeId,
        cycleCount: input.state.cycleCount,
        stateJson: JSON.stringify(input.state),
        now: input.now,
      })
      this.replacePersistentNodes(input.id, input.state)
    })()
  }

  updateSave(input: { id: string; name?: string; revision: string; state: GameState; now: string }): boolean {
    const result = this.database.transaction(() => {
      const row = this.database.prepare('SELECT * FROM saves WHERE id = ?').get(input.id) as SaveRow | undefined
      if (!row) return false
      this.database.prepare(`
        UPDATE saves
        SET name = @name, story_revision = @revision, state_schema_version = @stateSchemaVersion,
            current_node_id = @currentNodeId, cycle_count = @cycleCount, state_json = @stateJson, updated_at = @now
        WHERE id = @id
      `).run({
        id: input.id,
        name: input.name ?? row.name,
        revision: input.revision,
        stateSchemaVersion: STATE_SCHEMA_VERSION,
        currentNodeId: input.state.currentNodeId,
        cycleCount: input.state.cycleCount,
        stateJson: JSON.stringify(input.state),
        now: input.now,
      })
      this.replacePersistentNodes(input.id, input.state)
      return true
    })()
    return result === true
  }

  deleteSave(id: string): boolean {
    return this.database.prepare('DELETE FROM saves WHERE id = ?').run(id).changes > 0
  }

  private replacePersistentNodes(saveId: string, state: GameState): void {
    this.database.prepare('DELETE FROM persistent_nodes WHERE save_id = ?').run(saveId)
    const insert = this.database.prepare('INSERT INTO persistent_nodes (save_id, node_id, data_json) VALUES (?, ?, ?)')
    for (const [nodeId, data] of Object.entries(state.persistentNodes)) {
      insert.run(saveId, nodeId, JSON.stringify(data))
    }
  }

  loadPersistentNodes(saveId: string): Record<string, unknown> {
    const rows = this.database.prepare('SELECT node_id, data_json FROM persistent_nodes WHERE save_id = ?').all(saveId) as Array<{ node_id: string; data_json: string }>
    return Object.fromEntries(rows.map(row => [row.node_id, JSON.parse(row.data_json)]))
  }

  close(): void {
    this.database.close()
  }
}
