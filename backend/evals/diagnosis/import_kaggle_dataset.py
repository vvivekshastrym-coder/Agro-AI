"""Downloads `jawadali1045/20k-multi-class-crop-disease-images` via kagglehub,
audits duplicates and class hygiene, and builds a clean stratified evaluation manifest
compatible with `run_diagnosis_benchmark.py`.

Usage (from repo root):
  python backend/evals/diagnosis/import_kaggle_dataset.py --per-class 5

Hygiene guarantees:
- Deduplicates exact MD5 copies (the raw Kaggle Train/Validation folders share 1,763 identical files).
- Excludes conflicting cross-class exact duplicates (15 images shared across multiple bollworm folders).
- Merges split-case & nested folders ("bacterial_blight in Cotton" + "Bacterial Blight in cotton",
  "Wheat Brown leaf Rust" + "Wheat Brown leaf rust", "Healthy Wheat" + "Wheat___Healthy").
- Excludes classes with < 20 clean unique images ("bollrot on Cotton", n=4) and records them explicitly.
"""
import argparse
import collections
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kaggle_20k_taxonomy import CROP_HAS_HEALTHY_CLASS, lookup_folder_taxonomy  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def scan_and_deduplicate(dataset_root: Path):
    """Returns (clean_by_canonical_key, audit_summary)."""
    raw_files = [
        p for p in sorted(dataset_root.rglob("*"))
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    md5_to_records = collections.defaultdict(list)
    unmapped_folders = set()
    excluded_by_rule = collections.Counter()

    for p in raw_files:
        folder = p.parent.name
        tax = lookup_folder_taxonomy(folder)
        if tax is None:
            unmapped_folders.add(folder)
            continue
        if tax.get("exclude_reason"):
            excluded_by_rule[f"{folder} ({tax['exclude_reason']})"] += 1
            continue
        digest = hashlib.md5(p.read_bytes()).hexdigest()
        md5_to_records[digest].append((p, folder, tax))

    clean_by_key = collections.defaultdict(list)
    exact_dup_files_skipped = 0
    cross_class_conflict_hashes = 0
    cross_class_conflict_files = 0

    for digest, recs in md5_to_records.items():
        canonical_keys = {r[2]["canonical_key"] for r in recs}
        if len(canonical_keys) > 1:
            cross_class_conflict_hashes += 1
            cross_class_conflict_files += len(recs)
            continue
        if len(recs) > 1:
            exact_dup_files_skipped += len(recs) - 1
        p0, folder0, tax0 = recs[0]
        clean_by_key[tax0["canonical_key"]].append((p0, folder0, tax0, digest))

    audit = {
        "raw_total_files": len(raw_files),
        "unique_clean_md5_hashes": sum(len(v) for v in clean_by_key.values()),
        "exact_duplicate_files_removed": exact_dup_files_skipped,
        "cross_class_conflict_hashes_removed": cross_class_conflict_hashes,
        "cross_class_conflict_files_removed": cross_class_conflict_files,
        "excluded_classes_by_hygiene_rule": dict(excluded_by_rule),
        "unmapped_folders": sorted(unmapped_folders),
        "crop_has_healthy_class": CROP_HAS_HEALTHY_CLASS,
        "canonical_classes_retained": len(clean_by_key),
        "per_class_clean_counts": {k: len(clean_by_key[k]) for k in sorted(clean_by_key)},
    }
    return clean_by_key, audit


def build_manifest(dataset_root: Path, per_class: int, seed: int, out_path: Path):
    clean_by_key, audit = scan_and_deduplicate(dataset_root)
    rng = random.Random(seed)
    samples = []

    for key in sorted(clean_by_key):
        items = sorted(clean_by_key[key], key=lambda x: str(x[0]))
        chosen = rng.sample(items, min(per_class, len(items)))
        for idx, (img_path, raw_folder, tax, digest) in enumerate(chosen, 1):
            slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
            samples.append({
                "id": f"{slug}-{idx:03d}",
                "image_path": str(img_path.resolve()),
                "md5": digest,
                "raw_class": raw_folder,
                "canonical_key": key,
                "is_plant": True,
                "expected_crop": tax["crop"],
                "expected_problem": tax["problem"],
                "expected_category": tax["category"],
                "crop_hint_supplied": "",
            })

    manifest = {
        "version": "0.2-kaggle-dedup-canonical",
        "dataset": "jawadali1045/20k-multi-class-crop-disease-images",
        "reviewer": "UNREVIEWED_PUBLIC_DATASET (deduplicated & canonically mapped; supplement with KVK Indian field photos)",
        "audit": audit,
        "classes_found": len(clean_by_key),
        "samples_per_class": per_class,
        "total_samples": len(samples),
        "samples": samples,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Dataset root: {dataset_root}")
    print(
        f"Raw files: {audit['raw_total_files']} | Clean deduplicated: {audit['unique_clean_md5_hashes']} | "
        f"Canonical classes: {len(clean_by_key)} | Stratified samples: {len(samples)} -> {out_path}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="jawadali1045/20k-multi-class-crop-disease-images")
    ap.add_argument("--per-class", type=int, default=5, help="Stratified sample count per canonical class")
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
