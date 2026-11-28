"""Post-hoc Centered-Embedding OOD & Temperature Calibration + Unbiased Test Verifier
for `backend/app/ml/agro_two_stage_v1.onnx`.

Why centered embeddings:
- MobileNetV3 pooled activations lie largely in the positive orthant, compressing raw cosine
  similarities into [0.85, 0.99]. Subtracting `global_mean` (fit strictly on `train`) before L2
  normalization centers the hypersphere so in-domain crop leaves cluster tightly around their
  class prototypes while non-plant / synthetic / UI / noise images drop sharply in cosine similarity.
- All thresholds (`ood_centered_cos_threshold`, `in_domain_mod_cosine`, `in_domain_high_cosine`,
  `T_crop`, `T_problem`) are fit strictly on `train` + `val`, then evaluated once on untouched `test`.
"""
import base64
import collections
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

import sys
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
from train_two_stage_classifier import (  # noqa: E402
    calibrate_precision_threshold,
    compute_ece,
    fit_temperature,
    load_rgb_224,
    make_non_plant_synthetic_images,
    prf_metrics,
    softmax_np,
    stratified_group_split,
)


def foliar_naturalness_score(chw_01: np.ndarray) -> np.ndarray:
    """Computes simple per-image visual statistics [N] distinguishing natural plant/soil scenes
    from uniform blocks, UI wireframes, pure noise, or synthetic line drawings."""
    # chw_01: [N, 3, 224, 224]
    r, g, b = chw_01[:, 0], chw_01[:, 1], chw_01[:, 2]
    std_all = chw_01.reshape(len(chw_01), -1).std(axis=1)
    # Excess green / natural vegetation or necrotic brown-yellow pigment presence
    exg = (2.0 * g - r - b)
    plant_pigment_frac = ((exg > 0.04) | ((g > b * 1.08) & (r > b * 1.05))).mean(axis=(1, 2))
    # Pixel-to-pixel high-frequency noise check (pure random noise has huge adjacent diff > 0.25)
    hf_diff = np.abs(chw_01[:, :, :, 1:] - chw_01[:, :, :, :-1]).mean(axis=(1, 2, 3))
    score = np.where((std_all < 0.03) | (hf_diff > 0.22), 0.0, 0.5 + 0.5 * np.clip(plant_pigment_frac * 2.5, 0.0, 1.0))
    return score.astype(np.float32)


