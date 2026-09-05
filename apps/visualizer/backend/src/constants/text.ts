/**
 * Shared text-processing constants.
 *
 * Minimal stopword list for Mirror distinctive-descriptor log-odds. Extending it
 * would change which descriptors surface.
 */
export const EN_STOPWORDS: ReadonlySet<string> = new Set([
  'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
  'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
  'it', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they',
  'my', 'your', 'our', 'their',
]);
