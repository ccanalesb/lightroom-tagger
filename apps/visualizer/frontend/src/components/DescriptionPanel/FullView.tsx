import type { ImageDescription } from '../../services/api'
import {
  DESC_PANEL_SUMMARY,
  DESC_PANEL_COMPOSITION,
  DESC_PANEL_PERSPECTIVES,
  DESC_PANEL_TECHNICAL,
  DESC_PANEL_SUBJECTS,
  DESC_PANEL_MODEL,
  DESC_BEST_FIT,
  DESC_COMPOSITION_DEPTH,
  DESC_COMPOSITION_BALANCE,
  DESC_TECHNICAL_MOOD,
  DESC_TECHNICAL_LIGHTING,
  DESC_TECHNICAL_TIME,
  DESC_TECHNICAL_COLORS,
} from '../../constants/strings'
import { Section } from '../shared/Section'
import { underscoreToSpaces } from '../../utils/underscoreToSpaces'
import { descriptionScoreColor } from '../../utils/scoreColorClasses'
import { DESCRIPTION_PERSPECTIVE_LABELS } from './perspectiveLabels'

interface FullViewProps {
  description: ImageDescription
}

export function FullView({ description }: FullViewProps) {
  const { composition, perspectives, technical, subjects } = description

  return (
    <div className="space-y-3 text-sm">
      {description.summary && (
        <Section title={DESC_PANEL_SUMMARY}>
          <p className="text-gray-700">{description.summary}</p>
        </Section>
      )}

      {perspectives && Object.keys(perspectives).length > 0 && (
        <Section title={DESC_PANEL_PERSPECTIVES}>
          <div className="space-y-2">
            {(Object.entries(perspectives) as [string, { analysis: string; score: number }][]).map(
              ([key, val]) => (
                <div key={key} className="flex gap-2">
                  <div className="flex-shrink-0 w-20">
                    <span className={`inline-block text-xs px-1.5 py-0.5 rounded font-medium ${descriptionScoreColor(val.score)}`}>
                      {DESCRIPTION_PERSPECTIVE_LABELS[key] || key} {val.score}
                    </span>
                    {description.best_perspective === key && (
                      <span className="block text-[10px] text-gray-400 mt-0.5">{DESC_BEST_FIT}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-600 flex-1">{val.analysis}</p>
                </div>
              ),
            )}
          </div>
        </Section>
      )}

      {composition && Object.keys(composition).length > 0 && (
        <Section title={DESC_PANEL_COMPOSITION}>
          <div className="text-xs text-gray-600 space-y-1">
            {composition.techniques && composition.techniques.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {composition.techniques.map((t) => (
                  <span key={t} className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">
                    {underscoreToSpaces(t)}
                  </span>
                ))}
              </div>
            )}
            {composition.problems && composition.problems.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {composition.problems.map((p) => (
                  <span key={p} className="bg-red-50 text-red-700 px-1.5 py-0.5 rounded">
                    {p}
                  </span>
                ))}
              </div>
            )}
            {composition.depth && (
              <p>
                {DESC_COMPOSITION_DEPTH} {composition.depth}
              </p>
            )}
            {composition.balance && (
              <p>
                {DESC_COMPOSITION_BALANCE} {composition.balance}
              </p>
            )}
          </div>
        </Section>
      )}

      {technical && Object.keys(technical).length > 0 && (
        <Section title={DESC_PANEL_TECHNICAL}>
          <div className="text-xs text-gray-600 space-y-1">
            {technical.mood && (
              <p>
                {DESC_TECHNICAL_MOOD}: {technical.mood}
              </p>
            )}
            {technical.lighting && (
              <p>
                {DESC_TECHNICAL_LIGHTING}: {underscoreToSpaces(technical.lighting)}
              </p>
            )}
            {technical.time_of_day && (
              <p>
                {DESC_TECHNICAL_TIME}: {underscoreToSpaces(technical.time_of_day)}
              </p>
            )}
            {technical.dominant_colors && technical.dominant_colors.length > 0 && (
              <div className="flex items-center gap-1">
                <span>{DESC_TECHNICAL_COLORS}</span>
                {technical.dominant_colors.map((c) => (
                  <span
                    key={c}
                    className="inline-block w-4 h-4 rounded border border-gray-200"
                    style={{ backgroundColor: c }}
                    title={c}
                  />
                ))}
              </div>
            )}
          </div>
        </Section>
      )}

      {subjects && subjects.length > 0 && (
        <Section title={DESC_PANEL_SUBJECTS}>
          <div className="flex flex-wrap gap-1">
            {subjects.map((s) => (
              <span key={s} className="bg-blue-50 text-blue-700 text-xs px-1.5 py-0.5 rounded">
                {s}
              </span>
            ))}
          </div>
        </Section>
      )}

      {description.model_used && (
        <p className="text-[10px] text-gray-400">
          {DESC_PANEL_MODEL}: {description.model_used}
        </p>
      )}
    </div>
  )
}