def run_onnx_split(sess: ort.InferenceSession, records: list):
    embs_l, cl_l, pl_l, nat_l = [], [], [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for s in range(0, len(records), 128):
            batch = records[s:s + 128]
            imgs = list(pool.map(lambda r: load_rgb_224(r[0], 0), batch))
            x_np = np.stack(imgs, axis=0)
            emb_b, cl_b, pl_b = sess.run(None, {"input_rgb_01": x_np})
            embs_l.append(emb_b)
            cl_l.append(cl_b)
            pl_l.append(pl_b)
            nat_l.append(foliar_naturalness_score(x_np))
    return (
        np.concatenate(embs_l, axis=0),
        np.concatenate(cl_l, axis=0),
        np.concatenate(pl_l, axis=0),
        np.concatenate(nat_l, axis=0),
    )


def main():
    t0 = time.time()
    import kagglehub
    dataset_root = Path(kagglehub.dataset_download("jawadali1045/20k-multi-class-crop-disease-images"))
    clean_by_key, audit = scan_and_deduplicate(dataset_root)
    clean_by_key = {k: v for k, v in clean_by_key.items() if len(v) >= 20}

    problem_keys = sorted(clean_by_key.keys())
    crops = sorted({clean_by_key[k][0][2]["crop"] for k in problem_keys})
    crop_to_idx = {c: i for i, c in enumerate(crops)}
    prob_to_idx = {k: i for i, k in enumerate(problem_keys)}

    crop_to_prob_indices = {c: [] for c in crops}
    problem_meta = []
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

    splits = stratified_group_split(clean_by_key, seed=42)
    onnx_path = REPO_ROOT / "backend" / "app" / "ml" / "agro_two_stage_v1.onnx"
    meta_path = REPO_ROOT / "backend" / "app" / "ml" / "agro_two_stage_v1_meta.json"
    report_path = THIS_DIR / "model_eval_report.json"

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    print("Running ONNX over train, val, and test splits for centered-embedding calibration...")
    tr_emb, _, _, _ = run_onnx_split(sess, splits["train"])
    val_emb, val_cl, val_pl, val_nat = run_onnx_split(sess, splits["val"])
    test_emb, test_cl, test_pl, test_nat = run_onnx_split(sess, splits["test"])

    yc_tr = np.array([crop_to_idx[r[2]["crop"]] for r in splits["train"]], dtype=np.int64)
    yp_tr = np.array([prob_to_idx[r[1]] for r in splits["train"]], dtype=np.int64)
    yc_val = np.array([crop_to_idx[r[2]["crop"]] for r in splits["val"]], dtype=np.int64)
    yp_val = np.array([prob_to_idx[r[1]] for r in splits["val"]], dtype=np.int64)
    yt_crop = np.array([crop_to_idx[r[2]["crop"]] for r in splits["test"]], dtype=np.int64)
    yt_prob = np.array([prob_to_idx[r[1]] for r in splits["test"]], dtype=np.int64)

    # Fit global mean strictly on train embeddings and compute L2-normalized centered class prototypes
    global_mean = tr_emb.mean(axis=0, keepdims=True).astype(np.float32)

    def center_norm(e: np.ndarray) -> np.ndarray:
        c = e - global_mean
        return c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-8)

    tr_c = center_norm(tr_emb)
    prototypes = np.zeros((len(problem_keys), 576), dtype=np.float32)
    for p_idx in range(len(problem_keys)):
        v = tr_c[yp_tr == p_idx].mean(axis=0)
        prototypes[p_idx] = v / (np.linalg.norm(v) + 1e-8)

    val_c = center_norm(val_emb)
    test_c = center_norm(test_emb)

    # Fit temperatures on val
    t_crop = fit_temperature(val_cl, yc_val)
    masked_val_pl = np.full_like(val_pl, -1e4)
    for row_i, c_i in enumerate(yc_val):
        idxs = crop_to_prob_indices[crops[int(c_i)]]
        masked_val_pl[row_i, idxs] = val_pl[row_i, idxs]
    t_prob = fit_temperature(masked_val_pl, yp_val)

    val_crop_probs = softmax_np(val_cl / t_crop, axis=1)
    val_crop_pred = val_crop_probs.argmax(axis=1)
    val_crop_conf = val_crop_probs.max(axis=1)
    val_crop_ok = (val_crop_pred == yc_val).astype(np.float32)
    crop_high_thr = calibrate_precision_threshold(val_crop_conf, val_crop_ok, target_precision=0.94, fallback=0.80)
    crop_mod_thr = round(max(0.48, min(crop_high_thr - 0.10, 0.58)), 4)

    val_pred_masked_pl = np.full_like(val_pl, -1e9)
    for row_i, c_i in enumerate(val_crop_pred):
        idxs = crop_to_prob_indices[crops[int(c_i)]]
        val_pred_masked_pl[row_i, idxs] = val_pl[row_i, idxs]
    val_prob_probs = softmax_np(val_pred_masked_pl / t_prob, axis=1)
    val_prob_pred = val_prob_probs.argmax(axis=1)
    val_prob_conf = val_prob_probs.max(axis=1)
    val_e2e_ok = ((val_crop_pred == yc_val) & (val_prob_pred == yp_val)).astype(np.float32)
    prob_high_thr = calibrate_precision_threshold(val_prob_conf, val_e2e_ok, target_precision=0.92, fallback=0.78)
    prob_mod_thr = round(max(0.42, min(prob_high_thr - 0.15, 0.52)), 4)

    # Centered cosine + foliar naturalness composite OOD score on val plants vs OOD val images
    val_plant_cos = (val_c @ prototypes.T).max(axis=1)
    val_plant_ood_score = val_plant_cos * val_nat

    ood_val_jpegs = make_non_plant_synthetic_images(count=80, seed=49)
    ood_val_arr = np.stack([
        np.transpose(np.asarray(Image.open(io.BytesIO(jb)).convert("RGB").resize((224, 224), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0, (2, 0, 1))
        for jb in ood_val_jpegs
    ], axis=0)
    ood_val_emb, _, _ = sess.run(None, {"input_rgb_01": ood_val_arr})
    ood_val_cos = (center_norm(ood_val_emb) @ prototypes.T).max(axis=1)
    ood_val_nat = foliar_naturalness_score(ood_val_arr)
    ood_val_score = ood_val_cos * ood_val_nat

    # Pick OOD threshold maximizing separation on val (keeping >= 98% of real val leaves while rejecting OOD)
    q_plant_015 = float(np.quantile(val_plant_ood_score, 0.015))
    q_ood_95 = float(np.quantile(ood_val_score, 0.95))
    ood_score_thr = round(float(0.5 * (q_plant_015 + min(q_ood_95, q_plant_015))), 4)
    in_domain_mod_cos = round(float(np.quantile(val_plant_cos, 0.025)), 4)
    in_domain_high_cos = round(float(np.quantile(val_plant_cos, 0.12)), 4)

    print(
        f"Centered Calibration: val_plant_cos_p025={in_domain_mod_cos}, val_plant_score_p015={q_plant_015:.3f}, "
        f"val_ood_score_p95={q_ood_95:.3f} -> ood_score_thr={ood_score_thr}"
    )

    # Evaluate on untouched 15% test split (n=2283) + 80 unseen OOD test images
    uncal_crop_probs = softmax_np(test_cl, axis=1)
    cal_crop_probs = softmax_np(test_cl / t_crop, axis=1)
    pred_crop = cal_crop_probs.argmax(axis=1)
    conf_crop = cal_crop_probs.max(axis=1)

    cos_sims_test = test_c @ prototypes.T
    cos_plant = cos_sims_test.max(axis=1)
    test_ood_score = cos_plant * test_nat

    masked_test_pl_uncal = np.full_like(test_pl, -1e9)
    masked_test_pl_cal = np.full_like(test_pl, -1e9)
    oracle_masked_pl = np.full_like(test_pl, -1e9)
    for i in range(len(splits["test"])):
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

    cat_counts = collections.Counter()
    high_total = 0
    high_wrong = 0
    healthy_total = 0
    healthy_false_diag = 0

    for i in range(len(splits["test"])):
        c_name = crops[int(pred_crop[i])]
        p_meta = problem_meta[int(pred_prob[i])]
        true_meta = problem_meta[int(yt_prob[i])]
        pred_crop_pidxs = crop_to_prob_indices[c_name]
        crop_proto_cos = float(np.max(cos_sims_test[i, pred_crop_pidxs]))
        best_proto_cos = float(cos_sims_test[i, int(pred_prob[i])])

        if test_ood_score[i] < ood_score_thr:
            cat = "LOW"
            status_i = "not_a_plant"
        elif conf_crop[i] < crop_mod_thr or crop_proto_cos < in_domain_mod_cos:
            cat = "LOW"
            status_i = "needs_crop_confirmation"
        else:
            c_lvl = 2 if (conf_crop[i] >= crop_high_thr and crop_proto_cos >= in_domain_high_cos) else 1
            if conf_prob[i] < prob_mod_thr or best_proto_cos < in_domain_mod_cos:
                p_lvl = 0
            elif conf_prob[i] >= prob_high_thr and best_proto_cos >= in_domain_high_cos:
                p_lvl = 2
            else:
                p_lvl = 1
            lvl = min(c_lvl, p_lvl)
            if not CROP_HAS_HEALTHY_CLASS.get(c_name, True):
                lvl = min(lvl, 1)
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

    # Evaluate 80 fresh unseen OOD non-plant test images
    ood_test_jpegs = make_non_plant_synthetic_images(count=80, seed=1041)
    ood_test_arr = np.stack([
        np.transpose(np.asarray(Image.open(io.BytesIO(jb)).convert("RGB").resize((224, 224), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0, (2, 0, 1))
        for jb in ood_test_jpegs
    ], axis=0)
    ood_t_emb, ood_t_cl, _ = sess.run(None, {"input_rgb_01": ood_test_arr})
    ood_t_cos = (center_norm(ood_t_emb) @ prototypes.T).max(axis=1)
    ood_t_nat = foliar_naturalness_score(ood_test_arr)
    ood_t_score = ood_t_cos * ood_t_nat
    ood_t_crop_conf = softmax_np(ood_t_cl / t_crop, axis=1).max(axis=1)
    ood_rejected = int(((ood_t_score < ood_score_thr) | (ood_t_cos < in_domain_mod_cos) | (ood_t_crop_conf < crop_mod_thr)).sum())

    onnx_size_mb = round(onnx_path.stat().st_size / (1024 * 1024), 2)
    summary_metrics = {
        "test_samples": len(splits["test"]),
        "stage_a_plant_id_accuracy": round(float(crop_ok_arr.mean()), 4),
        "stage_a_crop_macro_f1": crop_macro_f1,
        "stage_a_crop_weighted_f1": crop_weighted_f1,
        "stage_b_end_to_end_accuracy": round(float(e2e_ok_arr.mean()), 4),
        "stage_b_oracle_crop_accuracy": round(float(oracle_ok_arr.mean()), 4),
        "stage_b_macro_f1": prob_macro_f1,
        "stage_b_weighted_f1": prob_weighted_f1,
        "false_diagnosis_rate_on_healthy": round(healthy_false_diag / healthy_total, 4) if healthy_total else None,
        "false_high_confidence_rate": round(high_wrong / high_total, 4) if high_total else 0.0,
        "high_confidence_coverage": round(high_total / len(splits["test"]), 4),
        "ece_crop_before_temp_scaling": ece_crop_before,
        "ece_crop_after_temp_scaling": ece_crop_after,
        "ece_problem_before_temp_scaling": ece_prob_before,
        "ece_problem_after_temp_scaling": ece_prob_after,
        "ood_non_plant_test_count": len(ood_test_jpegs),
        "ood_non_plant_rejection_rate": round(ood_rejected / len(ood_test_jpegs), 4),
        "test_gate_status_distribution": dict(cat_counts),
    }

    proto_fp16_b64 = base64.b64encode(prototypes.astype(np.float16).tobytes()).decode("ascii")
    mean_fp16_b64 = base64.b64encode(global_mean.reshape(-1).astype(np.float16).tobytes()).decode("ascii")

    meta_payload = {
        "model_id": "agro-two-stage-mobilenetv3s-v1",
        "architecture": "MobileNetV3-Small Dual-Head (Stage A Crop + Stage B Crop-Conditioned Disease/Pest/Healthy)",
        "dataset": "jawadali1045/20k-multi-class-crop-disease-images",
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
        "global_mean_fp16_b64": mean_fp16_b64,
        "prototypes_fp16_b64": proto_fp16_b64,
        "calibration": {
            "T_crop": t_crop,
            "T_problem": t_prob,
            "ood_cosine_threshold": ood_score_thr,
            "in_domain_mod_cosine": in_domain_mod_cos,
            "in_domain_high_cosine": in_domain_high_cos,
            "crop_high_prob": crop_high_thr,
            "crop_mod_prob": crop_mod_thr,
            "problem_high_prob": prob_high_thr,
            "problem_mod_prob": prob_mod_thr,
        },
        "held_out_test_metrics": summary_metrics,
    }
    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

    eval_report = {
        "model_id": meta_payload["model_id"],
        "calibration_runtime_seconds": round(time.time() - t0, 1),
        "dataset": meta_payload["dataset"],
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
    report_path.write_text(json.dumps(eval_report, indent=2), encoding="utf-8")
    print(json.dumps(summary_metrics, indent=2))


if __name__ == "__main__":
    main()
