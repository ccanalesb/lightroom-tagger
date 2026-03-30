const VISION_BADGE_COLORS: Record<string, string> = {
  SAME: 'bg-green-100 text-green-800',
  DIFFERENT: 'bg-red-100 text-red-800',
  UNCERTAIN: 'bg-yellow-100 text-yellow-800',
}

export function visionBadgeClasses(result: string | undefined): string {
  return VISION_BADGE_COLORS[result ?? 'UNCERTAIN'] ?? VISION_BADGE_COLORS.UNCERTAIN
}
