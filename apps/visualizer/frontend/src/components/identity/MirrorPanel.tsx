import { useState } from 'react'
import { IdentityAPI, type MirrorExemplar, type MirrorResponse, type MirrorTechniqueSection } from '../../services/api'
import { useQuery } from '../../data'
import { Card, CardContent } from '../ui/Card'
import { thumbnailUrl } from '../../utils/imageUrl'
import {
  IDENTITY_MIRROR_EMPTY,
  IDENTITY_MIRROR_INTRO,
  IDENTITY_MIRROR_LOW_COVERAGE,
  IDENTITY_MIRROR_SECTION,
  IDENTITY_MIRROR_STANDOUT,
  IDENTITY_MIRROR_WHY_HERE,
} from '../../constants/strings'

function formatStatTooltip(section: MirrorTechniqueSection): string {
  const wr = Math.round(section.win_rate * 100)
  const chance = Math.round(section.chance_rate * 100)
  return `wins ${wr}% of contests vs ~${chance}% by chance · z=${section.z_score}`
}

function MirrorExemplarModal({
  section,
  exemplar,
  onClose,
}: {
  section: MirrorTechniqueSection
  exemplar: MirrorExemplar
  onClose: () => void
}) {
  const sorted = [...exemplar.per_perspective].sort((a, b) => b.percentile - a.percentile)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
      role="presentation"
      onClick={(ev) => {
        if (ev.target === ev.currentTarget) onClose()
      }}
    >
      <div
        className="grid max-h-[88vh] w-full max-w-[880px] overflow-auto rounded-card border border-border bg-surface md:grid-cols-[1.2fr_1fr]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mirror-modal-title"
      >
        <div className="flex items-center justify-center bg-black">
          <img
            src={thumbnailUrl('catalog', exemplar.image_key)}
            alt=""
            className="max-h-[88vh] w-full object-contain"
          />
        </div>
        <div className="space-y-4 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="break-all text-xs text-text-tertiary">{exemplar.filename || exemplar.image_key}</p>
              <h3 id="mirror-modal-title" className="text-lg font-semibold text-text">
                {IDENTITY_MIRROR_WHY_HERE}
              </h3>
            </div>
            <button
              type="button"
              className="text-2xl leading-none text-text-tertiary hover:text-text"
              aria-label="Close"
              onClick={onClose}
            >
              ×
            </button>
          </div>

          <div className="rounded-base border border-accent/40 bg-bg p-3">
            <p className="text-[11px] uppercase tracking-wider text-accent">{IDENTITY_MIRROR_STANDOUT}</p>
            <p className="mt-1 text-base font-semibold text-text">
              {section.display_name} — {exemplar.percentile}th percentile
            </p>
            <p className="mt-2 text-sm text-text-secondary">
              Ranks in the top {(100 - exemplar.percentile).toFixed(1)}% of your catalog on this lens
              {exemplar.purity > 0
                ? `, and leads its own next-strongest lens by ${exemplar.purity} points (distinctive, not just generally strong).`
                : '.'}
            </p>
            <p className="mt-2 text-xs text-text-tertiary">{formatStatTooltip(section)}</p>
          </div>

          <ul className="space-y-0 text-sm">
            {sorted.map((row) => {
              const top = row.perspective_slug === section.perspective_slug
              const pct = Math.round(row.percentile * 1000) / 10
              return (
                <li
                  key={row.perspective_slug}
                  className="grid grid-cols-[1fr_auto] items-center gap-2 border-t border-border py-2"
                >
                  <span className={top ? 'font-semibold text-accent' : 'text-text'}>{row.display_name}</span>
                  <span className="tabular-nums text-text-secondary">
                    {pct}th pct · {row.score}/10
                  </span>
                  <span className="col-span-2 h-1 overflow-hidden rounded bg-bg">
                    <span
                      className={`block h-full ${top ? 'bg-accent' : 'bg-accent/50'}`}
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </span>
                </li>
              )
            })}
          </ul>

          {exemplar.rationale_preview ? (
            <p className="text-sm text-text-secondary">{exemplar.rationale_preview}</p>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function TechniqueBlock({
  section,
  onOpenExemplar,
}: {
  section: MirrorTechniqueSection
  onOpenExemplar: (exemplar: MirrorExemplar) => void
}) {
  return (
    <section className="space-y-3" aria-labelledby={`mirror-tech-${section.perspective_slug}`}>
      <div className="flex flex-wrap items-baseline gap-3">
        <h3 id={`mirror-tech-${section.perspective_slug}`} className="text-xl font-semibold text-text">
          {section.display_name}
        </h3>
        <span
          className={`cursor-help border-b border-dotted text-sm font-semibold ${
            section.leading_not_distinctive
              ? 'border-border text-text-secondary'
              : 'border-accent/50 text-accent'
          }`}
          title={formatStatTooltip(section)}
          tabIndex={0}
        >
          {section.strength_label}
        </span>
        {section.low_coverage ? (
          <span className="rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs text-warning">
            {IDENTITY_MIRROR_LOW_COVERAGE.replace('{pct}', String(Math.round(section.coverage * 100)))}
          </span>
        ) : null}
      </div>

      {section.leading_not_distinctive ? (
        <p className="text-sm text-text-tertiary">
          No technique clears the bar for a distinctive signature — your strengths are fairly even. This is
          simply your leading lens.
        </p>
      ) : null}

      {section.descriptors.length > 0 ? (
        <ul className="flex flex-wrap gap-2 text-xs">
          {section.descriptors.map((d) => (
            <li
              key={d.token}
              className="rounded-full border border-border bg-bg px-2 py-0.5 text-text-secondary"
            >
              <span className="font-medium text-text">{d.token}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {section.exemplars.length > 0 ? (
        <div className="flex gap-2.5 overflow-x-auto pb-2">
          {section.exemplars.map((exemplar, index) => (
            <button
              key={exemplar.image_key}
              type="button"
              className="relative h-[150px] w-[150px] shrink-0 snap-start overflow-hidden rounded-base border border-border bg-bg transition hover:-translate-y-0.5 hover:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent"
              onClick={() => onOpenExemplar(exemplar)}
            >
              <span className="absolute left-1.5 top-1.5 rounded-md bg-black/60 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                #{index + 1}
              </span>
              <img
                src={thumbnailUrl('catalog', exemplar.image_key)}
                alt={`Exemplar ${index + 1}`}
                loading="lazy"
                className="h-full w-full object-cover"
              />
            </button>
          ))}
        </div>
      ) : (
        <p className="text-sm italic text-text-tertiary">No exemplars yet for this technique.</p>
      )}
    </section>
  )
}

function MirrorContent({ data }: { data: MirrorResponse }) {
  const [modal, setModal] = useState<{ section: MirrorTechniqueSection; exemplar: MirrorExemplar } | null>(
    null,
  )

  if (data.sections.length === 0) {
    return (
      <p className="text-sm text-text-secondary" role="status">
        {IDENTITY_MIRROR_EMPTY}
      </p>
    )
  }

  return (
    <>
      <p className="text-sm text-text-secondary">
        {IDENTITY_MIRROR_INTRO.replace('{count}', String(data.population))}
      </p>
      <div className="space-y-10">
        {data.sections.map((section) => (
          <TechniqueBlock
            key={section.perspective_slug}
            section={section}
            onOpenExemplar={(exemplar) => setModal({ section, exemplar })}
          />
        ))}
      </div>
      {data.meta?.scores_are_advisory ? (
        <p className="text-xs text-text-tertiary">{data.meta.scores_are_advisory}</p>
      ) : null}
      {modal ? (
        <MirrorExemplarModal
          section={modal.section}
          exemplar={modal.exemplar}
          onClose={() => setModal(null)}
        />
      ) : null}
    </>
  )
}

export function MirrorPanel() {
  const data = useQuery(['identity', 'mirror'] as const, () => IdentityAPI.getMirror())

  return (
    <section className="space-y-3" aria-labelledby="identity-mirror-heading">
      <h2 id="identity-mirror-heading" className="text-card-title text-text">
        {IDENTITY_MIRROR_SECTION}
      </h2>
      <Card padding="md">
        <CardContent className="space-y-6 !text-text">
          <MirrorContent data={data} />
        </CardContent>
      </Card>
    </section>
  )
}
