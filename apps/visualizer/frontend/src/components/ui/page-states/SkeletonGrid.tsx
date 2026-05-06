import { TILE_GRID_CLASS } from '../TileGrid';

interface SkeletonGridProps {
  count?: number;
  className?: string;
}

export function SkeletonGrid({ count = 12, className = TILE_GRID_CLASS }: SkeletonGridProps) {
  return (
    <div className={className}>
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="border border-border rounded-card overflow-hidden bg-bg">
      <div className="aspect-square bg-border animate-pulse" />
      <div className="p-2 space-y-1">
        <div className="h-3 bg-border rounded animate-pulse" />
        <div className="h-2 bg-border rounded w-2/3 animate-pulse" />
      </div>
    </div>
  );
}
