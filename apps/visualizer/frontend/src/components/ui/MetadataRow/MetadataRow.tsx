interface MetadataRowProps {
  label: string;
  value: string;
  mono?: boolean;
}

export function MetadataRow({ label, value, mono = false }: MetadataRowProps) {
  return (
    <div className="flex justify-between items-start py-2 border-b border-border last:border-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className={`text-sm text-text text-right ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}
