export function ScoreLine({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500">{label}:</span>
      <span className="font-mono">{(score * 100).toFixed(0)}%</span>
    </div>
  );
}
