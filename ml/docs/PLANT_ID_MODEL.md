# Plant-ID model

On-device species identification from a photo. The client (web and Android)
runs a small ONNX image model, sends only the embedding to the server, and the
server ranks it against per-species prototypes in Postgres. Uncertain answers
fall back to the existing Claude vision endpoint. Organised, like
[`WATERING_MODEL.md`](WATERING_MODEL.md), on Burkov's 10-step lifecycle.

## 1. Business problem

Photo ID (`POST /api/identify`) was a Claude API call. That costs money per
photo, needs `ANTHROPIC_API_KEY` on the server, and wasn't evaluated: there was
no measured accuracy and nothing calibrated about the confidence it reports.

## 2. Goal

For the `identify` mode only (health, disease and pest stay on Claude):

- answer locally when confident, and be right ≥ 90% of the time when it does
  (`TARGET_ACCURACY` in `ml/experiments/plantid_backbones.py`);
- defer to Claude otherwise. A local answer is never forced;
- never load a model in a Render request (see the free-tier request-path rule).
  The server does one SQL scan.

Success is measured on held-out real-world photos, not the library's own.

## 3. Data

| Set | Source | Size | Used for |
|---|---|---|---|
| Library photos | `plant_library_image`, **excluding the 6,207 `ai-generated` rows** | 24,733 photos, ≤ 4 real per species | prototypes, distillation |
| Eval set | iNaturalist research-grade, CC0/CC-BY, `ml/data/build_plantid_eval.py` | 300 species × 5 = 1,500 photos | evaluation only |
| Distillation set | broad iNaturalist Plantae, CC0/CC-BY/CC-BY-NC, `ml/data/build_plantid_distill_set.py` | 30,000 photos + the library | training only (labels unused) |

**Label = species, not library row.** Many library rows are cultivars that
share a scientific name (23 rows are *Capsicum annuum*), and no photo can tell
them apart. `species_key` (`ml/features/plantid_data.py`) strips cultivar names
(`(Brandywine)`, `'Jalapeno'`) and rank markers but keeps trinomials (cabbage
and kale look different). 8,890 species have at least one real photo.

**Eval-set design.** One photo per observation, so a species isn't five shots
of the same plant. Photos whose SHA-256 or iNaturalist photo id matches a
library image are dropped. The species are split 50/50 by species, with seed 42:
the *calibration* half picks blends, temperature, the hand-off threshold and
the training checkpoint, and every reported number comes from the *test* half.
Species are sampled crops-first. "Cultivated" means ≥ 3 library rows or a row
typed vegetable/herb (108 species); `PlantLibrary.type` is NULL for about 89% of rows.

**Known data limits.**
- iNaturalist research grade **excludes cultivated plants**, so "cultivated"
  eval photos show wild or naturalised individuals, not garden beds.
- Synonyms aren't merged (*Lycopersicum esculentum* vs *Solanum lycopersicum*).
  That needs a taxonomy lookup (GBIF/iNat), which isn't done.
- Library photos are noisy (Wikimedia includes herbarium sheets and
  mismatches). See the α = 0 finding in §6.

## 4. Features / preprocessing

The client contract (`ml/features/plantid_preprocess.py`, mirrored in
`apps/web/src/utils/plantid.ts` and `android/.../PlantIdPreprocess.kt`):
apply EXIF rotation → crop the centred square → bilinear-resize to `input_size` → RGB/255 →
NCHW float32. Mean/std normalisation and L2-normalising the output are baked
into the ONNX graph, so clients have no per-model constants. Android
downsamples by halving so its 2×2 bilinear scale doesn't alias.

## 5. Training

**Phase 1: frozen backbones** (`ml/experiments/plantid_backbones.py`). Each
species prototype is the mean of its L2-normalised photo embeddings,
optionally blended with a text prototype (`"a photo of Genus species."`) for
CLIP-family models.

