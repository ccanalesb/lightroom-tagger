export function descriptionScoreColor(score: number): string {
  if (score >= 7) return 'text-green-700 bg-green-50';
  if (score >= 5) return 'text-yellow-700 bg-yellow-50';
  return 'text-red-700 bg-red-50';
}
