/**
 * CLIP image embeddings.
 *
 * Two decisions here are load-bearing and must not be "simplified":
 *
 * 1. **Our own preprocessing, not the library's.** transformers.js's `AutoProcessor`
 *    resizes through sharp/libvips, which is not Pillow. That alone drifts the
 *    embedding to ~0.93 cosine against the 43,451 vectors already in `library.db` —
 *    inside the near-duplicate band that stack detection and catalog similarity rank
 *    on. Feeding Pillow-exact pixels through the same graph gives cosine 1.000000
 *    (1-cos = 2.6e-12). So `clipPixelValues` does the preprocessing and the
 *    processor is bypassed entirely.
 * 2. **fp32.** Quantized weights would change the output, and `q8` measured no
 *    faster (20.3 ms vs 19.5 ms per image).
 */
import { CLIPVisionModelWithProjection, Tensor, env } from '@huggingface/transformers';
import sharp from 'sharp';
import { serializeFloat32 } from '../db/connection.js';
import { CLIP_PIXEL_VALUES_SHAPE, clipPixelValues } from './clip-preprocess.js';
import type { Plane } from './pil-resample.js';

/** Must match the model id recorded alongside the stored vectors. */
export const CLIP_EMBED_MODEL_ID = 'clip-ViT-B-32';
/** The transformers.js/ONNX export of the same weights. */
export const CLIP_ONNX_MODEL_ID = 'Xenova/clip-vit-base-patch32';
export const CLIP_EMBED_DIM = 512;

type VisionModel = Awaited<ReturnType<typeof CLIPVisionModelWithProjection.from_pretrained>>;

let modelPromise: Promise<VisionModel> | null = null;

/** Load the vision tower once per process, as the Python service does. */
function getModel(): Promise<VisionModel> {
  if (modelPromise === null) {
    env.allowLocalModels = false;
    modelPromise = CLIPVisionModelWithProjection.from_pretrained(CLIP_ONNX_MODEL_ID, {
      dtype: 'fp32',
    });
  }
  return modelPromise;
}

/** Decode an image file to interleaved RGB. sharp's JPEG/PNG decode is byte-identical
 *  to Pillow's — verified on a real cache JPEG (0 differing bytes of 2,098,176). */
export async function decodeRgb(path: string): Promise<Plane> {
  const { data, info } = await sharp(path)
    .removeAlpha()
    .toColourspace('srgb')
    .raw()
    .toBuffer({ resolveWithObject: true });
  return {
    data: new Uint8Array(data),
    width: info.width,
    height: info.height,
    channels: info.channels,
  };
}

function l2Normalize(v: Float32Array): Float32Array {
  let sum = 0;
  for (let i = 0; i < v.length; i++) sum += v[i]! * v[i]!;
  const norm = Math.sqrt(sum);
  if (norm === 0) return v;
  const out = new Float32Array(v.length);
  for (let i = 0; i < v.length; i++) out[i] = v[i]! / norm;
  return out;
}

/** Embed already-decoded pixels. Returns an L2-normalized 512-d vector. */
export async function encodePixels(rgb: Plane): Promise<Float32Array> {
  const model = await getModel();
  const pixelValues = new Tensor('float32', clipPixelValues(rgb), [...CLIP_PIXEL_VALUES_SHAPE]);
  const { image_embeds } = await model({ pixel_values: pixelValues });
  return l2Normalize(new Float32Array(image_embeds.data as Float32Array));
}

/**
 * Embed image files. Mirrors `encode_images(paths, batch_size=8)`.
 *
 * Sequential rather than batched: the ONNX session is already internally threaded,
 * and batching here would only add peak memory. Parallelism belongs at the job
 * level, across worker threads.
 */
export async function encodeImages(paths: string[]): Promise<Float32Array[]> {
  const out: Float32Array[] = [];
  for (const path of paths) {
    out.push(await encodePixels(await decodeRgb(path)));
  }
  return out;
}

/**
 * The `vec0` blob for one embedding.
 *
 * The dimension check is the Python assertion kept deliberately: `vec0` stores
 * whatever bytes it is handed, so a wrong-length vector would be written and only
 * surface later as a KNN that silently returns nothing.
 */
export function clipVecBlob(vector: Float32Array): Buffer {
  if (vector.length !== CLIP_EMBED_DIM) {
    throw new Error(`CLIP embedding must be ${CLIP_EMBED_DIM}-d, got ${vector.length}`);
  }
  return serializeFloat32(vector);
}
