# Parked capabilities

Capabilities that were built, used, and then removed from `master` during the consolidation
tracked by [map #218](https://github.com/ccanalesb/lightroom-tagger/issues/218).

**Removed is not lost.** Git holds every deleted line forever, and each capability has an
annotated tag pointing at the last commit that contained it — `git checkout parked/<slug>`
puts you back in a tree where the feature works. What git cannot hold is *why* it was
retired and what the attempt taught. That is the only job of these docs.

| Capability | Status | Tag | Doc |
| --- | --- | --- | --- |
| Chat / NL / semantic search | to be removed by [#223](https://github.com/ccanalesb/lightroom-tagger/issues/223) | `parked/chat-search` | — |
| Instagram import + vision matching | to be removed by [#225](https://github.com/ccanalesb/lightroom-tagger/issues/225) | `parked/instagram-matching` | — |
| Posting analytics | retired 2026-08-12 ([#222](https://github.com/ccanalesb/lightroom-tagger/issues/222)) | `parked/posting-analytics` | [posting-analytics.md](posting-analytics.md) |

Each removal PR fills in its own row — adding the retirement date and linking the doc it
writes — so this table is never a promise of a file that does not exist.

## Writing one

Copy [`_TEMPLATE.md`](_TEMPLATE.md). Three sections and a few paragraphs; the header and
footer lines carry the history pointer. **Longer is not better** — a park doc nobody
finishes is worth less than a short one that lands, and the reasoning is the payload, not
the description.

Cut the tag on the last commit that still contains the capability, **before** the removal
PR merges:

```sh
git tag -a parked/<slug> -m "last commit containing <capability> (map #218)"
git push origin parked/<slug>
```

Record both the tag name and its short SHA in the doc. The tag is what you check out; the
SHA is what survives if the tag is ever deleted or a mirror drops it.

## Not parked

**Catalog similarity** is not in this directory and should not be added to it. It survives
the consolidation and is being *reframed* rather than retired — see
[#226](https://github.com/ccanalesb/lightroom-tagger/issues/226). CLIP embeddings,
`clip_similarity` and `sqlite-vec` all stay. Only the Instagram-dump side of CLIP goes,
with [#225](https://github.com/ccanalesb/lightroom-tagger/issues/225).

Removal and reframe are different diagnoses. The three capabilities above failed on cost,
precision, or a dependency that was itself being deleted — no change of presentation fixes
any of those. A capability that goes unused because it was *framed* badly is a design
problem, and belongs in a design ticket, not here.
