"""Phase 10 Leaf Diagnosis Benchmark & Calibration Runner.

Usage (from repo root):
  python backend/evals/diagnosis/run_diagnosis_benchmark.py --manifest path/to/manifest.json

Manifest format (expert-labelled Indian farm photos):
{
  "version": "1.0",
  "reviewer": "Agronomist / KVK name",
  "samples": [
    {
      "id": "ka-ragi-001",
      "image_path": "samples/ka-ragi-001.jpg",
      "is_plant": true,
      "expected_crop": "Ragi",
      "expected_problem": "Leaf Blast",
      "expected_category": "fungal",
      "crop_hint_supplied": ""
    }
  ]
}

Computes:
- Plant identification accuracy & per-crop precision / recall / F1
- Problem / disease identification accuracy (on correctly identified crops)
- False diagnosis rate on non-plant / healthy / ambiguous photos
- False HIGH-confidence rate (HIGH confidence predicted when crop or problem is wrong)
Never fabricates benchmark numbers: requires real expert-labelled images in the manifest.
"""
import argparse
import asyncio
import collections
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.diagnosis_engine import analyze_leaf_image_v3, crops_match  # noqa: E402


def _prf(tp: int, fp: int, fn: int):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


async def run_benchmark(manifest_path: str, out_path: str):
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    base_dir = os.path.dirname(os.path.abspath(manifest_path))
    samples = manifest.get("samples") or []
    if not samples:
        raise SystemExit("Manifest contains 0 samples. Add expert-reviewed images before running benchmark.")

    rows = []
    crop_tp = collections.Counter()
    crop_fp = collections.Counter()
    crop_fn = collections.Counter()
    false_diagnoses = 0
    non_disease_total = 0
    false_high_conf = 0
    high_conf_total = 0

    for item in samples:
        img_file = os.path.join(base_dir, item["image_path"])
        raw_bytes = open(img_file, "rb").read()
        res = await analyze_leaf_image_v3(raw_bytes, "image/jpeg", crop_hint=item.get("crop_hint_supplied", ""))

        exp_is_plant = item.get("is_plant", True)
        exp_crop = (item.get("expected_crop") or "").strip().lower()
        exp_prob = (item.get("expected_problem") or "").strip().lower()

        pred_crop = ((res.get("plant_identification") or {}).get("crop") or res.get("crop") or "").strip().lower()
        pred_prob = (res.get("disease") or "").strip().lower()
        conf_cat = res.get("confidence_category", "LOW")

        crop_ok = (not exp_is_plant and res.get("status") == "not_a_plant") or (exp_is_plant and crops_match(exp_crop, pred_crop))
        prob_ok = crop_ok and (exp_prob in pred_prob or pred_prob in exp_prob) if exp_prob else crop_ok

        if exp_is_plant and exp_crop:
            if crop_ok:
                crop_tp[exp_crop] += 1
            else:
                crop_fn[exp_crop] += 1
                if pred_crop:
                    crop_fp[pred_crop] += 1

        if (not exp_is_plant) or exp_prob in ("healthy", "unclear", ""):
            non_disease_total += 1
            if res.get("status") in ("ok", "moderate_confidence") and pred_prob not in ("healthy", ""):
                false_diagnoses += 1

        if conf_cat == "HIGH":
            high_conf_total += 1
            if not (crop_ok and prob_ok):
                false_high_conf += 1

        rows.append({"id": item["id"], "status": res.get("status"), "pred_crop": pred_crop, "pred_problem": pred_prob,
                     "confidence_category": conf_cat, "crop_ok": crop_ok, "problem_ok": prob_ok})

    all_crops = sorted(set(crop_tp) | set(crop_fp) | set(crop_fn))
    per_crop = {c: _prf(crop_tp[c], crop_fp[c], crop_fn[c]) for c in all_crops}
    summary = {
        "manifest_version": manifest.get("version"),
        "reviewer": manifest.get("reviewer"),
        "total_samples": len(rows),
        "plant_id_accuracy": round(sum(1 for r in rows if r["crop_ok"]) / len(rows), 4),
        "end_to_end_accuracy": round(sum(1 for r in rows if r["problem_ok"]) / len(rows), 4),
        "false_diagnosis_rate": round(false_diagnoses / non_disease_total, 4) if non_disease_total else None,
        "false_high_confidence_rate": round(false_high_conf / high_conf_total, 4) if high_conf_total else None,
        "per_crop_metrics": per_crop,
        "rows": rows,
    }
    json.dump(summary, open(out_path, "w", encoding="utf-8"), indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "benchmark_results.json"))
    args = ap.parse_args()
    asyncio.run(run_benchmark(args.manifest, args.out))