**Phase 2: distillation** (`ml/training/train_plantid_student.py`). Only
BioCLIP was accurate enough, and its 86M-parameter image tower is too big for a
client. A small student (backbone + linear head into BioCLIP's 512-d space)
is trained on unlabelled photos, with the same augmented crop going to both models:

    loss = (1 − cos(student, teacher)) + λ · KL(p_teacher ‖ p_student)
    p = softmax(embedding · species_text_prototypesᵀ / 0.01)

The KL term targets exactly what is served: the ranking over species. Because
the student lives in BioCLIP's space, it is served against BioCLIP's
prototypes (computed offline), which also covers species with one or two photos.

## 6. Evaluation

Phase 1, test half: 750 photos across 150 species, ranked against all 8,890 species.

| Backbone | Params | top-1 | top-5 | cultivated top-1 | best α | coverage @ τ | accuracy @ τ |
|---|---|---|---|---|---|---|---|
| **BioCLIP** | 86M | **43.7%** | **69.6%** | 34.1% | 0.0 | 15.7% | 94.9% |
| DINOv2-S | 22M | 18.0% | 33.5% | 10.7% | 1.0 | 0.1% | 100% (1 photo) |
| MobileCLIP-S1 | 22M | 9.3% | 20.1% | 8.3% | 0.25 | 0.7% | 100% |
| MobileCLIP2-S0 | 11M | 7.3% | 17.7% | 9.3% | 0.0 | 2.8% | 57.1% |

Findings:
- General-purpose CLIP models are poor at fine-grained species. BioCLIP's
  text-only zero-shot alone is 43.7%.
- **α = 0 for BioCLIP**: text prototypes (43.7%) beat image prototypes from
  library photos (27.6%), and blending them in hurts. The library photos are
  the weak link.
- Temperature scaling matters: BioCLIP's raw-softmax ECE is 0.44, and 0.06 after scaling.

Distillation pilot (8k photos, 2 epochs, calibration-half top-1): MobileCLIP2-S0
4.1%, DINOv2-S 0.1%, so **MobileCLIP2-S0 is the student**. Full run: *pending*.

Head-to-head with production Claude (`ml/evaluation/plantid_claude_baseline.py`,
local vs Claude vs hybrid on the same test photos): *pending, needs
`ANTHROPIC_API_KEY`*.

Metrics code: `ml/evaluation/plantid_metrics.py` (top-k, ECE, temperature fit,
coverage curve, threshold choice), tested in `tests/unit/test_plantid_metrics.py`.

## 7. Deployment

`ml/training/export_plantid_onnx.py` writes `ml/models/plantid_<v>.onnx`
(static int8, QDQ) and `plantid_<v>.json` (input size, temperature, τ,
metrics). Prototypes and calibration are computed from the **exported int8
model on the client preprocessing**, so the server's probabilities describe
what clients actually embed. **Parity gate:** int8 vs fp32 top-1 agreement must
be ≥ 0.97, or nothing is written. `scripts/build_plantid_prototypes.py` loads the
prototypes into `plant_image_prototype`, replacing that version's rows in one
transaction. Promotion is manual (commit the artifacts), as for the other models.

## 8. Serving

- `GET /api/identify/model`: the current version's public config (newest by
  `created`; `PLANTID_MODEL_VERSION` pins a rollback).
- `GET /api/identify/model/{v}.onnx`: the model file, `Cache-Control: immutable`.
- `POST /api/identify/embedding`: `{embedding, model_version, top_k}` → the
  same shape as `/api/identify` plus `source: "local"` and `confident`. One SQL
  query returns the top-k; a second computes the **full softmax normaliser over
  every species** (a top-k-only softmax would overstate confidence). An unknown
  version or a version with no prototypes returns 409, and the client falls back to Claude.

Clients: web loads `onnxruntime-web/wasm` lazily on the Identify page (about 3.7 MB
gzipped runtime). Android downloads the model on first use and caches it in
`filesDir`; it isn't bundled, so a new version needs no app release. ONNX Runtime
1.30.0 on both.

## 9. Monitoring

*Not built yet.* Planned: log `source`/`confident` per request and the share
answered locally, plus disagreement on the photos where both local and Claude answered.

## 10. Maintenance

New library photos → re-run the export and prototype load. A new version
ships side by side with the old one (both sets of rows coexist), clients pick
it up from `/api/identify/model`, and the old one returns 409 once its rows are deleted.

## Model card

- **Intended use:** suggesting a species for a garden photo, with a hand-off to Claude when unsure.
- **Not for:** edibility or toxicity decisions, or disease diagnosis.
- **Data licences:** eval photos are CC0/CC-BY with attribution in the
  committed CSV; distillation photos include CC-BY-NC and are used for
  training only, never redistributed.
- **Known failure modes:** cultivars collapse to their species; synonyms
  aren't merged; garden-bed context is under-represented (see §3); the
  answer is closed-set over the 8,890 library species with photos.

## Quick reference

Setup (local GPU machine only; deliberately not a `pyproject.toml` extra, since
adding `torchvision` to the lock bumps the shared `torch` pin):

```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
uv pip install open_clip_torch timm onnx onnxruntime onnxscript
```

```bash
uv run --no-sync python ml/data/build_plantid_eval.py                 # eval set
uv run --no-sync python ml/experiments/plantid_backbones.py           # bake-off
uv run --no-sync python ml/data/build_plantid_distill_set.py --library --inat 30000
uv run --no-sync python ml/training/train_plantid_student.py --student mobileclip2_s0 --epochs 15 --tag v1
uv run --no-sync python ml/training/export_plantid_onnx.py --student-ckpt ml/data/raw/plantid_cache/student_mobileclip2_s0_v1.pt --version v1
uv run --no-sync python scripts/build_plantid_prototypes.py --version v1
uv run --no-sync python ml/evaluation/plantid_claude_baseline.py --backbone bioclip
```
