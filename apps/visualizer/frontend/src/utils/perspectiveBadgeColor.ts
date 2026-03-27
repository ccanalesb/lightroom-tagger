export function perspectiveBadgeColor(score: number): string {
  if (score >= 7) return 'bg-green-50 text-green-700';
  if (score >= 5) return 'bg-yellow-50 text-yellow-700';
  return 'bg-red-50 text-red-700';
}
