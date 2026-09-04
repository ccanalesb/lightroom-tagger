/**
 * Shared text-processing constants.
 *
 * A deliberately minimal stopword list, not a full NLTK set: it exists so the
 * Mirror's distinctive-descriptor log-odds are not dominated by articles and
 * pronouns. Extending it would change which descriptors surface, so it stays a
 * verbatim copy.
 */
export const EN_STOPWORDS: ReadonlySet<string> = new Set([
  'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
  'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
  'it', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they',
  'my', 'your', 'our', 'their',
]);
