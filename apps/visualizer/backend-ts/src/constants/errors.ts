/** Backend error message constants. Ported from `constants/errors.py` verbatim —
 * these strings are asserted on by tests and surfaced in the UI. */

// Database errors
export const ERROR_DB_NOT_FOUND = 'Library database not found';
export const ERROR_DB_CONNECTION = 'Database connection failed';

// Resource errors
export const ERROR_IMAGE_NOT_FOUND = 'Image not found';
export const ERROR_IMAGE_FILE_NOT_FOUND = 'Image file not found';
export const ERROR_MEDIA_NOT_FOUND = 'Media not found';

// General errors
export const ERROR_INTERNAL_SERVER = 'Internal server error';
export const ERROR_INVALID_REQUEST = 'Invalid request parameters';
