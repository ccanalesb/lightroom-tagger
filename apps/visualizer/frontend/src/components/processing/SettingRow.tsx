import { ReactNode } from 'react';

interface SettingRowProps {
  name: string;
  /** What the setting is currently doing, or what is wrong with it. */
  description: ReactNode;
  /** The controls that sit at the end of the row. */
  control: ReactNode;
  /** Shown under the row when the setting needs more than its control fits. */
  panel?: ReactNode;
}

/**
 * One setting in the settings list: name and state on the left, control on the
 * right, and an optional panel underneath.
 *
 * Below `sm` the two halves stack, because a path and a pair of buttons do not
 * share a phone-width line. Everything that can be long sits in a `min-w-0`
 * column so it truncates instead of pushing the controls off-screen.
 */
export function SettingRow({ name, description, control, panel }: SettingRowProps) {
  return (
    <div className="p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <div className="text-sm font-medium text-text">{name}</div>
          <div className="mt-0.5 text-sm text-text-secondary">{description}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:flex-shrink-0">{control}</div>
      </div>
      {panel && <div className="mt-4 space-y-3 border-t border-border pt-4">{panel}</div>}
    </div>
  );
}

/**
 * A path on one line. The directory truncates and the filename does not, since
 * the filename is what identifies the catalog; plain `truncate` would eat it.
 */
export function PathSummary({ path }: { path: string }) {
  const cut = path.lastIndexOf('/');
  return (
    <span className="flex min-w-0" title={path}>
      <span className="truncate text-text-tertiary">{path.slice(0, cut + 1)}</span>
      <span className="flex-shrink-0">{path.slice(cut + 1)}</span>
    </span>
  );
}
