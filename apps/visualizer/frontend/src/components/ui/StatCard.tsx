const COLOR_CLASSES = {
  blue: 'bg-blue-50 text-blue-700 border-blue-200',
  purple: 'bg-purple-50 text-purple-700 border-purple-200',
  green: 'bg-green-50 text-green-700 border-green-200',
  yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
} as const

type StatCardColor = keyof typeof COLOR_CLASSES

interface StatCardProps {
  label: string;
  value: number;
  color: StatCardColor;
}

export function StatCard({ label, value, color }: StatCardProps) {
  const palette = COLOR_CLASSES[color] ?? COLOR_CLASSES.blue
  return (
    <div className={`rounded-lg border p-4 ${palette}`}>
      <p className="text-sm font-medium">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  )
}
