/**
 * User-added provider models. Port of the `provider_models` helpers in
 * `apps/visualizer/backend/database.py`.
 *
 * Lives in `visualizer.db` rather than `library.db`: these are app settings, not
 * catalog data.
 */
import type { Db } from '../connection.js';

export interface UserModelRow {
  provider_id: string;
  model_id: string;
  model_name: string;
  vision: number;
}

/** User-added models, optionally scoped to one provider. */
export function getUserModels(db: Db, providerId?: string): UserModelRow[] {
  if (providerId !== undefined) {
    return db
      .prepare(
        `
        SELECT provider_id, model_id, model_name, vision
        FROM provider_models
        WHERE provider_id = ?
        ORDER BY model_id
        `,
      )
      .all(providerId) as UserModelRow[];
  }
  return db
    .prepare(
      `
      SELECT provider_id, model_id, model_name, vision
      FROM provider_models
      ORDER BY provider_id, model_id
      `,
    )
    .all() as UserModelRow[];
}

/** Raised when the (provider, model) pair already exists; the API maps it to 409. */
export class DuplicateUserModelError extends Error {
  constructor(providerId: string, modelId: string) {
    super(`Model ${modelId} already exists for ${providerId}`);
    this.name = 'DuplicateUserModelError';
  }
}

/** Insert a user-defined model row. */
export function addUserModel(
  db: Db,
  providerId: string,
  modelId: string,
  modelName: string,
  vision = true,
): void {
  try {
    db.prepare(
      `
      INSERT INTO provider_models (provider_id, model_id, model_name, vision)
      VALUES (?, ?, ?, ?)
      `,
    ).run(providerId, modelId, modelName, vision ? 1 : 0);
  } catch (e) {
    // The primary key is (provider_id, model_id); a clash is a 409, not a 500.
    if ((e as { code?: string }).code === 'SQLITE_CONSTRAINT_PRIMARYKEY') {
      throw new DuplicateUserModelError(providerId, modelId);
    }
    throw e;
  }
}

/** Delete a user-defined model. Returns whether a row was removed. */
export function deleteUserModel(db: Db, providerId: string, modelId: string): boolean {
  const info = db
    .prepare('DELETE FROM provider_models WHERE provider_id = ? AND model_id = ?')
    .run(providerId, modelId);
  return info.changes > 0;
}
