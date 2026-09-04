/**
 * CLIP image preprocessing, matching `CLIPImageProcessor` for
 * `openai/clip-vit-base-patch32` as sentence-transformers configures it.
 *
 * Config read off the live model (transformers, Pillow 12.2.0):
 *   do_convert_rgb, do_resize {shortest_edge: 224}, resample = 3 (BICUBIC),
 *   do_center_crop {224, 224}, do_rescale 1/255,
 *   image_mean [0.48145466, 0.4578275, 0.40821073],
 *   image_std  [0.26862954, 0.26130258, 0.27577711]
 *
 * Must NOT be replaced by transformers.js's own processor: its `RawImage.resize`
 * goes through sharp, which drifts the embedding to ~0.93 cosine against the stored
 * corpus. See src/imaging/pil-resample.ts for the measurements.
 */
import { centerCrop, pilResize, type Plane } from './pil-resample.js';

export const CLIP_IMAGE_SIZE = 224;
export const CLIP_SHORTEST_EDGE = 224;
export const CLIP_IMAGE_MEAN = [0.48145466, 0.4578275, 0.40821073] as const;
export const CLIP_IMAGE_STD = [0.26862954, 0.26130258, 0.27577711] as const;

/**
 * Port of `get_resize_output_image_size(..., default_to_square=False)`: scale the
 * shortest edge to `shortestEdge` and let the long edge follow, truncating (not
 * rounding) as Python's `int()` does.
 */
export function resizeShortestEdgeSize(
  width: number,
  height: number,
  shortestEdge = CLIP_SHORTEST_EDGE,
): { width: number; height: number } {
  const [short, long] = width <= height ? [width, height] : [height, width];
  const newLong = Math.trunc((shortestEdge * long) / short);
  return width <= height
    ? { width: shortestEdge, height: newLong }
    : { width: newLong, height: shortestEdge };
}

/**
 * Turn decoded RGB pixels into the `pixel_values` tensor the vision tower expects:
 * shape `[1, 3, 224, 224]`, channels-first, float32.
 */
export function clipPixelValues(rgb: Plane): Float32Array {
  if (rgb.channels < 3) {
    throw new Error(`clipPixelValues expects RGB input, got ${rgb.channels} channel(s)`);
  }

  const target = resizeShortestEdgeSize(rgb.width, rgb.height);
  const resized = pilResize(rgb, target.width, target.height, 'bicubic');
  const cropped = centerCrop(resized, CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE);

  const side = CLIP_IMAGE_SIZE;
  const plane = side * side;
  const out = new Float32Array(3 * plane);
  const { data, channels } = cropped;

  // Interleaved RGB -> planar CHW, rescaled by 1/255 then standardized.
  for (let ch = 0; ch < 3; ch++) {
    const mean = CLIP_IMAGE_MEAN[ch]!;
    const std = CLIP_IMAGE_STD[ch]!;
    const base = ch * plane;
    for (let i = 0; i < plane; i++) {
      out[base + i] = (data[i * channels + ch]! / 255 - mean) / std;
    }
  }
  return out;
}

/** Shape of the tensor `clipPixelValues` returns, for the ONNX/transformers input. */
export const CLIP_PIXEL_VALUES_SHAPE = [1, 3, CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE] as const;
