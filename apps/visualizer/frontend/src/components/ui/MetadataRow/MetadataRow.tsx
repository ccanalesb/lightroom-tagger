interface MetadataRowProps {
  label: string;
  /**
   * Row value. When `null`, `undefined`, or empty string the row renders
   * nothing -- callers don't have to wrap each `<MetadataRow>` in a
   * ternary to hide missing data.
   */
  value: string | null | undefined;
  mono?: boolean;
}

export function MetadataRow({ label, value, mono = false }: MetadataRowProps) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex justify-between items-start py-2 border-b border-border last:border-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className={`text-sm text-text text-right ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}
