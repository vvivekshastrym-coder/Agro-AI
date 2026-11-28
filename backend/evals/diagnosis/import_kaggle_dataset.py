"""Downloads `jawadali1045/20k-multi-class-crop-disease-images` via kagglehub
and builds a stratified evaluation manifest compatible with `run_diagnosis_benchmark.py`.

Usage (from repo root):
  pip install kagglehub
  python backend/evals/diagnosis/import_kaggle_dataset.py --per-class 5

Notes:
- Keeps downloaded images in kagglehub's local cache (~/.cache/kagglehub), NEVER inside git.
- Labels in public Kaggle datasets are community-curated (`source_review="kaggle_public_unreviewed"`),
  not KVK/ICAR field-verified Indian farm photos — keep separate from expert-reviewed field manifests.
"""
import argparse
import collections
import json
import os
import random
import re
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_folder_label(folder_name: str):
    """Splits folder names like 'Tomato___Early_blight', 'Rice__Leaf_Blast', or 'Cotton_Healthy' into (crop, problem, category)."""
    cleaned = folder_name.strip()
    if "___" in cleaned:
        crop_raw, prob_raw = cleaned.split("___", 1)
    elif "__" in cleaned:
        crop_raw, prob_raw = cleaned.split("__", 1)
    elif "_" in cleaned:
        crop_raw, prob_raw = cleaned.split("_", 1)
    else:
        crop_raw, prob_raw = cleaned, "unknown"

    crop = re.sub(r"[_\-]+", " ", crop_raw).strip().title()
    prob = re.sub(r"[_\-]+", " ", prob_raw).strip()
    prob_low = prob.lower()
    if "healthy" in prob_low:
        cat = "healthy"
        prob = "Healthy"
    elif any(k in prob_low for k in ("blight", "rust", "mildew", "rot", "spot", "smut", "blast", "mold", "scab", "anthracnose")):
        cat = "fungal"
    elif any(k in prob_low for k in ("bacteri", "canker", "wilt")):
        cat = "bacterial"
    elif any(k in prob_low for k in ("virus", "mosaic", "curl", "yellow leaf")):
        cat = "viral"
    elif any(k in prob_low for k in ("mite", "aphid", "borer", "miner", "worm", "thrip", "bug", "pest", "insect")):
        cat = "pest"
    else:
        cat = "unclear"
    return crop, prob, cat


def build_manifest(dataset_root: Path, per_class: int, seed: int, out_path: Path):
    by_folder = collections.defaultdict(list)
    for p in dataset_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            by_folder[p.parent.name].append(p)

    rng = random.Random(seed)
    samples = []
    for folder in sorted(by_folder.keys()):
        files = sorted(by_folder[folder])
        chosen = rng.sample(files, min(per_class, len(files)))
        crop, prob, cat = parse_folder_label(folder)
        for idx, img_path in enumerate(chosen, 1):
            samples.append({
                "id": f"{re.sub(r'[^a-z0-9]+', '-', folder.lower()).strip('-')}-{idx:03d}",
                "image_path": str(img_path.resolve()),
                "raw_class": folder,
                "is_plant": True,
                "expected_crop": crop,
                "expected_problem": prob,
                "expected_category": cat,
                "crop_hint_supplied": "",
            })

    manifest = {
        "version": "0.1-kaggle-public",
        "dataset": "jawadali1045/20k-multi-class-crop-disease-images",
        "reviewer": "UNREVIEWED_PUBLIC_DATASET (use for dev/smoke benchmarking; supplement with KVK Indian field photos)",
        "classes_found": len(by_folder),
        "samples_per_class": per_class,
        "total_samples": len(samples),
        "samples": samples,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Dataset root: {dataset_root}")
    print(f"Classes discovered: {len(by_folder)} | Stratified samples written: {len(samples)} -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="jawadali1045/20k-multi-class-crop-disease-images")
    ap.add_argument("--per-class", type=int, default=5, help="Stratified sample count per class folder")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "kaggle_20k_manifest.json"))
    args = ap.parse_args()

    try:
        import kagglehub
    except ImportError:
        raise SystemExit("kagglehub is not installed. Run: pip install kagglehub")

    path = kagglehub.dataset_download(args.dataset)
    print("Path to dataset files:", path)
    build_manifest(Path(path), args.per_class, args.seed, Path(args.out))


if __name__ == "__main__":
    main()
