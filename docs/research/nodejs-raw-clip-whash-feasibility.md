# Replacing three Python native deps with Node.js/TypeScript

Research finding: can a Node 24 / macOS arm64 backend fully replace `rawpy`, `sentence-transformers clip-ViT-B-32`,
and `imagehash.whash`, with **no Python left in the process**?

Method: primary sources only (npm registry, GitHub REST API, official repo source, HF model cards, crates.io),
plus **direct empirical testing on this machine** — Node v24.14.1, darwin arm64 — against real camera RAW files
from [raw.pixls.us](https://raw.pixls.us/) and the project's own `.venv` (rawpy 0.26.1 / LibRaw 0.22.0).
Where a number below is measured rather than cited, it says so.

Call sites being replaced:
- `lightroom_tagger/core/analyzer/image_prep.py:130` — `raw.postprocess(use_camera_wb=True, half_size=True)`
- `lightroom_tagger/core/clip_embedding_service.py:17,31` — `SentenceTransformer("clip-ViT-B-32").encode(..., normalize_embeddings=True)`
- `lightroom_tagger/core/hasher.py:38` — `imagehash.whash(img)` (all defaults)

---

## Verdicts

| # | Capability | Verdict | Primary choice | Fallback |
|---|---|---|---|---|
| 1 | RAW decode (`use_camera_wb`, `half_size`) | **viable with caveats** | `libraw-wasm` 1.6.0 via its raw Emscripten factory | `@imagemagick/magick-wasm` 0.0.43 (3–65× slower, no half-size) |
| 2 | CLIP ViT-B/32 embeddings | **viable with caveats** | `onnxruntime-node` 1.29.0 + fp32 `vision_model.onnx` + **hand-rolled Pillow-exact preprocessing** | `@huggingface/transformers` 4.2.0 with `dtype:'fp32'` and its resize bypassed |
| 3 | Wavelet perceptual hash | **viable** | **vendor a ~168-line port** (PIL fixed-point Lanczos + 12-line 2D Haar) | `rosetta-squint-hash` 1.0.0 |

**No Python is required for any of the three.** But two of the three only reach parity by reimplementing
Pillow's resampler in JavaScript — see the cross-cutting finding below.

### The single biggest risk: PIL's resampler is the hinge, and it is load-bearing twice

Items 2 and 3 fail for the *same* reason, and it is not the part anyone would budget for. Neither CLIP nor
whash is hard because of the model or the wavelet — the CLIP ONNX graph is numerically exact
(cosine 1.000000 when fed Python's own tensor, §2.1) and the 2D Haar DWT is **12 lines** (§3.4). Both are
hard because **`sharp`/libvips resizing is not `PIL`/Pillow resizing**, and every stored value in the
database was produced through Pillow:

| Using `sharp` for the resize | Measured consequence |
|---|---|
| CLIP embeddings | cosine **0.92–0.97** vs the stored corpus (0.796 worst case) — inside the near-duplicate band |
| whash | only **33 %** of hashes exact; up to **22/64 bits** wrong |
| Pillow-exact JS port | CLIP `1 − cos < 1.1e-11`; whash **100 %** exact on all non-degenerate images |

So the real cost of this migration is **one carefully-ported, bit-exact Pillow resample module** (~90–110
lines of fixed-point integer arithmetic, `PRECISION_BITS = 22`, `Math.trunc` not `Math.floor`) shared by
both call sites. That module is verified achievable — it was built and measured pixel-identical to PIL
(maxdiff 0). Budget it as a deliberate, tested component, **not** as an incidental `sharp().resize()` call.
The trap is that `sharp` looks like it works: it runs, it's fast, the images look right, and the numbers
are quietly 4–6 bits or 0.05 cosine off.

Secondary risks, in order: (a) `libraw-wasm` produces materially different pixels from rawpy on **Olympus
`.orf` and Samsung `.srw`**, fails entirely on **`.x3f`**, and is off by one pixel on **CR3/SR2** — and
this is *not* fixable by aligning LibRaw versions (tested and refuted, §1.4.1); (b) `libraw-wasm` leaks
until the process dies after ~14 images unless you call `inst.delete()` (§1.3); (c) ~1–2 % of whash values,
concentrated in **blank/void/clipped frames**, can never be bit-matched from JS because pywt's
compiler-contracted FMA has no JS equivalent (§3.5).

Note the ordering dependency: **the RAW decoder is upstream of both other items.** Any ORF/SRW/CR3
divergence in §1 propagates into the whash bits and CLIP vectors for those files, independent of how
perfect the ports in §2 and §3 are.

---

## 1. RAW photo decoding

Target: equivalent to `rawpy`'s `raw.postprocess(use_camera_wb=True, half_size=True)` for
`.dng .raw .cr2 .cr3 .nef .arw .rw2 .orf .raf .sr2 .srw .x3f`.

The project's Python side is **rawpy 0.26.1 bundling LibRaw 0.22.0** (measured: `rawpy.libraw_version` → `(0, 22, 0)`).
That matters — everything below is graded against that exact LibRaw version.

### 1.1 Candidate survey

All dates/versions from the npm registry (`npm view`) and the GitHub REST API, retrieved 2026-09-02.
Download counts from `api.npmjs.org/downloads/point/last-month`.

| Package | Version | Last publish | Downloads/mo | Repo activity | Verdict |
|---|---|---|---|---|---|
| [`libraw-wasm`](https://www.npmjs.com/package/libraw-wasm) | 1.6.0 | 2026-07-02 | **35,650** | [ybouane/LibRaw-Wasm](https://github.com/ybouane/LibRaw-Wasm), 56★, pushed 2026-07-02, CI + release automation | **best option** |
| [`@imagemagick/magick-wasm`](https://www.npmjs.com/package/@imagemagick/magick-wasm) | 0.0.43 | 2026-08-25 | — | [dlemstra/magick-wasm](https://github.com/dlemstra/magick-wasm), actively released | viable fallback |
| [`@colorhythm/libraw-wasm`](https://www.npmjs.com/package/@colorhythm/libraw-wasm) | 1.1.1 | 2026-08-03 | 707 | [colorhythm/libraw-wasm](https://github.com/colorhythm/libraw-wasm), **0★**, repo created 2026-06-03 | too new/unproven |
| [`librawspeed`](https://www.npmjs.com/package/librawspeed) | 1.0.129 | 2025-10-12 | 208 | [pixFlowTeam/librawspeed](https://github.com/pixFlowTeam/librawspeed), 3★ | napi addon, must compile LibRaw; unproven |
| [`librawspeed-full`](https://www.npmjs.com/package/librawspeed-full) | 1.0.132 | 2026-06-10 | 23 | fork of the above (`bookyo/librawspeed-full`) | unproven |
| [`lightdrift-libraw`](https://www.npmjs.com/package/lightdrift-libraw) | 1.0.0 | 2026-08-15 | 742 | `unique01082/lightdrift-libraw` | 1.0.0 only, keyword-stuffed; unproven |
| [`@julianberger/libraw.js`](https://www.npmjs.com/package/@julianberger/libraw.js) | 3.3.1 | 2025-10-23 | 98 | [JulianBerger/libraw.js](https://github.com/JulianBerger/libraw.js), 0★ | fork of below |
| [`libraw.js`](https://www.npmjs.com/package/libraw.js) | 3.0.0 | 2023-03-06 | 39 | [justinkambic/libraw.js](https://github.com/justinkambic/libraw.js), 12★, 7 open issues | stale; napi, needs system LibRaw |
| [`libraw-mini`](https://www.npmjs.com/package/libraw-mini) | 0.1.9 | 2025-12-13 | 139 | [xdadda/libraw-mini](https://github.com/xdadda/libraw-mini), 5★ | pre-1.0 |
| [`libraw`](https://www.npmjs.com/package/libraw) (a.k.a. `node-libraw`) | 0.1.4 | **2017-03-24** | 55 | `m0g/node-libraw`, uses `nan` | **dead** |
| [`dcraw`](https://www.npmjs.com/package/dcraw) | 1.0.3 | **2017-12-14** | — | `zfedoran/dcraw.js`, GPL-2.0 | **dead**; also GPL |
| [`dcraw-wasm`](https://www.npmjs.com/package/dcraw-wasm) | 0.0.3 | 2026-03-15 | 122 | [nhebling/dcraw-wasm](https://github.com/nhebling/dcraw-wasm), 1★ | pre-1.0; dcraw itself is retired upstream |
| [`wasm-imagemagick`](https://www.npmjs.com/package/wasm-imagemagick) | 1.2.8 | **2020-08-20** | — | [KnicKnic/WASM-ImageMagick](https://github.com/KnicKnic/WASM-ImageMagick) | **dead** |
| `@rgba/libraw`, `node-libraw` | — | — | — | — | **do not exist on npm** (registry returns 404) |

`@rgba/libraw` and `node-libraw` were both checked directly against the registry and return
`404 Not Found` — the publishable name is `libraw` (see table), whose last release was 2017.

**Rust → napi-rs options.** All three are alive but none is a drop-in:

- [`rawloader`](https://crates.io/crates/rawloader) 0.37.2 (2026-08-15). Its
  [README format list](https://github.com/pedrocr/rawloader/blob/master/README.md) covers CR2/CRW but
  **not CR3 and not X3F**, and it deliberately returns only "the raw pixels themselves, exactly as encoded
  by the camera" plus WB multipliers — **it does not demosaic**.
- [`imagepipe`](https://crates.io/crates/imagepipe) 0.5.1 (2026-08-15) supplies the demosaic on top of
  rawloader, but it is its own pipeline, so there is **no LibRaw output parity** by construction.
- [`rawler`](https://crates.io/crates/rawler) 0.8.0 (2026-08-30), from
  [dnglab/dnglab](https://github.com/dnglab/dnglab), **does** support CR3
  ([format table](https://github.com/dnglab/dnglab/blob/main/README.md)) — but its purpose is DNG
  conversion/metadata, X3F is absent from its table, and again there is no `postprocess()` equivalent.

So the Rust route costs a napi build, loses parity, and *still* has the X3F gap. Not recommended.

### 1.2 sharp / libvips: ruled out, with a citation

libvips *does* now have a native libraw loader — `dcrawload`, added in **libvips 8.18.0** (17/12/25) per the
[ChangeLog](https://github.com/libvips/libvips/blob/master/ChangeLog), gated on the
`raw` meson feature (`option('raw', ... description: 'Build with libraw')`,
[meson_options.txt:231](https://github.com/libvips/libvips/blob/master/meson_options.txt)). The libvips
[README](https://github.com/libvips/libvips/blob/master/README.md) states: *"### libraw — The usual camera
RAW loader. If this is not present, vips will try to load raw camera images via imagemagick instead."*

But **sharp's prebuilt binaries disable both**. `sharp-libvips`
[`build/posix.sh:390-391`](https://github.com/lovell/sharp-libvips/blob/main/build/posix.sh) passes:

```
-Dmagick=disabled ... -Draw=disabled
```

Confirmed empirically with the current release (measured — `sharp 0.35.4`, `libvips 8.18.6`, darwin arm64):

```
sharp format keys with input support: jpeg,png,webp,tiff,gif,svg,heif,vips
sharp.format.magick.input: {"file":false,"buffer":false,"stream":false}
test.cr3  sharp FAIL Input buffer contains unsupported image format
sony.ARW  sharp FAIL Input buffer contains unsupported image format
test.orf  sharp FAIL Input buffer contains unsupported image format
test.rw2  sharp FAIL Input buffer contains unsupported image format
test.nef  sharp OK tiff 160x120     <-- the tiny EXIF thumbnail, not the image
test.dng  sharp OK tiff 720x480     <-- an embedded preview, not the image
```

The CR2/NEF/DNG "successes" are libvips' TIFF loader latching onto the container and returning a thumbnail
or preview — not a demosaic. sharp's own docs confirm the general shape of this: PDF and OpenSlide input
"[requires] the use of a globally-installed libvips compiled with support for ... ImageMagick or
GraphicsMagick"
([api-constructor.md](https://github.com/lovell/sharp/blob/main/docs/src/content/docs/api-constructor.md)),
and a custom global libvips is *"unsupported on Windows and on macOS when running Node.js under Rosetta"*
([install.md](https://github.com/lovell/sharp/blob/main/docs/src/content/docs/install.md)).

**Conclusion: sharp cannot decode camera RAW and building a custom libvips to make it do so is not a
supportable path.** sharp is still the right tool for the *resize/encode* step after decoding.

### 1.3 `libraw-wasm` — the important gotchas, and that it works anyway

`libraw-wasm` 1.6.0 pins **LibRaw 0.22.1** and lcms2 2.19.1, built with Emscripten 5.0.7
([`compileLibraw.sh`](https://github.com/ybouane/LibRaw-Wasm/blob/main/compileLibraw.sh)).

Its settings object maps **1:1 onto the rawpy call** — from the
[README](https://github.com/ybouane/LibRaw-Wasm/blob/main/readme.md):

```js
halfSize: false,      // -h  : output at 1/2 size
useCameraWb: false,   // -w  : camera's recorded WB
userQual: 3,          // -q  : interpolation quality  (3 = AHD, matches LibRaw/rawpy default)
outputBps: 8,         // -4  : 8 or 16 bits per sample (matches rawpy default)
noAutoBright: false,  //      matches rawpy no_auto_bright=False
outputColor: 1,       // -o  : sRGB (matches rawpy default)
```

**Gotcha 1 — the documented entry point does not run in Node.** The README claims Node support, but the
build is `-s ENVIRONMENT="web,worker"`
([`compileLibraw.sh`](https://github.com/ybouane/LibRaw-Wasm/blob/main/compileLibraw.sh)) and
[`index.js`](https://github.com/ybouane/LibRaw-Wasm/blob/main/index.js) constructs a browser
`new Worker(new URL('./worker.js', import.meta.url), {type:"module"})`. Node has no global `Worker`.
Measured:

```
node v24.14.1 darwin arm64
typeof globalThis.Worker: undefined
CONSTRUCT FAILED: ReferenceError Worker is not defined
```

**Workaround (measured, works):** skip the wrapper and drive the Emscripten `MODULARIZE`/`EXPORT_ES6`
factory directly, supplying the wasm bytes yourself so the fetch path is never taken:

```js
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const factory = (await import('libraw-wasm/dist/libraw.js')).default;
const wasmBinary = new Uint8Array(await readFile(require.resolve('libraw-wasm/dist/libraw.wasm')));

const Module = await factory({ wasmBinary });   // ~6ms, once per process
const inst = new Module.LibRaw();
try {
  await inst.open(buf, { useCameraWb: true, halfSize: true });
  const img = await inst.imageData();           // { width, height, bits, colors, data: Uint8Array }
} finally {
  inst.delete();                                // ← MANDATORY, see gotcha 2
}
```

This yields `Module.LibRaw` with `open`, `metadata`, `imageData`, `rawImageData`, `thumbnailData`.
That is ~10 lines of shim, no build step, no native compilation — the package is pure WASM with
**zero runtime dependencies**, so arm64 support is automatic.

**Gotcha 2 — you must call `inst.delete()` or the process dies after ~14 images.** The Embind-owned C++
object is never freed by GC. Measured, one reused `Module`, 7 files × rounds:

| | without `inst.delete()` | with `inst.delete()` |
|---|---|---|
| after 7 decodes | ok, rss 1575 MB | ok, rss 832 MB |
| after 14 decodes | ok, rss 2568 MB | ok, rss 835 MB |
| after 21 decodes | **all decodes fail**, rss 2703 MB | ok, rss 834 MB |
| after 42 decodes | — | ok, rss 880 MB, **0 failures** |

The wasm heap is `ALLOW_MEMORY_GROWTH=1` with a 2 GB ceiling and never shrinks. With `delete()`, RSS is flat
and mean decode time actually *improves* (365 → 304 ms) as the heap warms. **For a 43k-image batch this is
the difference between working and not working.** Note this is invisible if you use the documented
wrapper, whose `dispose()` tears down the whole worker.

### 1.4 Measured format coverage and pixel parity vs rawpy

Same file, same options, `rawpy 0.26.1`/LibRaw 0.22.0 vs `libraw-wasm` 1.6.0/LibRaw 0.22.1, half-size +
camera WB, byte-for-byte diff of the RGB8 buffer:

| Format | Sample | JS result | Python result | Byte diff | Max Δ |
|---|---|---|---|---|---|
| `.arw` | Sony (LibRaw-Wasm example) | 3120×2084, 182 ms | 3120×2084, 125 ms | 0.251 % | **1** |
| `.cr2` | Canon EOS 50D | 2385×1588, 282 ms | 2385×1588, 209 ms | 0.117 % | **1** |
| `.nef` | Nikon D850 14-bit | 4144×2760, 847 ms | 4144×2760, 508 ms | 0.275 % | **1** |
| `.dng` | Leica Q2 | 4196×2816, 656 ms | 4196×2816, 408 ms | 0.307 % | **1** |
| `.rw2` | Panasonic DC-G9 | 5201×3897, 475 ms | 5201×3897, 453 ms | 0.116 % | **1** |
| `.raf` | Fujifilm X-T3 | 3123×2085, 130 ms | 3123×2085, 81 ms | 0.255 % | **1** |
| `.cr3` | **Canon EOS R5** | 4095×2731, 642 ms | 4096×2732, 369 ms | **dimension mismatch (−1 px each axis)** | — |
| `.sr2` | Sony DSC-R1 | 1962×1304, 44 ms | 1963×1304, 34 ms | **dimension mismatch (−1 px width)** | — |
| `.orf` | Olympus E-M1 II | 2620×1956, 481 ms | 2620×1956, 296 ms | **94.6 %** | **220** |
| `.srw` | Samsung NX1 | 3248×2168, 423 ms | 3248×2168, 394 ms | **66.7 %** | **99** |
| `.x3f` | Sigma sd Quattro | **FAIL** | 5446×3624, 653 ms | — | — |

**Canon CR3 works.** That was the format most at risk and it decodes fine — LibRaw has native CR3 support
and 0.22 explicitly lists Canon EOS R5-class bodies
([Changelog](https://github.com/LibRaw/LibRaw/blob/master/Changelog.txt)).

**The good news:** on 6 of 11 formats the WASM output is effectively bit-identical to rawpy — only ~0.1–0.3 %
of bytes differ and **never by more than ±1**, which is 8-bit rounding, attributable to the build's
`-ffast-math -msimd128` flags.

**The bad news, in three parts:**

1. **ORF and SRW diverge materially.** Not a spatial shift and not a channel permutation (measured: best
   shift is dy=0 dx=0; all channel permutations are worse). Correlation is 0.9918 (ORF) / 0.9981 (SRW) with a
   linear fit of `js ≈ 1.020·py − 8.23` — i.e. a real tonal/WB difference, not noise. Disabling
   auto-brightness on both sides shrinks it (ORF max Δ 220 → 47, mean 5.66 → 1.33) but does **not** remove
   it, so auto-bright is an amplifier, not the cause.
2. **CR3 and SR2 come out one pixel smaller on each axis**, so any downstream hash or embedding sees a
   different image even before pixel values are considered.
3. **X3F (Sigma Foveon) fails outright** in the WASM build while rawpy handles it (rawpy: 5446×3624 in
   653 ms). The thrown value is an unconverted C++ exception, so the error message is literally
   `[object Object]` — expect poor diagnostics.

### 1.4.1 Root-causing the divergence (two hypotheses tested and killed)

**Hypothesis A — LibRaw version skew (0.22.0 vs 0.22.1). REFUTED.** This was the obvious explanation:
the `0.22.0...0.22.1` [compare](https://github.com/LibRaw/LibRaw/compare/0.22.0...0.22.1) contains
*"Check real color count against filters; do not pass really 4-color images to fbdd or advanced demosaic"*,
*"Check for correct bayer pattern, pass incorect ones to vng_interpolate"* and *"X3F decoder: implemented
hard single allocation limit via LIBRAW_X3F_ALLOC_LIMIT_MB"* — seemingly a direct match for all three
symptoms. And rawpy **v0.27.0** (2026-05-07) *"Update to LibRaw 0.22.1"*
([release notes](https://github.com/letmaik/rawpy/releases)), so the versions can be aligned.

So I aligned them: installed `rawpy==0.27.1` in a scratch venv (verified `rawpy.libraw_version → (0, 22, 1)`,
matching the wasm's pin exactly) and re-ran the whole matrix. **The results were byte-for-byte identical to
the 0.22.0 run** — ORF still 94.6077 % / max 220 / mean 5.65972, SRW still 66.7240 % / max 99, CR3 and SR2
still off by one pixel, X3F still failing in JS and still succeeding in Python. Not one number moved.

**Upgrading rawpy does not fix this.** The cause is in the WASM build, not the LibRaw version.

**Hypothesis B — different demosaic algorithm. REFUTED, and informative.** Forcing `userQual`/
`demosaic_algorithm` to 0 (linear) and 3 (AHD) on both sides gave *identical* diffs at both settings
(ORF 76.8120 % / max 47 / mean 1.33223 at **both** qual 0 and qual 3). That is expected once you notice
that **`half_size=True` bypasses interpolation entirely** — it 2×2-bins the Bayer quads — so the demosaic
is not in the code path at all.

**Which localises the fault to the raw unpack / black-level / `scale_colors()` stage.** Supporting
evidence: for this Olympus file rawpy reports `black_level_per_channel: [255, 255, 255, 255]` against
`white_level: 4095` — a 6.2 % black pedestal — while `libraw-wasm`'s metadata surface reports only
`black = 0` and does not expose `cblack[]` at all. Olympus and Samsung are also exactly the two makers
whose decoders were rewritten in LibRaw 0.22 (*"New implementation for Samsung V3 decoder (NX1, NX500,
etc)"* and the new OM System decoder that *"supports old (12-bit) Olympus/OM-System files too"*, per the
[Changelog](https://github.com/LibRaw/LibRaw/blob/master/Changelog.txt)).

The most plausible remaining cause is the build's own numerics: `compileLibraw.sh` compiles LibRaw with
`-O3 -flto -ffast-math -msimd128` and `--enable-openmp`
([compileLibraw.sh](https://github.com/ybouane/LibRaw-Wasm/blob/main/compileLibraw.sh)). **`-ffast-math`
licenses the compiler to break IEEE semantics**, which is a fine trade for ±1 rounding but not for a
float-heavy scaling stage. A secondary suspect: the repo **commits the built static libs** (`libs/libraw.a`)
and `compileLibraw.sh` skips rebuilding them unless `FORCE_LIBS=1`, so the shipped `libraw.wasm` may not
correspond to the pinned source. The binary carries no version string (checked — `strings` on
`libraw.wasm` yields no LibRaw version), so this is not verifiable from the outside.

**Actionable:** the one experiment left worth running is to fork and rebuild with `-ffast-math` removed
and `FORCE_LIBS=1`. That is a one-line change to a script the repo already ships, and if it collapses the
ORF/SRW gap it converts item 1 from "viable with caveats" to "viable". It will not fix X3F.

This instability is a **known, open, unanswered issue upstream**:
[ybouane/LibRaw-Wasm#12](https://github.com/ybouane/LibRaw-Wasm/issues/12), *"NEF decoding produces
different pixel values after latest WASM update"* (opened 2026-02-24, still open, no maintainer reply),
reports a B-channel shift of −35/255 between two `libraw.wasm` builds of the same package. **Pin the exact
`libraw-wasm` version and treat any bump as a re-hash/re-embed event.**

Why it matters here specifically: `image_prep.convert_raw_to_jpg` feeds the decoded RGB into the JPEG that
the whash and CLIP stages consume. So a mean Δ of 5.7/255 on Olympus files will produce a **different
`whash` bit-string and a slightly rotated CLIP vector** for those images. The RAW decoder is upstream of
both other items in this document.

### 1.5 The embedded-preview shortcut (measured)

`libraw-wasm` exposes `thumbnailData()`, which pulls the camera's embedded JPEG with no demosaic:

| Format | Preview size | Time |
|---|---|---|
| `.cr3` | **8192×5464** | 11 ms |
| `.dng` | **8368×5584** | 9 ms |
| `.nef` | **8256×5504** | 7 ms |
| `.srw` | 6480×4320 | 4 ms |
| `.arw` | 6192×4128 | 4 ms |
| `.cr2` | 4752×3168 | 4 ms |
| `.raf` | 4416×2944 | 6 ms |
| `.orf` | 3200×2400 | 3 ms |
| `.rw2` | **1920×1440** | 12 ms |
| `.sr2` | **640×424** | 3 ms |
| `.x3f` | FAIL | — |

**~30–100× faster than demosaicing** and on modern formats the preview is full sensor resolution. But it is
**not uniform**: Panasonic RW2 tops out at 1920×1440 and older Sony SR2 at 640×424. As a *substitute* for
demosaicing it would silently change the input resolution for some cameras, and the preview carries the
camera's own JPEG rendering (its tone curve and sharpening), not LibRaw's — so hashes and embeddings would
not be comparable with the existing corpus. **Good as a fast path / thumbnail source; not a parity substitute.**

### 1.6 `exifr` and `exiftool-vendored` for previews: ruled out

The task asked whether these can pull the full-size embedded preview. Measured with `exifr` 7.1.3
(latest; **last published 2021-08-05**, [npm](https://www.npmjs.com/package/exifr)):

```
test.cr3  exifr.thumbnail ERR Unknown file format
test.raf  exifr.thumbnail ERR Unknown file format
test.x3f  exifr.thumbnail ERR Unknown file format
test.srw  exifr.thumbnail ERR Offset is outside the bounds of the DataView
test.nef  exifr.thumbnail = null
test.orf  exifr.thumbnail = null
test.rw2  exifr.thumbnail = null
test.dng  exifr.thumbnail = null
test.cr2  exifr.thumbnail 160x120
test.sr2  exifr.thumbnail 160x120
sony.ARW  exifr.thumbnail 160x120
```

`exifr` returns only the **160×120 EXIF thumbnail** where it works at all, and errors outright on CR3, RAF,
X3F and SRW. Not usable.

[`exiftool-vendored`](https://www.npmjs.com/package/exiftool-vendored) 37.2.0 (2026-08-08, actively
maintained) *does* have the right API — `extractPreview()` and `extractJpgFromRaw()`
([README](https://github.com/photostructure/exiftool-vendored.js/blob/main/README.md)) — but it works by
spawning the **vendored Perl ExifTool binary** as a child process. That satisfies "no Python" only on a
technicality: it trades a Python dependency for a Perl one plus per-file process overhead. And it is
redundant, since `libraw-wasm`'s in-process `thumbnailData()` already does this in 3–12 ms.

### 1.7 `@imagemagick/magick-wasm` as fallback (measured)

Better than expected, and worth recording: the 0.0.43 wasm **does** ship a libraw delegate.

```
IM ImageMagick 7.1.2-30 Q8 wasm32 344e9056f:20260823
delegates: bzlib freetype heic jng jp2 jpeg jxl lcms lqr openexr png raw tiff webp xml zlib
declared RAW formats: ARW,CR2,CR3,CRW,DCRAW,DNG,NEF,ORF,RAF,RAW,RW2,SR2,SRW,X3F
```

Two operational notes from testing. First, the package ships `dist/x86/magick.wasm` and
`dist/x64/magick.wasm`; the **x64 (memory64) build fails to instantiate on Node 24**
(`LinkError: Import #122 "a" "ob": function import requires a callable`) — use the x86 build. Second, you
must force the format via `MagickReadSettings.format`, or CR2/ARW get misrouted to the TIFF coder and fail
with `TIFF directory is missing required "ImageLength" field`.

With the format forced, 10 of 11 formats decode (X3F still fails: `NoDecodeDelegateForThisImageFormat`).
But it is a poor parity target:

| Format | magick-wasm | libraw-wasm | Ratio |
|---|---|---|---|
| `.cr3` | 8191×5463, 2774 ms | 4095×2731, 642 ms | 4.3× slower |
| `.raf` | 6246×4170, 8411 ms | 3123×2085, 130 ms | **65× slower** |
| `.nef` | 8288×5520, 2222 ms | 4144×2760, 847 ms | 2.6× slower |
| `.rw2` | 10402×7794, 2998 ms | 5201×3897, 475 ms | 6.3× slower |

`setDefine('dng', 'half-size', 'true')` was **silently ignored** — every output came back full size, i.e. 4×
the pixels. Combined with a `Q8` quantum build and no exposed camera-WB control that matches LibRaw's
`-w` semantics, this is a *fallback for coverage*, not a parity path.

### 1.8 Throughput

Measured, single-threaded, one warm `Module`, 7 mixed-format files × 6 rounds, with `delete()`:
**304 ms/file mean** at half-size, stable RSS ~880 MB. For 43,451 images that is **≈ 3.7 hours
single-threaded**; across 8 `node:worker_threads` workers, ≈ 30 minutes. Python rawpy measured
~250 ms/file on the same files, so the WASM penalty is roughly **1.2–1.7×** — acceptable.
Module init is ~6 ms, so per-worker startup is free.

### 1.9 Verdict — item 1

> **Viable with caveats.** Primary choice: **`libraw-wasm` 1.6.0**, driven through its raw Emscripten
> factory with an explicit `wasmBinary` and a mandatory `inst.delete()` per image. Fallback:
> **`@imagemagick/magick-wasm` 0.0.43** (x86 wasm, forced format) for coverage, accepting 3–65× slower
> full-resolution decodes. `sharp`, `exifr`, `dcraw`, `node-libraw` and the Rust crates are all ruled out
> above.
>
> Caveats that must be designed around: (a) **`.x3f` does not decode at all** — keep a Python/exiftool
> escape hatch or drop the format; (b) **Olympus `.orf` and Samsung `.srw` do not match rawpy** (mean Δ
> 5.7 and 3.0 of 255) and **CR3/SR2 differ by one pixel per axis**, so those images need re-hashing and
> re-embedding rather than assuming continuity; (c) pin the exact package version — upstream
> [issue #12](https://github.com/ybouane/LibRaw-Wasm/issues/12) documents pixel output changing between
> builds of the same package, with no maintainer response.
>
> **Aligning LibRaw versions does not help** — that was the obvious fix and it was tested and refuted
> (§1.4.1): with rawpy 0.27.1 on LibRaw 0.22.1, matching the wasm's pin exactly, not one number moved. The
> one experiment still worth running is a fork rebuilt **without `-ffast-math`** and with `FORCE_LIBS=1`,
> a one-line change to a script the repo already ships. If that closes the ORF/SRW gap, item 1 becomes
> plainly **viable**. It will not fix `.x3f`.

---

## 2. CLIP ViT-B/32 embeddings

Target: new vectors must be cosine-comparable with **43,451 stored 512-dim L2-normalized** embeddings
produced by `SentenceTransformer("clip-ViT-B-32").encode(..., normalize_embeddings=True)`.

### 2.1 Headline result

**The ONNX model is numerically faithful. The image preprocessing is not.** Measured on this machine
(macOS arm64, Node v24.14.1), six real photographs decoded from the RAW files in §1 and saved as
quality-95 JPEG, `@huggingface/transformers` 4.2.0 with `Xenova/clip-vit-base-patch32` at **fp32**, versus
the project's own `clip_embedding_service` code path:

| Image | Pixels | cosine vs Python | L2 distance |
|---|---|---|---|
| `photo_canon_r5.jpg` | 4095×2731 | 0.968431 | 0.251 |
| `photo_fuji_xt3.jpg` | 3123×2085 | 0.964299 | 0.267 |
| `photo_sony.jpg` | 3120×2084 | 0.947584 | 0.324 |
| `photo_leica_q2.jpg` | 4196×2816 | 0.930840 | 0.372 |
| `photo_nikon_d850.jpg` | 4144×2760 | 0.926095 | 0.384 |
| `photo_olympus.jpg` | 2620×1956 | 0.921986 | 0.395 |
| **min / mean / max** | | **0.9220 / 0.9432 / 0.9684** | |

For scale: the inter-image cosine among these six *unrelated* photographs is 0.3231–0.6567. So an image
would be only **0.94 similar to itself** across the Python→Node boundary. That is fatal for near-duplicate
work, where genuine near-dupes sit at 0.95+ — **the self-similarity floor lands inside the
near-duplicate band.** This is not a tolerance question; it is a correctness question.

A second, independent run over 34 images (7 real photos as both PNG and JPEG, plus 20 synthetic covering
6000×4000 and aspect ratios 1:1 to 1:10) put the range at **0.796–1.000**, with the error tracking the
downscale factor exactly as aliasing predicts:

| Input size | cosine |
|---|---|
| 224×224 (no resize needed) | **1.000000** |
| 640×480 | 0.967 |
| 1920×1080 | 0.920 |
| 6000×4000 | **0.823** |
| 4000×6000 | **0.796** |

Full-resolution camera files land in the worst bucket. Quantization is *not* the cause — q8 scored
0.791–0.926, barely different from fp32's 0.796–1.000.

**But feeding Python's own `pixel_values` tensor into the Node fp32 ONNX graph gives cosine
= 1.000000 (L2 ≈ 2e-6) on every image.** The transformer weights and ONNX runtime are exact. Every bit of
divergence is preprocessing.

### 2.2 Why: `sharp.affine`, not Pillow's resize

Both `preprocessor_config.json` files agree on the intent.
[`openai/clip-vit-base-patch32`](https://huggingface.co/openai/clip-vit-base-patch32/raw/main/preprocessor_config.json):
`size: 224`, `crop_size: 224`, `resample: 3`, mean `[0.48145466, 0.4578275, 0.40821073]`, std
`[0.26862954, 0.26130258, 0.27577711]`.
[`Xenova/clip-vit-base-patch32`](https://huggingface.co/Xenova/clip-vit-base-patch32/raw/main/preprocessor_config.json)
adds the modern shapes (`size: {shortest_edge: 224}`, `crop_size: {height: 224, width: 224}`,
`rescale_factor: 0.00392156862745098`, `do_convert_rgb: true`) with the **same `resample: 3` (bicubic)**
and the same mean/std. Verified at runtime — transformers.js reports exactly these values.

The problem is the implementation. In Node, `RawImage.resize`
([`src/utils/image.js`](https://github.com/huggingface/transformers.js/blob/main/packages/transformers/src/utils/image.js))
calls:

```js
sharp.affine([h / H, 0, 0, w / W], { interpolator: 'bicubic' })
// with the source comment: "This matches how the python Pillow library does it."
```

**That comment is wrong.** Bicubic is honoured as a *name* but silently downgraded in *algorithm class*:
[Pillow's filter docs](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters) state that
`resize` with BICUBIC uses "all pixels that may contribute" — a scale-adaptive, antialiased convolution —
whereas a fixed 4×4 kernel is what `transform`/affine does. And
[libvips itself uses `vips_affine` only for upsizing](https://www.libvips.org/API/current/method.Image.resize.html);
transformers.js uses it for every scale. That is precisely why the error grows with the downscale factor
and vanishes at 224×224. (The browser path ignores `resample` altogether — `// TODO use resample in browser
environment`. Only `resample: 1` reaches sharp's filtered `resize()`.)

Target *dimensions* do match Python; the pixel values do not. Measured, same image, first 8 `pixel_values`:

```
Python: [-0.682782, -0.775774, -0.775774, -0.653585, -0.463806, -0.098845,  0.222320,  0.222320]
Node:   [-0.493003, -0.638987, -0.711979, -0.711979, -0.609790, -0.084247,  0.470494,  0.645675]
```

**This is the same root cause as item 3.** PIL's resampling versus libvips/sharp broke whash (§3.4) and it
breaks CLIP here. One defect, two symptoms.

### 2.3 Upstream status: known, acknowledged, never fixed

- [#595](https://github.com/huggingface/transformers.js/issues/595) "CLIP Embeddings on JS and Python side
  are not equal" (closed 2024-02-23). Maintainer: *"due to slight differences in the image resizing
  algorithms used under the hood (Pillow in python; sharp in javascript)."*
- [#482](https://github.com/huggingface/transformers.js/issues/482) (closed) — the fullest admission:
  *"Bicubic interpolation should be used, but there do indeed to be slight differences… **If we can achieve
  a 100% match with PIL, then that would solve all these issues.** … this didn't matter for the example
  image I used above since it's already 224x224."* That last clause independently corroborates the
  224×224 → 1.000000 result above.
- [#816](https://github.com/huggingface/transformers.js/issues/816) has published numbers matching ours:
  torch↔onnx **0.99999999997**, torch↔js **0.7656**. Redirected to
  [onnxruntime#21275](https://github.com/microsoft/onnxruntime/issues/21275), closed stale 2025-06-07,
  never attributed.
- [#426](https://github.com/huggingface/transformers.js/issues/426) sets the only published tolerance bar:
  *"any differences under 1e-5 can be safely ignored."* **0.92–0.97 is four to five orders of magnitude
  outside it.**
- Origin: commit [`4a282bf`](https://github.com/huggingface/transformers.js/commit/4a282bf632151301bbca019bc8e41db8e41a639d)
  (2023-05-02, no PR review) swapped `resize({kernel:'cubic'})` → `affine()`, resting on one community
  comment in [sharp#3642](https://github.com/lovell/sharp/issues/3642) about a *no-argument* Pillow resize.
  The same commit rewrote golden test values (tiger score 0.805 → 0.608).
  [PR #1101](https://github.com/huggingface/transformers.js/pull/1101), a native resampler, was closed
  unmerged after 15 months.
- **The official docs claim the opposite, with no caveat.** The
  [README](https://github.com/huggingface/transformers.js/blob/main/README.md) states Transformers.js is
  *"designed to be functionally equivalent to … transformers."* There is no open issue tracking this and
  no doc mention of `parity`, `Pillow`, `resample` or `antialias`. **Do not take the equivalence claim at
  face value.**

### 2.4 Library and weight facts

**`@huggingface/transformers`** — latest **4.2.0**, published 2026-04-22
([registry](https://registry.npmjs.org/@huggingface/transformers)); GitHub release 2026-04-23. v3 ended at
3.8.1 (2025-12-02), so **v4 is the only current line**. 16.3k stars, 274 open issues, 14 commits since
4.2.0 (last 2026-08-29) — alive but slowing. Dependencies: `onnxruntime-node` **1.24.3** (exact pin),
`onnxruntime-web`, **`sharp` ^0.34.5**. No `engines` field. **macOS arm64 + Node 24 works** — verified by
running it, with prebuilt `libonnxruntime.1.24.3.dylib` and `onnxruntime_binding.node` under
`bin/napi-v6/darwin/arm64/` plus `@img/sharp-darwin-arm64`.

**Weights.** [`Xenova/clip-vit-base-patch32`](https://huggingface.co/api/models/Xenova/clip-vit-base-patch32)
ships 23 ONNX files: `model{,_fp16,_quantized,_uint8,_q4,_q4f16,_bnb4}.onnx` plus `text_model_*` and
`vision_model_*` variants. **`vision_model.onnx` is 335.4 MB fp32** — available off the shelf, no re-export.

**Default dtype in Node is fp32, not quantized.** `src/utils/devices.js` sets
`DEFAULT_DEVICE = apis.IS_NODE_ENV ? 'cpu' : 'wasm'`, and `src/utils/dtypes.js` sets
`DEFAULT_DEVICE_DTYPE = fp32` with the mapping overriding **only** `wasm → q8`. Confirmed empirically:
omitting `dtype` gave bit-identical output to explicit `fp32` and downloaded the 335 MB
`vision_model.onnx`. **But this is undocumented for Node** — the
[dtypes guide](https://huggingface.co/docs/transformers.js/guides/dtypes) only discusses fp32-for-WebGPU
and q8-for-WASM. **Pass `{ dtype: 'fp32' }` explicitly anyway.**

**`onnxruntime-node`** — latest **1.29.0**, published 2026-08-24. Prebuilt **darwin-arm64** binaries
confirmed (`libonnxruntime.1.29.0.dylib`, 43.9 MB) and `InferenceSession.create` succeeds on the fp32
vision graph. Using it directly is viable; transformers.js is then only needed for download plumbing.

**The Python reference is a thin wrapper.**
[`sentence-transformers/clip-ViT-B-32` `modules.json`](https://huggingface.co/sentence-transformers/clip-ViT-B-32/raw/main/modules.json)
contains exactly one module, `sentence_transformers.models.CLIPModel`, which calls
`get_image_features`. **There is no `Normalize` module** — the L2 normalization comes solely from
`normalize_embeddings=True` at `clip_embedding_service.py:34`. Note also that under the installed
transformers the processor resolves to `CLIPImageProcessorPil` (PIL BICUBIC, `default_to_square=False`),
not the torchvision "fast" processor; **if that ever flips, the reference itself moves.**

### 2.5 What exact parity requires

Porting Pillow's `ImagingResample` bicubic to JS (~90 lines: `PRECISION_BITS = 22` fixed-point
coefficients, horizontal pass → uint8 intermediate → vertical pass — the same machinery item 3 needs)
produced output **pixel-identical to PIL: 100.0000 % exact bytes, maxdiff 0** on 7 real images, and
**1 − cos < 1.1e-11 across all 34 test images**, including 6000×4000 downscales and 1:10 aspect ratios.
Grayscale JPEG, palette PNG and RGBA PNG all pass.

Three non-obvious gotchas, each worth real accuracy:

1. **HF `center_crop` floors, it does not round**: `(orig - crop) // 2`
   ([image_transforms.py](https://github.com/huggingface/transformers/blob/main/src/transformers/image_transforms.py)).
   Using `Math.round` cost 0.9976 on odd deltas.
2. **`sharp` applies embedded ICC profiles; PIL does not.** One test image with an ICC profile had 95 % of
   bytes differ, maxdiff 79/255, cosine 0.9976. Fix: `sharp(input, { ignoreIcc: true })`
   ([documented option](https://github.com/lovell/sharp/blob/main/docs/src/content/docs/api-constructor.md)).
3. Folding the centre crop into the resize box is mathematically identical for a uniform scale and **2×
   faster** (100 → 33 ms/img).

Also: neither PIL nor sharp auto-applies EXIF orientation by default, so they agree — **do not "fix" this
by enabling `autoOrient`.**

### 2.6 Performance

Measured, batch 8: Python baseline (torch 2.11 on MPS) **54.1 ms/img** → 39 min for 43,451. Node with the
fused Pillow-exact pipeline **56.3 ms/img** → **41 min**, of which inference alone is 8.1 ms/img. So Node
reaches **~96 % of Python-on-MPS** on JPEG input — preprocessing, not inference, dominates both.

macOS acceleration is a dead end but a *safe* one: CoreML and WebGPU execution providers both load and run
on darwin-arm64 ([`js/node/README.md`](https://github.com/microsoft/onnxruntime/blob/v1.24.3/js/node/README.md)
confirms macOS arm64 support; CoreML since v1.17.0, WebGPU per the
[1.22.0 release notes](https://github.com/microsoft/onnxruntime/releases/tag/v1.22.0)). All three gave
cosine 1.000000 against each other, but **no speedup**: cpu 12.5, coreml 14.8, webgpu 15.1 ms/img. Don't
bother. (The [onnxruntime.ai Node page](https://onnxruntime.ai/docs/get-started/with-javascript/node.html)
is stale and omits both; cite `js/node/README.md`. Also `device: 'gpu'` will not select CoreML — pass
`'coreml'` explicitly.) No official transformers.js CPU throughput benchmark exists;
[issue #86](https://github.com/huggingface/transformers.js/issues/86) has requested one since 2023-04-13,
unanswered.

### 2.7 Verdict — item 2

> **Viable with caveats — but *only* if you replace transformers.js's image preprocessing.** Primary
> choice: **`onnxruntime-node` (1.29.0) running `Xenova/clip-vit-base-patch32`'s fp32 `vision_model.onnx`,
> with a hand-rolled Pillow-exact bicubic resize + floor centre-crop + CLIP mean/std**, using `sharp` only
> to decode to raw RGB with `ignoreIcc: true`. Fallback: `@huggingface/transformers` 4.2.0 with
> `{ dtype: 'fp32' }` **and its `RawImage.resize` bypassed** — convenient for model download and tokenizer
> plumbing, never for pixels.
>
> **Using transformers.js as shipped is not viable here**: measured cosine against the existing corpus is
> 0.92–0.97 on real camera-sized photos (0.796 worst case), which is inside the near-duplicate band, four
> to five orders of magnitude outside the project's own stated 1e-5 tolerance, and caused by a defect
> upstream has acknowledged since 2023 and never fixed. Quantization is a red herring — Node already
> defaults to fp32; the resize is the whole problem.
>
> Remaining caveats: **CMYK JPEGs break parity** (cosine 0.973 — PIL's naive CMYK→RGB differs from
> libvips' colour-managed conversion); detect and route those to Python or normalize them first. And the
> parity harness has not been run against the actual 43,451 stored vectors — **before migrating, re-embed
> a few hundred real cached JPEGs and diff against the stored blobs**, since the stored vectors also carry
> whatever the RAW decoder of §1 produced at the time.

---

## 3. Wavelet perceptual hash

Target: `imagehash.whash(img)` as called at `hasher.py:38` — **all defaults**, i.e. `hash_size=8`,
`mode='haar'`, `remove_max_haar_ll=True`. Installed locally: **imagehash 4.3.2, pywt 1.8.0, pillow 12.2.0**
(measured). imagehash 4.3.2 was released 2025-02-01 ([PyPI](https://pypi.org/pypi/ImageHash/json)).

### 3.1 What `whash` actually does

From [`imagehash/__init__.py`](https://github.com/JohannesBuchner/imagehash/blob/master/imagehash/__init__.py)
(default branch is `master`, not `main`):

```python
def whash(image, hash_size=8, image_scale=None, mode='haar', remove_max_haar_ll=True):
	import pywt
	if image_scale is not None:
		assert image_scale & (image_scale - 1) == 0, 'image_scale is not power of 2'
	else:
		image_natural_scale = 2**int(numpy.log2(min(image.size)))
		image_scale = max(image_natural_scale, hash_size)
	ll_max_level = int(numpy.log2(image_scale))
	level = int(numpy.log2(hash_size))
	dwt_level = ll_max_level - level
	image = image.convert('L').resize((image_scale, image_scale), ANTIALIAS)
	pixels = numpy.asarray(image) / 255.
	if remove_max_haar_ll:
		coeffs = pywt.wavedec2(pixels, 'haar', level=ll_max_level)
		coeffs = list(coeffs); coeffs[0] *= 0
		pixels = pywt.waverec2(coeffs, 'haar')
	coeffs = pywt.wavedec2(pixels, mode, level=dwt_level)
	dwt_low = coeffs[0]
	med = numpy.median(dwt_low)
	diff = dwt_low > med
	return ImageHash(diff)
```

Notes that matter for a port:

- **`ANTIALIAS` is LANCZOS**, not a box or bilinear filter (lines 38–43 alias
  `Image.Resampling.LANCZOS`). The resize is to a **square**, `(image_scale, image_scale)` — aspect ratio
  is *not* preserved.
- Order is **greyscale first, then resize**.
- For a 12 MP photo (6000×4000): `min=4000`, `int(log2(4000)) = 11` → `image_scale = 2048`,
  `ll_max_level = 11`, `level = 3`, `dwt_level = 8`. So the image is resized to **2048×2048** and taken 8
  Haar levels down to an 8×8 LL block.
- **`remove_max_haar_ll=True` is arithmetically a no-op.** Because the image was just resized to exactly
  `2^ll_max_level` square, `wavedec2(..., level=ll_max_level)` makes `coeffs[0]` a **1×1** scalar; zeroing it
  and reconstructing is identical to subtracting the global mean (verified: max deviation 5.55e-16). A
  constant pixel offset shifts all 64 LL coefficients *and* their median by the same amount, so `> med` is
  invariant (verified: ptp 1.42e-14). Its only real effect is ~1e-16 of float dust — which is a
  bit-exactness *liability*, not an optimisation (see §3.4).
- **Threshold** is `numpy.median` of the 64 LL coefficients — for even counts, the **mean of the two middle
  sorted values** — then strict `>`, so **ties resolve to `False`**. Bits pack row-major (C-order),
  **MSB first**, into 16 hex chars. `ImageHash.__sub__` is plain Hamming distance.

### 3.2 pywt Haar semantics a port must match

`'haar'` is an alias for `db1` ([wavelets.c](https://github.com/PyWavelets/pywt/blob/main/pywt/_extensions/c/wavelets.c)),
with the single coefficient `7.0710678118654752440e-01` repeated
([wavelets_coeffs.template.h](https://github.com/PyWavelets/pywt/blob/main/pywt/_extensions/c/wavelets_coeffs.template.h)).
Measured against the installed pywt 1.8.0:

```
dec_lo [0.7071067811865476, 0.7071067811865476]
dec_hi [-0.7071067811865476, 0.7071067811865476]
```

- **Sign convention** is even-minus-odd: `cD[k] = (x[2k] − x[2k+1])/√2`. Irrelevant for whash — the forward
  pass only recurses on `cA`, and the one place details are used (`waverec2`) is an exact inverse.
- **Numerical trap:** use `Math.SQRT1_2` / `Math.sqrt(0.5)`, **not** `1 / Math.sqrt(2)`, which is one ULP
  lower (verified in Python: `C == math.sqrt(0.5)` is `True`, `C == 1/math.sqrt(2)` is `False`).
- **Default extension mode is `'symmetric'`**
  ([2D DWT docs](https://pywavelets.readthedocs.io/en/latest/ref/2d-dwt-and-idwt.html)) — **but it is
  provably irrelevant here.** Output length is `(N + filter_len − 1) / 2` integer-divided
  ([common.c](https://github.com/PyWavelets/pywt/blob/main/pywt/_extensions/c/common.c)), which for
  `filter_len=2` and even `N` is exactly `N/2`, and the mode-specific boundary block in
  [convolution.template.c](https://github.com/PyWavelets/pywt/blob/main/pywt/_extensions/c/convolution.template.c)
  never executes for a length-2 filter. Since the input is a power of two at every level (2048 → 1024 → …
  → 8), **a JS port needs no padding logic at all.**
- **Layout:** `wavedec2` returns `[cAn, (cHn, cVn, cDn), …]`, and pywt's `cH` corresponds to axis 0 (what
  most literature calls LH). whash only ever reads `coeffs[0]`, so this naming trap only bites on the
  `waverec2` round-trip.

### 3.3 The JS/Rust ecosystem: nothing off-the-shelf is right

**`discrete-wavelets` is unusable on two counts.** v5.0.15, last published **2023-01-29**
([npm](https://www.npmjs.com/package/discrete-wavelets)). Its
[README](https://github.com/Symmetronic/discrete-wavelets) states outright: *"This library is no longer
actively maintained."* And — confirming the suspicion in the brief — **it is 1D only**: the entire public
API in [`src/wt.ts`](https://github.com/Symmetronic/discrete-wavelets/blob/main/src/wt.ts) is
`dwt, idwt, wavedec, waverec, energy, maxLevel, pad, Modes`. There is no `dwt2`/`wavedec2`.

**There is no maintained general-purpose 2D DWT library on npm.** `wasmlets` 0.0.6 (2025-01-30) is 1D only;
`omni-wave`, `dwt`, `webfcwt`, `frequencyjs` are CWT, 1D, or abandoned.

**No mainstream perceptual-hash package implements the wavelet hash** — each was checked against its source:

| Package | Version | Published | Algorithms actually implemented |
|---|---|---|---|
| `imghash` | 1.1.4 | 2026-04-25 | blockhash only |
| `image-hash` | 7.0.1 | 2025-11-13 | blockhash only |
| `sharp-phash` | 2.2.0 | 2024-10-31 | pHash-DCT only; thresholds on the **mean**, not median |
| `blockhash-core` | 0.1.0 | 2019-12-07 | blockhash only |
| `phash` | 0.0.5 | 2013-07-02 | pHash-DCT only (native libpHash) |
| `jimp` / `@jimp/plugin-hash` | 1.6.1 | 2026-04-07 | pHash-DCT only; reads the *blue* channel as luma |

**Rust is a dead end for this specifically.** [`image_hasher` 3.1.1](https://docs.rs/image_hasher/3.1.1/image_hasher/enum.HashAlg.html)
(2026-02-21, the live qarmin fork) exposes `HashAlg = { Mean, Median, Gradient, VertGradient,
DoubleGradient, Blockhash }` — **no wavelet variant**, and no Haar source file at any version.
[`img_hash` 3.2.0](https://docs.rs/img_hash/3.2.0/img_hash/enum.HashAlg.html) (2021-05-04) is unmaintained
with the same list. `imgdd` advertises "wHash" but runs a **1D** transform over a flattened 8×8 and
thresholds reconstructed pixels — a different hash entirely.

**Two npm packages do implement whash**, both very new and both single-author:

- [`rosetta-squint-hash`](https://www.npmjs.com/package/rosetta-squint-hash) 1.0.0 (2026-05-26,
  BSD-2-Clause, ESM-only, dep `pngjs`), a self-described byte-exact Rust-derived port of imagehash 4.3.2
  exporting `whashHaar`. Its source independently carries the `Math.sqrt(0.5)` warning above, which is a
  good sign for its internals — but **zero GitHub stars, one author, one release**.
- [`browser-image-hash`](https://www.npmjs.com/package/browser-image-hash) 0.0.7 (2026-03-16) has a
  correct-looking `WaveletHashGenerator`, but its README only claims to match imagehash *"as much as
  possible"*, and it depends on **`wasm-imagemagick`, dead since 2020** (§1.1).

### 3.4 The DWT is trivial; the *resize* is the entire problem

This research built and validated a complete pure-JS port against real `imagehash.whash` 4.3.2 / pywt 1.8.0
over a 106-image corpus on this machine. Total size: **168 lines of plain JS**, no dependency beyond
`sharp` for image decoding. The split is not where you'd expect:

- **The 2D Haar DWT is ~12 lines.** Power-of-two input, no padding, no boundary logic, no library. The
  brief's hypothesis that reimplementation may be trivial is **confirmed — for the wavelet part.**
- **PIL-exact greyscale is 6 lines.**
- **PIL's Lanczos resize is ~110 lines**, and it is the whole difficulty.

**`sharp` cannot substitute for PIL's resize.** Its `kernel` defaults to `'lanczos3'`
([sharp resize docs](https://sharp.pixelplumbing.com/api-resize/)) which sounds like a match, but three
things compound: (a) `sharp().greyscale()` uses libvips `B_W`, not PIL's ITU-R 601-2 luma — measured max
difference **24 levels on 3.34 % of pixels**; (b) libvips `resize` does a shrink-then-reduce hybrid while
PIL always convolves at full resolution — measured combined difference to 512×512 was **max 28, mean 0.79,
7.22 % of pixels**; (c) PIL's 8-bit path is **fixed-point, not float**.

**Measured cost of the sharp shortcut: only 35/106 images matched (33 %)**, Hamming distances up to 22/64
with a mode of 4–6 bits. It saved 2.4× (37.7 vs 91.5 ms/image) and is unusable.

**Porting PIL faithfully does work, bit-exactly.** The spec is
[`Resample.c`](https://github.com/python-pillow/Pillow/blob/main/src/libImaging/Resample.c):
`LANCZOS = {lanczos_filter, 3.0}`; `precompute_coeffs` uses C `(int)` truncation (so `Math.trunc`, **not**
`Math.floor`); `PRECISION_BITS = 32 - 8 - 2 = 22`, with coefficients quantised to integers, an accumulator
biased by `1 << 21`, and `>> 22` with clamping to [0,255] **between** the horizontal and vertical passes.
`Image.resize`'s `reducing_gap` defaults to `None`, so there is no `reduce()` pre-pass
([Image.py](https://github.com/python-pillow/Pillow/blob/main/src/PIL/Image.py)). Greyscale is
`L24(rgb) = r*19595 + g*38470 + b*7471 + 0x8000` then `>> 16`
([Convert.c](https://github.com/python-pillow/Pillow/blob/main/src/libImaging/Convert.c)). Measured result
of the port against real PIL on a 1863×935 PNG and a 5184×3456 JPEG: `GREY exact: True maxdiff 0`,
`RESIZE exact: True maxdiff 0`. The fixed-point arithmetic is what makes this deterministic — 32-bit
intermediates (max ≈ 255·2²² ≈ 1.07e9) fit exactly in JS doubles.

### 3.5 The one genuinely unfixable gap: FMA and median ties

Tie handling is the real trap, and it is subtler than a `>` convention. Whether the two middle LL
coefficients are *exactly equal* is decided by 1-ULP dust from the `remove_max_haar_ll` round-trip — the
operation that is arithmetically a no-op.

pywt's kernel is `sum += filter[j] * input[i-j]`
([convolution.template.c](https://github.com/PyWavelets/pywt/blob/main/pywt/_extensions/c/convolution.template.c)),
and **the compiler contracts it into a fused multiply-add**. Measured against the installed pywt 1.8.0
over 20,000 random 2-sample Haar transforms, classifying each result by which arithmetic reproduces it
exactly:

```
{'plain': 16181, 'fma': 3819, 'sum_then_mul': 0, 'neither': 0}
```

**19 % of results are only reproducible with an FMA, and none are unexplained.** pywt's `meson.build` sets
no `-ffp-contract` flag, so this is the compiler default on a target where FMA is always available. JS has
no FMA primitive; emulating exactly-rounded double FMA via Dekker two-product transforms at every
accumulation across 4 subbands × 11 levels is possible but slow and gnarly.

**Corollary:** since x86-64 manylinux wheels build for the SSE2 baseline (no FMA to contract into), the
*Python* reference is likely **not bit-reproducible between macOS arm64 and Linux x86-64** for degenerate
images. "Bit-exact with imagehash" is therefore not a fully well-defined target. (Inference from the FMA
result, not directly tested — confirmable by running one flat-image whash in an x86 container.)

### 3.6 Measured accuracy of the port

| Content | n | exact | Hamming |
|---|---|---|---|
| random noise | 20 | **20** | 0 |
| smooth gradient | 20 | **20** | 0 |
| synthetic "photoish" | 20 | **20** | 0 |
| real screenshots + real EXIF JPEG | 8 | **8** | 0 |
| sky (gradient + sensor noise) | 6 | **6** | 0 |
| near-black void frames | 6 | 5 | one at 2 bits |
| flat + ±1 dither | 6 | 5 | one at 1 bit |
| **bit-constant flat regions** | 20 | **0** | 9–16 bits |
| **Overall** | 106 | 84 (79 %) | — |

**Excluding the pathological bit-constant class: 74/74 = 100 % exact.** `rosetta-squint-hash` scored
**identically — 68/88 on the first corpus, failing on exactly the same images** — so its byte-exactness
claim does not hold on degenerate input either, and the cause is not axis or operand order (an independent
Python emulation of pywt's non-FMA operation order also scored 68/88).

Otherwise the hash is very stable: flipping one source pixel by ±1 gave Hamming 0, and a resize differing
on 7 % of pixels still gave Hamming 0 — the 8×8 LL averages 64×64 blocks, so pixel noise washes out. The
failures are strictly a tie-breaking phenomenon.

**Direct relevance to this repo:** the failure population is *void / near-blank / clipped frames* — exactly
what the recent frame-substance work targets. Real sensor noise mostly saves you (sky and void JPEGs were
11/12), but genuinely clipped-black frames and synthetic images land in the 0 % bucket.

### 3.7 Performance

Single-threaded, macOS arm64, Node 24 (measured): **91.5 ms/image** on a mixed 0.3–18 MP corpus
(~46 min for 30k), **258.8 ms/image** on 12–18 MP only (~2.2 h for 30k). Cost is dominated by the JS
Lanczos convolution at full resolution. Across 8 `worker_threads`, roughly 15–20 minutes for a 30k
backfill.

### 3.8 Verdict — item 3

> **Viable.** Primary choice: **vendor a ~168-line self-contained port** (PIL fixed-point Lanczos +
> greyscale + a 12-line 2D Haar LL), with `sharp` used only to decode to RGB. Fallback:
> [`rosetta-squint-hash`](https://www.npmjs.com/package/rosetta-squint-hash) 1.0.0 — correct internals but
> zero-star, single-author, and no more accurate than the vendored port, so given the code is this small,
> vendoring beats depending. **Do not** reach for `discrete-wavelets` (1D, unmaintained), any existing
> phash npm package (none implement whash), or Rust (`image_hasher` has no wavelet variant, and you'd
> still port PIL's Lanczos yourself).
>
> One caveat: **`sharp` must not be used for the resize** — it costs 4–6 Hamming bits and drops exact
> agreement to 33 %. And ~1–2 % of frames, concentrated in blank/void/clipped images, will differ by a few
> bits from Python-generated hashes no matter what, because pywt's compiler-contracted FMA is not
> reproducible in JS. Never use a whash hex as an equality or cache key across the Python/JS boundary —
> only as a thresholded distance. If the whole library can be re-hashed in JS, this concern disappears by
> construction.

---

*Created using Anthropic Claude.* This note should stay on internal versions until a human has reviewed
and verified the content. Measured figures were produced on one machine (macOS arm64, Node v24.14.1,
`.venv` rawpy 0.26.1 / imagehash 4.3.2 / pywt 1.8.0 / pillow 12.2.0) against a small sample of camera files;
re-run the parity harnesses against the real corpus before acting. Follow the linked primary sources rather
than citing this document.
