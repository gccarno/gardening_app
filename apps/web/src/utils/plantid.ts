// On-device plant identification: run the ONNX image tower in the browser,
// send only the embedding to POST /api/identify/embedding.
//
// Preprocessing must match ml/features/plantid_preprocess.py exactly — the
// server's prototypes and calibration were computed through it:
//   centred square crop -> resize to input_size -> RGB / 255 -> NCHW float32.
// Normalisation is baked into the model, so there are no per-model constants.

import { apiFetch } from '@garden/shared';
import type * as Ort from 'onnxruntime-web/wasm';

export interface PlantIdConfig {
  model_version: string;
  input_size: number;
  embed_dim: number;
  preprocess: string;
}

export interface LocalCandidate {
  name: string | null;
  scientific_name: string | null;
  confidence: number | null;
  library_match: { library_id: number; library_name: string; image_filename: string | null } | null;
}

export interface LocalIdentifyResult {
  mode: 'identify';
  candidates: LocalCandidate[];
  diagnosis: null;
  care_advice: null;
  source: 'local';
  confident: boolean;
  model_version: string;
}

/** Centred square crop of a width x height image (matches center_square in Python). */
export function centerSquare(width: number, height: number) {
  const side = Math.min(width, height);
  return { left: Math.floor((width - side) / 2), top: Math.floor((height - side) / 2), side };
}

/** RGBA pixels (canvas ImageData order) -> planar RGB float32 in [0, 1]. */
export function toNchw(rgba: Uint8ClampedArray, size: number): Float32Array {
  const plane = size * size;
  const out = new Float32Array(3 * plane);
  for (let i = 0; i < plane; i++) {
    out[i] = rgba[i * 4] / 255;
    out[plane + i] = rgba[i * 4 + 1] / 255;
    out[2 * plane + i] = rgba[i * 4 + 2] / 255;
  }
  return out;
}

interface LoadedModel {
  config: PlantIdConfig;
  session: Ort.InferenceSession;
  ort: typeof Ort;
}

let loading: Promise<LoadedModel> | null = null;

/** Download (once per page load; the browser caches the file) and open the model. */
export function loadPlantIdModel(): Promise<LoadedModel> {
  loading ??= (async () => {
    const res = await apiFetch('/api/identify/model');
    if (!res.ok) throw new Error('No on-device model deployed');
    const config: PlantIdConfig = await res.json();
    const ort = await import('onnxruntime-web/wasm');   // CPU-wasm build only; separate chunk
    // Multi-threaded wasm needs cross-origin isolation, which this app doesn't set.
    ort.env.wasm.numThreads = 1;
    const session = await ort.InferenceSession.create(
      `/api/identify/model/${config.model_version}.onnx`, { executionProviders: ['wasm'] });
    return { config, session, ort };
  })();
  loading.catch(() => { loading = null; });   // let a later attempt retry
  return loading;
}

/** Photo -> preprocessed pixels, the same contract as the Python reference. */
export async function preprocessPhoto(photo: Blob, size: number): Promise<Float32Array> {
  const bitmap = await createImageBitmap(photo);   // applies EXIF orientation
  const { left, top, side } = centerSquare(bitmap.width, bitmap.height);
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bitmap, left, top, side, side, 0, 0, size, size);
  bitmap.close();
  return toNchw(ctx.getImageData(0, 0, size, size).data, size);
}

export async function embedPhoto(photo: Blob): Promise<{ embedding: number[]; model_version: string }> {
  const { config, session, ort } = await loadPlantIdModel();
  const size = config.input_size;
  const pixels = await preprocessPhoto(photo, size);
  const out = await session.run({ pixels: new ort.Tensor('float32', pixels, [1, 3, size, size]) });
  return { embedding: Array.from(out.embedding.data as Float32Array), model_version: config.model_version };
}

/**
 * Identify on-device. Returns null whenever the local path can't answer
 * (no model deployed, unsupported browser, version retired) — the caller then
 * asks Claude. A non-null result may still be `confident: false`.
 */
export async function identifyOnDevice(photo: Blob): Promise<LocalIdentifyResult | null> {
  try {
    const { embedding, model_version } = await embedPhoto(photo);
    const res = await apiFetch('/api/identify/embedding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ embedding, model_version, top_k: 3 }),
    });
    if (res.status === 409) loading = null;   // version retired: reload config next time
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
