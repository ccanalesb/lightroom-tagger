interface SkeletonGridProps {
  count?: number;
  className?: string;
}

export function SkeletonGrid({ count = 12, className = 'grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3' }: SkeletonGridProps) {
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
    <div className="border rounded-lg overflow-hidden bg-white">
      <div className="aspect-square bg-gray-200 animate-pulse" />
      <div className="p-2 space-y-1">
        <div className="h-3 bg-gray-200 rounded animate-pulse" />
        <div className="h-2 bg-gray-200 rounded w-2/3 animate-pulse" />
      </div>
    </div>
  );
}
