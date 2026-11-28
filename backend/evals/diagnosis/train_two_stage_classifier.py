"""Trains, calibrates, exports (ONNX), and evaluates a leakage-free Two-Stage Crop & Disease
Vision Classifier on `jawadali1045/20k-multi-class-crop-disease-images`.

Architecture:
- Backbone: Pretrained MobileNetV3-Small (`IMAGENET1K_V1`), early conv stem frozen (`features[:8]`),
  high-level Squeeze-and-Excitation semantic blocks (`features[8:]`) fine-tuned jointly with:
  * Stage A (`crop_head`): 5-crop classifier (Cotton, Maize, Rice, Sugarcane, Wheat)
  * Stage B (`problem_head`): 40-class crop-conditioned disease/pest/healthy classifier
  * L2-normalized 576-d penultimate embedding for class-prototype cosine OOD / non-plant rejection
- Post-hoc Calibration (fit strictly on held-out 15% `val` split):
  * Separate Temperature Scaling (`T_crop`, `T_problem`)
  * Prototype cosine similarity OOD threshold calibrated against non-plant synthetic/geometric/noise images
  * Categorical confidence thresholds (`HIGH`, `MODERATE`, `LOW`) calibrated for high precision
- Unbiased Final Evaluation (run via `onnxruntime` on untouched 15% `test` split):
  * Writes real measured metrics to `backend/evals/diagnosis/model_eval_report.json`
  * Exports self-contained single-file ONNX graph (`backend/app/ml/agro_two_stage_v1.onnx`) + metadata JSON.
"""
import argparse
import base64
import collections
import io
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFile, ImageOps
import torch

ImageFile.LOAD_TRUNCATED_IMAGES = True
import torch.nn as nn
import torch.nn.functional as F
import torchvision

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent.parent
sys.path.insert(0, str(THIS_DIR))

from import_kaggle_dataset import scan_and_deduplicate  # noqa: E402
from kaggle_20k_taxonomy import (  # noqa: E402
    CROP_HAS_HEALTHY_CLASS,
    CROP_SCIENTIFIC,
    CROP_VISIBLE_FEATURES,
    DEFAULT_CULTURAL_BY_CATEGORY,
)


def _safe_open_rgb(raw_im: Image.Image) -> Image.Image:
    try:
        im = ImageOps.exif_transpose(raw_im)
    except Exception:
        im = raw_im
    if im.mode in ("P", "RGBA", "LA"):
        im = im.convert("RGBA")
    return im.convert("RGB")


def compute_dhash(img_path: Path) -> str:
    """Fast 8x8 horizontal gradient perceptual hash to keep near-duplicates in the same split."""
    try:
        with Image.open(img_path) as im:
            g = _safe_open_rgb(im).convert("L").resize((9, 8), Image.Resampling.BILINEAR)
            arr = np.asarray(g, dtype=np.int16)
            bits = (arr[:, 1:] > arr[:, :-1]).flatten()
            val = 0
            for b in bits:
                val = (val << 1) | int(b)
            return f"{val:016x}"
    except Exception:
        return f"err_{img_path.name}"


def load_rgb_224(img_path: Path, train_jitter_seed: int = 0) -> np.ndarray:
    """Loads image, applies EXIF orientation safely, center-crops (or slight random crop if seed>0) to 224x224 float32 [0,1] CHW."""
    with Image.open(img_path) as raw:
        im = _safe_open_rgb(raw)
    w, h = im.size
    if train_jitter_seed > 0:
        rng = random.Random(train_jitter_seed)
        target_short = rng.randint(232, 264)
        scale = target_short / max(min(w, h), 1)
        nw, nh = max(224, int(round(w * scale))), max(224, int(round(h * scale)))
        im = im.resize((nw, nh), Image.Resampling.BILINEAR)
        x0 = rng.randint(0, nw - 224)
        y0 = rng.randint(0, nh - 224)
        im = im.crop((x0, y0, x0 + 224, y0 + 224))
        if rng.random() < 0.5:
            im = ImageOps.mirror(im)
        arr = np.asarray(im, dtype=np.float32) / 255.0
        gain = rng.uniform(0.90, 1.10)
        bias = rng.uniform(-0.04, 0.04)
        arr = np.clip(arr * gain + bias, 0.0, 1.0)
    else:
        scale = 240.0 / max(min(w, h), 1)
        nw, nh = max(224, int(round(w * scale))), max(224, int(round(h * scale)))
        im = im.resize((nw, nh), Image.Resampling.BILINEAR)
        x0 = (nw - 224) // 2
        y0 = (nh - 224) // 2
        im = im.crop((x0, y0, x0 + 224, y0 + 224))
        arr = np.asarray(im, dtype=np.float32) / 255.0
    return np.transpose(arr, (2, 0, 1)).astype(np.float32)


