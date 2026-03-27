/** Tailwind classes for description panel score pills (text + background). */
export function descriptionScoreColor(score: number): string {
  if (score >= 7) return 'text-green-700 bg-green-50';
  if (score >= 5) return 'text-yellow-700 bg-yellow-50';
  return 'text-red-700 bg-red-50';
}

/** Tailwind classes for compact perspective badges (background + text). */
export function perspectiveBadgeColor(score: number): string {
  if (score >= 7) return 'bg-green-50 text-green-700';
  if (score >= 5) return 'bg-yellow-50 text-yellow-700';
  return 'bg-red-50 text-red-700';
}
