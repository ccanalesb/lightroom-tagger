# Single-Image Matching from Instagram Detail

**Date:** 2026-03-27
**Status:** Ready for planning

## What We're Building

Replace the non-functional "Open Local File" button in the Instagram image detail modal (`ImageDetailsModal` in `InstagramPage.tsx`) with a "Match This Photo" action that runs the vision matching pipeline scoped to a single Instagram image.

The user stays in the modal, sees inline progress, gets a summary on completion, and can tweak settings and re-run without closing.

## Why This Approach

Running full batch matching for 45+ images when you just want to check one photo is wasteful. The current "Open Local File" button opens a `file://` URL that browsers block — dead UI. Replacing it with single-image matching turns dead space into the most useful action you can take on an Instagram detail view.

## Key Decisions

1. **Replace, don't add** — "Open Local File" is removed entirely. The new "Match This Photo" button takes its place.

2. **Same pipeline, scoped to one image** — Uses the same `vision_match` job type but with a `media_key` field in metadata to scope processing to a single Instagram image. Backend filters to just that image instead of all unprocessed.

3. **Full advanced settings** — Same `AdvancedOptions` panel as the Matching page: model selector, threshold, weights. Collapsed by default.

4. **Month/date scoping** — Auto-detect from the Instagram image's date (search catalog +/-90 days), but allow manual override with a month picker. The auto-detected range shows as the default.

5. **Inline progress** — Spinner + status text in the modal while the job runs. No navigation away.

6. **Completion summary** — Shows "Matched" / "No match" with the score and a link to the Matching Results page. Does not show full candidate list inline.

7. **Re-runnable** — After completion, settings remain editable. User can tweak model/weights and re-run from the same modal.

## Scope

### In scope
- New "Match This Photo" button replacing "Open Local File" in `ImageDetailsModal`
- Backend support for single-image `vision_match` job (`media_key` in metadata)
- AdvancedOptions integration in the modal
- Auto-detected date range with manual month override
- Inline progress/completion UI
- Re-run capability

### Out of scope
- Inline candidate thumbnails or side-by-side comparison
- Approve/reject workflow from the modal
- Changes to the batch Matching page

## Technical Notes

### Frontend
- `InstagramPage.tsx` — `ImageDetailsModal` section, replace the "Open Local File" button block (lines ~390-397)
- Reuse `AdvancedOptions` component from `components/AdvancedOptions.tsx`
- Reuse `JobsAPI.create()` and socket `job_updated` listener for progress
- Need month data from `ImagesAPI.getInstagramMonths()` for the manual picker

### Backend
- `handlers.py` — `handle_vision_match` needs to accept optional `media_key` in metadata and filter `match_dump_media` (or call a narrower function) to process only that image
- `match_instagram_dump.py` — `match_dump_media` or a new `match_single_media` function scoped to one `media_key`
- Job result should include enough info for the summary (matched catalog key, score, vision result)

## Open Questions

None — all key decisions resolved during brainstorming.