def make_non_plant_synthetic_images(count: int, seed: int) -> List[bytes]:
    """Generates diverse non-plant / UI / geometric / noise / solid / gradient JPEG images for OOD calibration & test."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    out: List[bytes] = []
    for idx in range(count):
        kind = idx % 8
        im = Image.new("RGB", (320, 320), (128, 128, 128))
        draw = ImageDraw.Draw(im)
        if kind == 0:
            # Solid non-leaf colours (concrete, sky, paper, brick, asphalt)
            col = rng.choice([(210, 210, 215), (45, 50, 58), (185, 95, 70), (70, 130, 200), (245, 242, 235)])
            im = Image.new("RGB", (320, 320), col)
        elif kind == 1:
            # Synthetic geometric lines/ellipses on green/brown background (like unit-test _make_jpeg!)
            bg = (rng.randint(50, 95), rng.randint(115, 160), rng.randint(45, 85))
            im = Image.new("RGB", (320, 320), bg)
            draw = ImageDraw.Draw(im)
            for i in range(16, 300, 22):
                draw.line([(i, 8), (320 - i, 312)], fill=(180, 160, 40), width=3)
                draw.ellipse([(i, i % 260), (i + 18, (i % 260) + 18)], fill=(95, 55, 30))
        elif kind == 2:
            # UI screenshot / document card wireframe
            im = Image.new("RGB", (320, 320), (248, 250, 252))
            draw = ImageDraw.Draw(im)
            draw.rectangle([0, 0, 320, 48], fill=(25, 45, 85))
            for y in range(68, 290, 36):
                draw.rectangle([20, y, 300, y + 22], outline=(190, 198, 210), fill=(255, 255, 255))
                draw.line([(30, y + 11), (rng.randint(140, 280), y + 11)], fill=(80, 90, 110), width=4)
        elif kind == 3:
            # Random RGB Gaussian / sensor noise
            arr = np_rng.integers(0, 256, size=(320, 320, 3), dtype=np.uint8)
            im = Image.fromarray(arr, mode="RGB")
        elif kind == 4:
            # Checkerboard / grid floor tiles
            tile = rng.choice([16, 24, 32, 40])
            c1 = (rng.randint(150, 230), rng.randint(150, 230), rng.randint(150, 230))
            c2 = (rng.randint(30, 100), rng.randint(30, 100), rng.randint(30, 100))
            for y in range(0, 320, tile):
                for x in range(0, 320, tile):
                    draw.rectangle([x, y, x + tile, y + tile], fill=c1 if ((x // tile + y // tile) % 2 == 0) else c2)
        elif kind == 5:
            # Smooth sky/sunset/wall gradient
            arr = np.zeros((320, 320, 3), dtype=np.uint8)
            c_top = np.array([rng.randint(20, 240) for _ in range(3)], dtype=np.float32)
            c_bot = np.array([rng.randint(20, 240) for _ in range(3)], dtype=np.float32)
            for y in range(320):
                t = y / 319.0
                arr[y, :, :] = np.clip((1 - t) * c_top + t * c_bot, 0, 255).astype(np.uint8)
            im = Image.fromarray(arr, mode="RGB")
        elif kind == 6:
            # Concentric circles / metallic/wheel object
            im = Image.new("RGB", (320, 320), (90, 95, 102))
            draw = ImageDraw.Draw(im)
            for r in range(140, 15, -18):
                shade = rng.randint(40, 210)
                draw.ellipse([160 - r, 160 - r, 160 + r, 160 + r], outline=(shade, shade, shade), width=6)
        else:
            # Dry bare soil / gravel / wood planks without plant tissue
            base = np_rng.normal(loc=[138, 104, 76], scale=22, size=(320, 320, 3))
            im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), mode="RGB")

        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
        out.append(buf.getvalue())
    return out


class TwoStageLeafNet(nn.Module):
    """Single-backbone, dual-head Crop (Stage A) + Problem (Stage B) network with built-in ImageNet normalization."""

    def __init__(self, num_crops: int, num_problems: int):
        super().__init__()
        weights = torchvision.models.MobileNet_V3_Small_Weights.DEFAULT
        base = torchvision.models.mobilenet_v3_small(weights=weights)
        self.register_buffer("mean", torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 3, 1, 1))

        self.stem = base.features[:8]  # Frozen early conv blocks -> [B, 48, 14, 14]
        self.top = base.features[8:]   # Trainable high-level SE + inverted residual blocks -> [B, 576, 7, 7]
        self.pool = base.avgpool       # -> [B, 576, 1, 1]

        self.crop_head = nn.Sequential(
            nn.Linear(576, 256),
            nn.Hardswish(),
            nn.Dropout(p=0.25),
            nn.Linear(256, num_crops),
        )
        self.problem_head = nn.Sequential(
            nn.Linear(576, 256),
            nn.Hardswish(),
            nn.Dropout(p=0.25),
            nn.Linear(256, num_problems),
        )

        for p in self.stem.parameters():
            p.requires_grad = False
        self.stem.eval()

    def forward_stem(self, x_01: torch.Tensor) -> torch.Tensor:
        x = (x_01 - self.mean) / self.std
        return self.stem(x)

    def forward_from_mid(self, mid: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        feat = self.pool(self.top(mid)).flatten(1)
        emb_norm = F.normalize(feat, p=2, dim=1)
        crop_logits = self.crop_head(feat)
        problem_logits = self.problem_head(feat)
        return emb_norm, crop_logits, problem_logits

    def forward(self, x_01: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mid = self.forward_stem(x_01)
        return self.forward_from_mid(mid)


def stratified_group_split(clean_by_key: Dict[str, list], seed: int = 42):
    """Splits each canonical class 70/15/15 by dHash cluster so near-duplicates never cross splits."""
    rng = random.Random(seed)
    splits = {"train": [], "val": [], "test": []}

    all_items = [(k, item) for k in sorted(clean_by_key) for item in clean_by_key[k]]
    print(f"Computing perceptual dHash across {len(all_items)} deduplicated images...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        dhashes = list(ex.map(lambda pair: compute_dhash(pair[1][0]), all_items))

    grouped_by_key = collections.defaultdict(lambda: collections.defaultdict(list))
    for (k, item), dh in zip(all_items, dhashes):
        grouped_by_key[k][dh].append(item)

    for k in sorted(grouped_by_key):
        clusters = list(grouped_by_key[k].items())
        rng.shuffle(clusters)
        total_n = sum(len(v) for _, v in clusters)
        target_test = max(4, int(round(0.15 * total_n)))
        target_val = max(4, int(round(0.15 * total_n)))

        test_bucket, val_bucket, train_bucket = [], [], []
        for dh, recs in clusters:
            if len(test_bucket) < target_test:
                test_bucket.extend((r[0], k, r[2], r[3], dh) for r in recs)
            elif len(val_bucket) < target_val:
                val_bucket.extend((r[0], k, r[2], r[3], dh) for r in recs)
            else:
                train_bucket.extend((r[0], k, r[2], r[3], dh) for r in recs)

        splits["train"].extend(train_bucket)
        splits["val"].extend(val_bucket)
        splits["test"].extend(test_bucket)

    # Strict zero-leakage assertions
    md5_sets = {s: {r[3] for r in rows} for s, rows in splits.items()}
    assert not (md5_sets["train"] & md5_sets["val"]), "MD5 leak between train and val!"
    assert not (md5_sets["train"] & md5_sets["test"]), "MD5 leak between train and test!"
    assert not (md5_sets["val"] & md5_sets["test"]), "MD5 leak between val and test!"

    dh_sets = {s: {(r[1], r[4]) for r in rows} for s, rows in splits.items()}
    assert not (dh_sets["train"] & dh_sets["val"]), "dHash leak between train and val!"
    assert not (dh_sets["train"] & dh_sets["test"]), "dHash leak between train and test!"
    assert not (dh_sets["val"] & dh_sets["test"]), "dHash leak between val and test!"

    return splits


def extract_stem_cache(
    net: TwoStageLeafNet,
    records: list,
    crop_to_idx: Dict[str, int],
    prob_to_idx: Dict[str, int],
    jitter_seed_base: int = 0,
    batch_size: int = 128,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Runs frozen `net.stem` once over `records` using threaded image loading, returning (mid_fp16, y_crop, y_prob)."""
    net.eval()
    n = len(records)
    mid_chunks = []
    y_crop = torch.zeros(n, dtype=torch.long)
    y_prob = torch.zeros(n, dtype=torch.long)

    for idx, r in enumerate(records):
        y_crop[idx] = crop_to_idx[r[2]["crop"]]
        y_prob[idx] = prob_to_idx[r[1]]

    with ThreadPoolExecutor(max_workers=8) as pool, torch.no_grad():
        for start in range(0, n, batch_size):
            batch_recs = records[start:start + batch_size]
            if jitter_seed_base > 0:
                args = [(r[0], jitter_seed_base + start + i + 1) for i, r in enumerate(batch_recs)]
            else:
                args = [(r[0], 0) for r in batch_recs]
            imgs = list(pool.map(lambda a: load_rgb_224(a[0], a[1]), args))
            x = torch.from_numpy(np.stack(imgs, axis=0))
            mid = net.forward_stem(x).to(torch.float16)
            mid_chunks.append(mid)

    return torch.cat(mid_chunks, dim=0), y_crop, y_prob


