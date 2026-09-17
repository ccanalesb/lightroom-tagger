/**
 * Reuse `better-sqlite3` statements per connection.
 *
 * `vec0` KNN prepares carry index-scan scratch memory; preparing once per ~43k
 * similarity-scan seeds was leaking multiple GB of RSS. Callers in tight loops
 * should use this instead of `db.prepare()` on every iteration.
 */
import type Database from 'better-sqlite3';
import type { Db } from './connection.js';

type Statement = Database.Statement;

const cache = new WeakMap<Db, Map<string, Statement>>();

export function prepareCached(db: Db, sql: string): Statement {
  let stmts = cache.get(db);
  if (!stmts) {
    stmts = new Map();
    cache.set(db, stmts);
  }
  let stmt = stmts.get(sql);
  if (!stmt) {
    stmt = db.prepare(sql);
    stmts.set(sql, stmt);
  }
  return stmt;
}
