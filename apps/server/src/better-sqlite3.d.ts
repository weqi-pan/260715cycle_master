declare module 'better-sqlite3' {
  export interface Statement {
    run(...parameters: unknown[]): { changes: number; lastInsertRowid: number | bigint }
    get(...parameters: unknown[]): unknown
    all(...parameters: unknown[]): unknown[]
  }
  export interface Database {
    pragma(source: string, options?: { simple?: boolean }): unknown
    prepare(sql: string): Statement
    exec(sql: string): void
    transaction<Arguments extends unknown[], Result>(handler: (...args: Arguments) => Result): (...args: Arguments) => Result
    close(): void
  }
  const DatabaseConstructor: {
    new (path: string, options?: { readonly?: boolean; fileMustExist?: boolean }): Database
  }
  export default DatabaseConstructor
}