def fit_temperature(logits: np.ndarray, targets: np.ndarray) -> float:
    """Finds positive scalar temperature T minimizing NLL on validation logits."""
    best_t = 1.0
    best_nll = float("inf")
    for t in np.linspace(0.35, 3.0, 107):
        scaled = logits / t
        scaled = scaled - scaled.max(axis=1, keepdims=True)
        log_probs = scaled - np.log(np.exp(scaled).sum(axis=1, keepdims=True))
        nll = float(-log_probs[np.arange(len(targets)), targets].mean())
        if nll < best_nll:
            best_nll = nll
            best_t = float(t)
    return round(best_t, 4)


def compute_ece(probs: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    conf = probs.max(axis=1)
    ece = 0.0
    n = len(conf)
    if n == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (conf > lo) & (conf <= hi) if b > 0 else (conf >= lo) & (conf <= hi)
        if mask.any():
            ece += (mask.sum() / n) * abs(float(correct[mask].mean()) - float(conf[mask].mean()))
    return round(float(ece), 4)


def calibrate_precision_threshold(conf: np.ndarray, correct: np.ndarray, target_precision: float, fallback: float) -> float:
    """Picks lowest threshold >= 0.55 achieving `target_precision` on val with at least 5% coverage."""
    min_count = max(10, int(0.05 * len(conf)))
    best = fallback
    for thr in np.linspace(0.55, 0.96, 83):
        mask = conf >= thr
        if mask.sum() >= min_count and float(correct[mask].mean()) >= target_precision:
            best = float(thr)
            break
    return round(best, 4)


def softmax_np(x: np.ndarray, axis: int = -1) -> np.ndarray:
    z = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(z)
    return e / np.sum(e, axis=axis, keepdims=True)


def prf_metrics(y_true: List[int], y_pred: List[int], label_names: List[str]) -> Tuple[Dict[str, dict], float, float]:
    per_label = {}
    f1s = []
    weighted_sum = 0.0
    total = max(len(y_true), 1)
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    for idx, name in enumerate(label_names):
        tp = int(((yt == idx) & (yp == idx)).sum())
        fp = int(((yt != idx) & (yp == idx)).sum())
        fn = int(((yt == idx) & (yp != idx)).sum())
        sup = int((yt == idx).sum())
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
        per_label[name] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "support": sup,
        }
        if sup > 0:
            f1s.append(f1)
            weighted_sum += f1 * sup
    macro_f1 = round(float(np.mean(f1s)) if f1s else 0.0, 4)
    weighted_f1 = round(float(weighted_sum / total), 4)
    return per_label, macro_f1, weighted_f1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="jawadali1045/20k-multi-class-crop-disease-images")
    ap.add_argument("--epochs", type=int, default=18)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1.6e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--onnx-out", default=str(REPO_ROOT / "backend" / "app" / "ml" / "agro_two_stage_v1.onnx"))
    ap.add_argument("--meta-out", default=str(REPO_ROOT / "backend" / "app" / "ml" / "agro_two_stage_v1_meta.json"))
    ap.add_argument("--report-out", default=str(THIS_DIR / "model_eval_report.json"))
    args = ap.parse_args()

    t_start = time.time()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(max(4, min(8, os.cpu_count() or 4)))

    import kagglehub
    dataset_root = Path(kagglehub.dataset_download(args.dataset))
    print(f"[1/6] Scanning & deduplicating dataset at {dataset_root}...")
    clean_by_key, audit = scan_and_deduplicate(dataset_root)

    # Filter classes with >= 20 clean unique images
    clean_by_key = {k: v for k, v in clean_by_key.items() if len(v) >= 20}
    problem_keys = sorted(clean_by_key.keys())
    crops = sorted({clean_by_key[k][0][2]["crop"] for k in problem_keys})
    crop_to_idx = {c: i for i, c in enumerate(crops)}
    prob_to_idx = {k: i for i, k in enumerate(problem_keys)}

    crop_to_prob_indices: Dict[str, List[int]] = {c: [] for c in crops}
    problem_meta: List[dict] = []
    for i, k in enumerate(problem_keys):
        tax = clean_by_key[k][0][2]
        c = tax["crop"]
        crop_to_prob_indices[c].append(i)
        cult = DEFAULT_CULTURAL_BY_CATEGORY.get(tax["category"], DEFAULT_CULTURAL_BY_CATEGORY["fungal"])
        problem_meta.append({
            "index": i,
            "canonical_key": k,
            "crop": c,
            "crop_scientific": CROP_SCIENTIFIC[c],
            "problem": tax["problem"],
            "category": tax["category"],
            "scientific_name": tax["scientific_name"],
            "affected_parts": tax["affected_parts"],
            "typical_symptoms": tax["typical_symptoms"],
            "organic_measures": cult["organic"],
            "prevention": cult["prevention"],
        })

    splits = stratified_group_split(clean_by_key, seed=args.seed)
    print(
        f"[2/6] Leakage-free split ready: train={len(splits['train'])}, "
        f"val={len(splits['val'])}, test={len(splits['test'])} across {len(crops)} crops / {len(problem_keys)} classes."
    )

    net = TwoStageLeafNet(num_crops=len(crops), num_problems=len(problem_keys))

    print("[3/6] Extracting frozen early-stem feature caches (clean + augmented view)...")
    t_cache = time.time()
    mid_tr_clean, yc_tr, yp_tr = extract_stem_cache(net, splits["train"], crop_to_idx, prob_to_idx, jitter_seed_base=0)
    mid_tr_aug, yc_tr_aug, yp_tr_aug = extract_stem_cache(net, splits["train"], crop_to_idx, prob_to_idx, jitter_seed_base=100_000)
    mid_val, yc_val, yp_val = extract_stem_cache(net, splits["val"], crop_to_idx, prob_to_idx, jitter_seed_base=0)
    print(f"      Stem caches built in {time.time() - t_cache:.1f}s.")

    mid_train_all = torch.cat([mid_tr_clean, mid_tr_aug], dim=0)
    yc_train_all = torch.cat([yc_tr, yc_tr_aug], dim=0)
    yp_train_all = torch.cat([yp_tr, yp_tr_aug], dim=0)

    # Inverse-sqrt class weights for balanced learning across imbalanced classes
    crop_counts = torch.bincount(yc_tr, minlength=len(crops)).float().clamp(min=1.0)
    crop_weights = (1.0 / torch.sqrt(crop_counts))
    crop_weights = crop_weights / crop_weights.mean()

    prob_counts = torch.bincount(yp_tr, minlength=len(problem_keys)).float().clamp(min=1.0)
    prob_weights = (1.0 / torch.sqrt(prob_counts))
    prob_weights = prob_weights / prob_weights.mean()

    # Boolean mask [num_crops, num_problems] for crop-conditioned Stage B training
    crop_prob_mask = torch.zeros((len(crops), len(problem_keys)), dtype=torch.bool)
    for c_name, p_idxs in crop_to_prob_indices.items():
        crop_prob_mask[crop_to_idx[c_name], p_idxs] = True

    trainable_params = [p for p in net.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=args.lr, weight_decay=1.5e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)

    best_val_score = -1.0
    best_state = None
    n_train = mid_train_all.size(0)

    print(f"[4/6] Fine-tuning high-level SE blocks + Stage A & Stage B heads for {args.epochs} epochs...")
    for epoch in range(1, args.epochs + 1):
        net.top.train()
        net.crop_head.train()
        net.problem_head.train()
        perm = torch.randperm(n_train)
        running_loss = 0.0

        for start in range(0, n_train, args.batch_size):
            idx = perm[start:start + args.batch_size]
            mb = mid_train_all[idx].float()
            yc = yc_train_all[idx]
            yp = yp_train_all[idx]

            optimizer.zero_grad()
            _, crop_logits, prob_logits = net.forward_from_mid(mb)

            loss_crop = F.cross_entropy(crop_logits, yc, weight=crop_weights, label_smoothing=0.04)
            loss_prob_global = F.cross_entropy(prob_logits, yp, weight=prob_weights, label_smoothing=0.04)

            allowed = crop_prob_mask[yc]
            masked_prob_logits = prob_logits.masked_fill(~allowed, -1e4)
            loss_prob_within = F.cross_entropy(masked_prob_logits, yp, weight=prob_weights, label_smoothing=0.03)

            loss = loss_crop + 0.5 * loss_prob_global + 1.0 * loss_prob_within
            loss.backward()
            optimizer.step()
            running_loss += float(loss.item()) * len(idx)

        scheduler.step()

        # Evaluate on held-out val split
        net.eval()
        with torch.no_grad():
            val_crop_logits_l, val_prob_logits_l = [], []
            for s in range(0, mid_val.size(0), 256):
                _, cl, pl = net.forward_from_mid(mid_val[s:s + 256].float())
                val_crop_logits_l.append(cl)
                val_prob_logits_l.append(pl)
            vcl = torch.cat(val_crop_logits_l, dim=0)
            vpl = torch.cat(val_prob_logits_l, dim=0)
            pred_c = vcl.argmax(dim=1)
            allowed_v = crop_prob_mask[pred_c]
            pred_p = vpl.masked_fill(~allowed_v, -1e9).argmax(dim=1)
            crop_acc = float((pred_c == yc_val).float().mean().item())
            e2e_acc = float(((pred_c == yc_val) & (pred_p == yp_val)).float().mean().item())
            _, val_macro_f1, _ = prf_metrics(yp_val.tolist(), pred_p.tolist(), problem_keys)

        score = 0.5 * val_macro_f1 + 0.5 * e2e_acc
        if score > best_val_score:
            best_val_score = score
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}

        if epoch in (1, 5, 10, 14, args.epochs):
            print(
                f"      Epoch {epoch:02d}/{args.epochs} | loss={running_loss / n_train:.4f} | "
                f"val_crop_acc={crop_acc:.4f} | val_e2e_acc={e2e_acc:.4f} | val_macro_f1={val_macro_f1:.4f}"
            )

    assert best_state is not None
    net.load_state_dict(best_state)
    net.eval()

    print("[5/6] Computing class prototypes, Temperature Scaling, and OOD thresholds on held-out val split...")
    with torch.no_grad():
        # Compute L2-normalized class prototypes from clean training features
        tr_embs = []
        for s in range(0, mid_tr_clean.size(0), 256):
            emb, _, _ = net.forward_from_mid(mid_tr_clean[s:s + 256].float())
            tr_embs.append(emb)
        tr_embs_all = torch.cat(tr_embs, dim=0).numpy()
        yc_tr_np = yc_tr.numpy()
        yp_tr_np = yp_tr.numpy()

        prototypes = np.zeros((len(problem_keys), 576), dtype=np.float32)
        for p_idx in range(len(problem_keys)):
            vec = tr_embs_all[yp_tr_np == p_idx].mean(axis=0)
            norm = np.linalg.norm(vec) + 1e-8
            prototypes[p_idx] = vec / norm

        # Validation forward pass
        val_embs, val_cl, val_pl = [], [], []
        for s in range(0, mid_val.size(0), 256):
            emb, cl, pl = net.forward_from_mid(mid_val[s:s + 256].float())
            val_embs.append(emb)
            val_cl.append(cl)
            val_pl.append(pl)
        val_embs_np = torch.cat(val_embs, dim=0).numpy()
        val_cl_np = torch.cat(val_cl, dim=0).numpy()
        val_pl_np = torch.cat(val_pl, dim=0).numpy()

    yc_val_np = yc_val.numpy()
    yp_val_np = yp_val.numpy()

    # Temperature scaling for Stage A (crop)
    t_crop = fit_temperature(val_cl_np, yc_val_np)

    # Temperature scaling for Stage B (within true-crop masked logits)
    masked_val_pl = np.full_like(val_pl_np, -1e4)
    for row_i, c_i in enumerate(yc_val_np):
        idxs = crop_to_prob_indices[crops[int(c_i)]]
        masked_val_pl[row_i, idxs] = val_pl_np[row_i, idxs]
    t_prob = fit_temperature(masked_val_pl, yp_val_np)

    # Calibrate HIGH / MODERATE probability cutoffs on validation set
    val_crop_probs = softmax_np(val_cl_np / t_crop, axis=1)
    val_crop_pred = val_crop_probs.argmax(axis=1)
    val_crop_conf = val_crop_probs.max(axis=1)
    val_crop_ok = (val_crop_pred == yc_val_np).astype(np.float32)

    crop_high_thr = calibrate_precision_threshold(val_crop_conf, val_crop_ok, target_precision=0.94, fallback=0.80)
    crop_mod_thr = round(min(crop_high_thr - 0.12, 0.55), 4)
    crop_mod_thr = max(0.45, crop_mod_thr)

    # End-to-end masked Stage B probabilities on val
    val_pred_masked_pl = np.full_like(val_pl_np, -1e9)
    for row_i, c_i in enumerate(val_crop_pred):
        idxs = crop_to_prob_indices[crops[int(c_i)]]
        val_pred_masked_pl[row_i, idxs] = val_pl_np[row_i, idxs]
    val_prob_probs = softmax_np(val_pred_masked_pl / t_prob, axis=1)
    val_prob_pred = val_prob_probs.argmax(axis=1)
    val_prob_conf = val_prob_probs.max(axis=1)
    val_e2e_ok = ((val_crop_pred == yc_val_np) & (val_prob_pred == yp_val_np)).astype(np.float32)

    prob_high_thr = calibrate_precision_threshold(val_prob_conf, val_e2e_ok, target_precision=0.90, fallback=0.82)
    prob_mod_thr = round(min(prob_high_thr - 0.15, 0.52), 4)
    prob_mod_thr = max(0.42, prob_mod_thr)

    # Calibrate OOD prototype cosine threshold using val plants vs synthetic non-plant val set
    val_plant_cos = (val_embs_np @ prototypes.T).max(axis=1)
    ood_val_jpegs = make_non_plant_synthetic_images(count=80, seed=args.seed + 7)
    ood_val_tensors = []
    for jb in ood_val_jpegs:
        im = Image.open(io.BytesIO(jb)).convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        ood_val_tensors.append(np.transpose(np.asarray(im, dtype=np.float32) / 255.0, (2, 0, 1)))
    with torch.no_grad():
        ood_emb, _, _ = net(torch.from_numpy(np.stack(ood_val_tensors, axis=0)))
        ood_val_cos = (ood_emb.numpy() @ prototypes.T).max(axis=1)

    q_plant_01 = float(np.quantile(val_plant_cos, 0.015))
    q_plant_03 = float(np.quantile(val_plant_cos, 0.03))
    q_plant_12 = float(np.quantile(val_plant_cos, 0.12))
    q_ood_98 = float(np.quantile(ood_val_cos, 0.98))
    ood_cos_thr = round(float(max(min(q_plant_01, 0.68), min(q_ood_98 + 0.02, 0.66))), 4)
    in_domain_mod_cos = round(float(max(ood_cos_thr + 0.03, q_plant_03)), 4)
    in_domain_high_cos = round(float(max(in_domain_mod_cos + 0.04, q_plant_12)), 4)
    print(
        f"      Calibration: T_crop={t_crop}, T_prob={t_prob} | crop_thr=({crop_mod_thr}, {crop_high_thr}) | "
        f"prob_thr=({prob_mod_thr}, {prob_high_thr}) | ood_cos_thr={ood_cos_thr} "
        f"(val_plant_p015={q_plant_01:.3f}, val_ood_p98={q_ood_98:.3f}, mod_cos={in_domain_mod_cos}, hi_cos={in_domain_high_cos})"
    )

    # Export single-file ONNX model (no external .data file)
    onnx_path = Path(args.onnx_out)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, 3, 224, 224, dtype=torch.float32)
    torch.onnx.export(
        net,
        dummy,
        str(onnx_path),
        input_names=["input_rgb_01"],
        output_names=["emb_norm", "crop_logits", "problem_logits"],
        dynamic_axes={
            "input_rgb_01": {0: "batch"},
            "emb_norm": {0: "batch"},
            "crop_logits": {0: "batch"},
            "problem_logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )
    # If exporter created an external data sidecar, consolidate inline into one ONNX file
    import onnx
    model_proto = onnx.load(str(onnx_path), load_external_data=True)
    data_sidecar = Path(str(onnx_path) + ".data")
    onnx.save_model(model_proto, str(onnx_path), save_as_external_data=False)
    if data_sidecar.exists():
        data_sidecar.unlink()
    onnx_size_mb = round(onnx_path.stat().st_size / (1024 * 1024), 2)
    print(f"      Exported self-contained ONNX model -> {onnx_path} ({onnx_size_mb} MB)")

    # [6/6] Unbiased End-to-End Evaluation on Untouched 15% Test Split via ONNXRuntime!
    print(f"[6/6] Evaluating exported ONNX model on untouched held-out test split (n={len(splits['test'])})...")
    import onnxruntime as ort
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    test_recs = splits["test"]
    test_embs_l, test_cl_l, test_pl_l = [], [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for s in range(0, len(test_recs), 128):
            batch = test_recs[s:s + 128]
            imgs = list(pool.map(lambda r: load_rgb_224(r[0], 0), batch))
            x_np = np.stack(imgs, axis=0)
            emb_b, cl_b, pl_b = sess.run(None, {"input_rgb_01": x_np})
            test_embs_l.append(emb_b)
            test_cl_l.append(cl_b)
            test_pl_l.append(pl_b)

    test_embs = np.concatenate(test_embs_l, axis=0)
    test_cl = np.concatenate(test_cl_l, axis=0)
    test_pl = np.concatenate(test_pl_l, axis=0)

    yt_crop = np.array([crop_to_idx[r[2]["crop"]] for r in test_recs], dtype=np.int64)
    yt_prob = np.array([prob_to_idx[r[1]] for r in test_recs], dtype=np.int64)

    # Uncalibrated vs calibrated ECE on Stage A & Stage B
    uncal_crop_probs = softmax_np(test_cl, axis=1)
    cal_crop_probs = softmax_np(test_cl / t_crop, axis=1)
    pred_crop = cal_crop_probs.argmax(axis=1)
    conf_crop = cal_crop_probs.max(axis=1)
    cos_sims_test = test_embs @ prototypes.T
    cos_plant = cos_sims_test.max(axis=1)

    masked_test_pl_uncal = np.full_like(test_pl, -1e9)
    masked_test_pl_cal = np.full_like(test_pl, -1e9)
    oracle_masked_pl = np.full_like(test_pl, -1e9)
    for i in range(len(test_recs)):
        pred_idxs = crop_to_prob_indices[crops[int(pred_crop[i])]]
        true_idxs = crop_to_prob_indices[crops[int(yt_crop[i])]]
        masked_test_pl_uncal[i, pred_idxs] = test_pl[i, pred_idxs]
        masked_test_pl_cal[i, pred_idxs] = test_pl[i, pred_idxs] / t_prob
        oracle_masked_pl[i, true_idxs] = test_pl[i, true_idxs] / t_prob

    uncal_prob_probs = softmax_np(masked_test_pl_uncal, axis=1)
    cal_prob_probs = softmax_np(masked_test_pl_cal, axis=1)
    oracle_prob_probs = softmax_np(oracle_masked_pl, axis=1)

    pred_prob = cal_prob_probs.argmax(axis=1)
    oracle_pred_prob = oracle_prob_probs.argmax(axis=1)
    conf_prob = cal_prob_probs.max(axis=1)

    crop_ok_arr = (pred_crop == yt_crop)
    e2e_ok_arr = crop_ok_arr & (pred_prob == yt_prob)
    oracle_ok_arr = (oracle_pred_prob == yt_prob)

    ece_crop_before = compute_ece(uncal_crop_probs, crop_ok_arr.astype(np.float32))
    ece_crop_after = compute_ece(cal_crop_probs, crop_ok_arr.astype(np.float32))
    ece_prob_before = compute_ece(uncal_prob_probs, e2e_ok_arr.astype(np.float32))
    ece_prob_after = compute_ece(cal_prob_probs, e2e_ok_arr.astype(np.float32))

    per_crop_metrics, crop_macro_f1, crop_weighted_f1 = prf_metrics(yt_crop.tolist(), pred_crop.tolist(), crops)
    per_prob_metrics, prob_macro_f1, prob_weighted_f1 = prf_metrics(yt_prob.tolist(), pred_prob.tolist(), problem_keys)

    # Evaluate categorical gate outcomes on held-out test set
    cat_counts = collections.Counter()
    high_total = 0
    high_wrong = 0
    healthy_total = 0
    healthy_false_diag = 0

    for i in range(len(test_recs)):
        c_name = crops[int(pred_crop[i])]
        p_meta = problem_meta[int(pred_prob[i])]
        true_meta = problem_meta[int(yt_prob[i])]

        # Mirror runtime categorical gating in local_specialist_vision.py
        pred_crop_pidxs = crop_to_prob_indices[c_name]
        crop_proto_cos = float(np.max(cos_sims_test[i, pred_crop_pidxs]))
        best_proto_cos = float(cos_sims_test[i, int(pred_prob[i])])

        if cos_plant[i] < ood_cos_thr:
            cat = "LOW"
            status_i = "not_a_plant"
        elif conf_crop[i] < crop_mod_thr or crop_proto_cos < in_domain_mod_cos:
            cat = "LOW"
            status_i = "needs_crop_confirmation"
        else:
            c_lvl = 2 if (conf_crop[i] >= crop_high_thr and crop_proto_cos >= in_domain_high_cos) else 1
            if conf_prob[i] < prob_mod_thr or best_proto_cos < (ood_cos_thr + 0.04):
                p_lvl = 0
            elif conf_prob[i] >= prob_high_thr and best_proto_cos >= in_domain_high_cos:
                p_lvl = 2
            else:
                p_lvl = 1
            lvl = min(c_lvl, p_lvl)
            if not CROP_HAS_HEALTHY_CLASS.get(c_name, True):
                lvl = min(lvl, 1)  # Rice capped at MODERATE in standalone local mode
            cat = {0: "LOW", 1: "MODERATE", 2: "HIGH"}[lvl]
            status_i = "low_confidence" if lvl == 0 else ("moderate_confidence" if lvl == 1 else "ok")

        cat_counts[status_i] += 1
        if cat == "HIGH":
            high_total += 1
            if not e2e_ok_arr[i]:
                high_wrong += 1
        if true_meta["category"] == "healthy":
            healthy_total += 1
            if status_i in ("ok", "moderate_confidence") and p_meta["category"] != "healthy":
                healthy_false_diag += 1

    # Evaluate held-out OOD non-plant test images (80 fresh unseen non-plant images)
    ood_test_jpegs = make_non_plant_synthetic_images(count=80, seed=args.seed + 999)
    ood_test_imgs = []
    for jb in ood_test_jpegs:
        im = Image.open(io.BytesIO(jb)).convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        ood_test_imgs.append(np.transpose(np.asarray(im, dtype=np.float32) / 255.0, (2, 0, 1)))
    ood_emb_t, ood_cl_t, _ = sess.run(None, {"input_rgb_01": np.stack(ood_test_imgs, axis=0)})
    ood_cos_t = (ood_emb_t @ prototypes.T).max(axis=1)
    ood_crop_conf_t = softmax_np(ood_cl_t / t_crop, axis=1).max(axis=1)
    ood_rejected = int(((ood_cos_t < ood_cos_thr) | (ood_crop_conf_t < crop_mod_thr)).sum())

    summary_metrics = {
        "test_samples": len(test_recs),
        "stage_a_plant_id_accuracy": round(float(crop_ok_arr.mean()), 4),
        "stage_a_crop_macro_f1": crop_macro_f1,
        "stage_a_crop_weighted_f1": crop_weighted_f1,
        "stage_b_end_to_end_accuracy": round(float(e2e_ok_arr.mean()), 4),
        "stage_b_oracle_crop_accuracy": round(float(oracle_ok_arr.mean()), 4),
        "stage_b_macro_f1": prob_macro_f1,
        "stage_b_weighted_f1": prob_weighted_f1,
        "false_diagnosis_rate_on_healthy": round(healthy_false_diag / healthy_total, 4) if healthy_total else None,
        "false_high_confidence_rate": round(high_wrong / high_total, 4) if high_total else 0.0,
        "high_confidence_coverage": round(high_total / len(test_recs), 4),
        "ece_crop_before_temp_scaling": ece_crop_before,
        "ece_crop_after_temp_scaling": ece_crop_after,
        "ece_problem_before_temp_scaling": ece_prob_before,
        "ece_problem_after_temp_scaling": ece_prob_after,
        "ood_non_plant_test_count": len(ood_test_jpegs),
        "ood_non_plant_rejection_rate": round(ood_rejected / len(ood_test_jpegs), 4),
        "test_gate_status_distribution": dict(cat_counts),
    }

    # Save compact metadata JSON alongside ONNX model (prototypes encoded in float16 base64 -> ~45 KB)
    proto_fp16_b64 = base64.b64encode(prototypes.astype(np.float16).tobytes()).decode("ascii")
    meta_payload = {
        "model_id": "agro-two-stage-mobilenetv3s-v1",
        "architecture": "MobileNetV3-Small Dual-Head (Stage A Crop + Stage B Crop-Conditioned Disease/Pest/Healthy)",
        "dataset": args.dataset,
        "dataset_scope_note": (
            "Trained on deduplicated 70/15/15 split of jawadali1045/20k-multi-class-crop-disease-images "
            "(5 crops, 40 classes). Community Kaggle dataset; Rice lacks a Healthy folder so standalone "
            "Rice predictions are capped at MODERATE confidence."
        ),
        "onnx_filename": onnx_path.name,
        "onnx_size_mb": onnx_size_mb,
        "input_size": 224,
        "embedding_dim": 576,
        "crops": crops,
        "crop_scientific": CROP_SCIENTIFIC,
        "crop_visible_features": CROP_VISIBLE_FEATURES,
        "crop_has_healthy_class": CROP_HAS_HEALTHY_CLASS,
        "crop_to_problem_indices": crop_to_prob_indices,
        "problems": problem_meta,
        "prototypes_fp16_b64": proto_fp16_b64,
        "calibration": {
            "T_crop": t_crop,
            "T_problem": t_prob,
            "ood_cosine_threshold": ood_cos_thr,
            "in_domain_mod_cosine": in_domain_mod_cos,
            "in_domain_high_cosine": in_domain_high_cos,
            "crop_high_prob": crop_high_thr,
            "crop_mod_prob": crop_mod_thr,
            "problem_high_prob": prob_high_thr,
            "problem_mod_prob": prob_mod_thr,
        },
        "held_out_test_metrics": summary_metrics,
    }
    Path(args.meta_out).write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

    eval_report = {
        "model_id": meta_payload["model_id"],
        "evaluated_at_epoch_seconds": round(time.time() - t_start, 1),
        "dataset": args.dataset,
        "split_counts": {k: len(v) for k, v in splits.items()},
        "zero_leakage_verified": {"md5_exact": True, "dhash_perceptual_8x8": True},
        "dataset_hygiene_audit": audit,
        "calibration": meta_payload["calibration"],
        "summary_metrics": summary_metrics,
        "per_crop_test_metrics": per_crop_metrics,
        "per_problem_test_metrics": per_prob_metrics,
        "known_limitations": [
            "Covers 5 crops (Cotton, Maize, Rice, Sugarcane, Wheat) across 40 classes; photos of other crops (e.g. Tomato, Ragi, Chilli, Coconut) require Cloud Vision VLM or will request crop confirmation / abstain.",
            "Raw Kaggle dataset has no 'Healthy Rice' folder; standalone local Rice predictions are capped at MODERATE confidence and include 'Healthy Rice leaf' as an explicit alternative.",
            "Public Kaggle dataset contains community-curated photos (including occasional extension-slide overlays) rather than KVK-audited Karnataka field photos.",
        ],
    }
    Path(args.report_out).write_text(json.dumps(eval_report, indent=2), encoding="utf-8")
    print("\n=== HELD-OUT 15% TEST SPLIT SUMMARY (ONNXRUNTIME) ===")
    print(json.dumps(summary_metrics, indent=2))
    print(f"Saved report -> {args.report_out}")


if __name__ == "__main__":
    main()
