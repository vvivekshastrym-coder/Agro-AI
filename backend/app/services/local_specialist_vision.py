"""Local Two-Stage Specialist Crop & Disease Vision Classifier (ONNXRuntime).

Trained on a deduplicated, perceptual-hash group-split (70/15/15) of
`jawadali1045/20k-multi-class-crop-disease-images` (5 crops, 40 classes).

Safety & Honesty Guarantees:
1. Two separate calibrated heads:
   - Stage A: Crop identification (`T_crop` temperature-scaled + prototype cosine OOD gate).
   - Stage B: Strictly masked to Stage A's identified/confirmed crop (`T_problem` temperature-scaled),
     so cross-crop disease mismatches are impossible.
2. Unsupported crops: if the farmer confirms a crop outside the 5 supported crops
   (Cotton, Maize, Rice, Sugarcane, Wheat), Stage B abstains (`Unable to identify`, `low` confidence)
   rather than applying another crop's disease labels.
3. Missing Healthy Rice guard: because the training dataset lacks a `Healthy Rice` folder, standalone
   Rice predictions are capped at `medium` (`MODERATE`) confidence and always include `Healthy Rice leaf`
   in `alternatives`.
4. Non-plant / out-of-distribution inputs: rejected via 576-d penultimate prototype cosine similarity.
"""
import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .diagnosis_engine import crops_match

logger = logging.getLogger(__name__)

_DEFAULT_ML_DIR = Path(__file__).resolve().parent.parent / "ml"
_SESSION_CACHE: Dict[str, Any] = {"loaded_path": None, "session": None, "meta": None, "prototypes": None}


def _model_paths() -> Tuple[Path, Path]:
    onnx_env = os.getenv("AGRO_LOCAL_DIAGNOSIS_MODEL", "").strip()
    meta_env = os.getenv("AGRO_LOCAL_DIAGNOSIS_META", "").strip()
    onnx_p = Path(onnx_env) if onnx_env else (_DEFAULT_ML_DIR / "agro_two_stage_v1.onnx")
    meta_p = Path(meta_env) if meta_env else (_DEFAULT_ML_DIR / "agro_two_stage_v1_meta.json")
    return onnx_p, meta_p


def is_local_specialist_enabled() -> bool:
    if os.getenv("AGRO_DISABLE_LOCAL_VISION", "").strip().lower() in ("1", "true", "yes"):
        return False
    onnx_p, meta_p = _model_paths()
    if not (onnx_p.is_file() and meta_p.is_file()):
        return False
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def get_local_specialist_metadata() -> Optional[Dict[str, Any]]:
    if not is_local_specialist_enabled():
        return None
    _, meta_p = _model_paths()
    try:
        data = json.loads(meta_p.read_text(encoding="utf-8"))
        return {
            "model_id": data.get("model_id"),
            "architecture": data.get("architecture"),
            "supported_crops": data.get("crops", []),
            "num_classes": len(data.get("problems", [])),
            "onnx_size_mb": data.get("onnx_size_mb"),
            "held_out_test_metrics": data.get("held_out_test_metrics"),
            "crop_has_healthy_class": data.get("crop_has_healthy_class"),
        }
    except Exception as exc:
        logger.warning("Could not read local specialist metadata: %s", exc)
        return None


def _load_bundle():
    if not is_local_specialist_enabled():
        return None, None, None
    onnx_p, meta_p = _model_paths()
    key = f"{onnx_p.resolve()}::{onnx_p.stat().st_mtime_ns}::{meta_p.stat().st_mtime_ns}"
    if _SESSION_CACHE["loaded_path"] == key and _SESSION_CACHE["session"] is not None:
        return _SESSION_CACHE["session"], _SESSION_CACHE["meta"], _SESSION_CACHE["prototypes"]

    import numpy as np
    import onnxruntime as ort

    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    raw_proto = base64.b64decode(meta["prototypes_fp16_b64"])
    num_probs = len(meta["problems"])
    emb_dim = int(meta.get("embedding_dim", 576))
    prototypes = np.frombuffer(raw_proto, dtype=np.float16).astype(np.float32).reshape(num_probs, emb_dim)
    global_mean = None
    if meta.get("global_mean_fp16_b64"):
        global_mean = np.frombuffer(base64.b64decode(meta["global_mean_fp16_b64"]), dtype=np.float16).astype(np.float32).reshape(emb_dim)

    sess_opts = ort.SessionOptions()
    sess_opts.intra_op_num_threads = 2
    sess = ort.InferenceSession(str(onnx_p), sess_options=sess_opts, providers=["CPUExecutionProvider"])

    _SESSION_CACHE["loaded_path"] = key
    _SESSION_CACHE["session"] = sess
    _SESSION_CACHE["meta"] = meta
    _SESSION_CACHE["prototypes"] = prototypes
    _SESSION_CACHE["global_mean"] = global_mean
    return sess, meta, prototypes


def _preprocess_224(image_bytes: bytes):
    import numpy as np
    from PIL import Image, ImageFile, ImageOps

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    raw = Image.open(io.BytesIO(image_bytes))
    try:
        im = ImageOps.exif_transpose(raw)
    except Exception:
        im = raw
    if im.mode in ("P", "RGBA", "LA"):
        im = im.convert("RGBA")
    im = im.convert("RGB")
    w, h = im.size
    scale = 240.0 / max(min(w, h), 1)
    nw, nh = max(224, int(round(w * scale))), max(224, int(round(h * scale)))
    im = im.resize((nw, nh), Image.Resampling.BILINEAR)
    x0 = (nw - 224) // 2
    y0 = (nh - 224) // 2
    im = im.crop((x0, y0, x0 + 224, y0 + 224))
    arr = np.asarray(im, dtype=np.float32) / 255.0
    chw = np.transpose(arr, (2, 0, 1))[None, :, :, :]
    return chw, arr


def _softmax_1d(logits):
    import numpy as np
    z = logits - float(np.max(logits))
    e = np.exp(z)
    return e / float(np.sum(e))


def _resolve_supported_crop(crop_text: str, supported_crops: List[str]) -> Optional[str]:
    if not crop_text:
        return None
    for sc in supported_crops:
        if crops_match(crop_text, sc):
            return sc
    return None


def predict_with_local_specialist(
    image_bytes: bytes,
    crop_hint: str = "",
    crop_confirmed: bool = False,
) -> Tuple[Optional[dict], Optional[str]]:
    """Runs the calibrated ONNX Two-Stage classifier and returns `(parsed_v3_dict, model_label)`."""
    sess, meta, prototypes = _load_bundle()
    if sess is None or meta is None or prototypes is None:
        return None, None

    import numpy as np

    try:
        x_np, rgb_hwc = _preprocess_224(image_bytes)
        emb_b, crop_logits_b, prob_logits_b = sess.run(None, {"input_rgb_01": x_np})
    except Exception as exc:
        logger.warning("Local specialist ONNX inference failed: %s", exc)
        return None, None

    emb_raw = emb_b[0]
    global_mean = _SESSION_CACHE.get("global_mean")
    if global_mean is not None:
        c_vec = emb_raw - global_mean
        emb = c_vec / (float(np.linalg.norm(c_vec)) + 1e-8)
    else:
        emb = emb_raw
    crop_logits = crop_logits_b[0]
    prob_logits = prob_logits_b[0]

    cal = meta["calibration"]
    crops: List[str] = meta["crops"]
    problems: List[dict] = meta["problems"]
    crop_to_indices: Dict[str, List[int]] = meta["crop_to_problem_indices"]
    crop_has_healthy: Dict[str, bool] = meta.get("crop_has_healthy_class", {})

    cos_sims = emb @ prototypes.T
    max_cos = float(np.max(cos_sims))
    ood_thr = float(cal.get("ood_cosine_threshold", 0.35))
    in_domain_mod_cos = float(cal.get("in_domain_mod_cosine", ood_thr + 0.06))
    in_domain_high_cos = float(cal.get("in_domain_high_cosine", in_domain_mod_cos + 0.06))

    # Foliar naturalness + high-frequency noise / blank-frame OOD score
    r_ch, g_ch, b_ch = rgb_hwc[:, :, 0], rgb_hwc[:, :, 1], rgb_hwc[:, :, 2]
    rgb_std = float(rgb_hwc.std())
    exg = 2.0 * g_ch - r_ch - b_ch
    pigment_frac = float(((exg > 0.04) | ((g_ch > b_ch * 1.08) & (r_ch > b_ch * 1.05))).mean())
    hf_diff = float(np.abs(rgb_hwc[:, 1:, :] - rgb_hwc[:, :-1, :]).mean())
    nat_score = 0.0 if (rgb_std < 0.03 or hf_diff > 0.22) else (0.5 + 0.5 * min(1.0, max(0.0, pigment_frac * 2.5)))
    ood_composite = max_cos * nat_score

    if ood_composite < ood_thr or rgb_std < 0.03:
        return (
            {
                "plant_identification": {
                    "is_plant": False,
                    "crop": "",
                    "scientific_name": "",
                    "variety": "",
                    "identification_confidence": "low",
                    "visible_features": [],
                    "candidate_crops": [],
                    "uncertain_reason": "Visual features fall outside known crop leaf distributions.",
                },
                "diagnosis": {},
            },
            f"{meta['model_id']} (Local Two-Stage ONNX)",
        )

    # ---------------- STAGE A: CROP IDENTIFICATION ----------------
    t_crop = float(cal.get("T_crop", 1.0))
    crop_probs = _softmax_1d(crop_logits / max(t_crop, 0.1))
    ranked_crop_idxs = np.argsort(-crop_probs).tolist()
    top_crop_idx = int(ranked_crop_idxs[0])
    pred_crop = crops[top_crop_idx]
    top_crop_prob = float(crop_probs[top_crop_idx])

    # Max prototype similarity specifically within the predicted crop
    pred_crop_pidxs = crop_to_indices.get(pred_crop, [])
    crop_proto_cos = float(np.max(cos_sims[pred_crop_pidxs])) if pred_crop_pidxs else max_cos

    crop_high_thr = float(cal.get("crop_high_prob", 0.80))
    crop_mod_thr = float(cal.get("crop_mod_prob", 0.55))

    if top_crop_prob >= crop_high_thr and crop_proto_cos >= in_domain_high_cos:
        plant_conf = "high"
        uncertain_reason = ""
    elif top_crop_prob >= crop_mod_thr and crop_proto_cos >= in_domain_mod_cos:
        plant_conf = "medium"
        uncertain_reason = "Leaf features match moderately; confirm crop if intercropped or another species."
    else:
        plant_conf = "low"
        uncertain_reason = (
            "Leaf appearance is ambiguous or belongs to a crop outside the local 5-crop specialist "
            "(Cotton, Maize, Rice, Sugarcane, Wheat)."
        )

    candidate_crops = [crops[i] for i in ranked_crop_idxs[1:4] if float(crop_probs[i]) >= 0.08]

    # Decide which crop governs Stage B
    target_crop = pred_crop
    if crop_confirmed and crop_hint.strip():
        supported = _resolve_supported_crop(crop_hint.strip(), crops)
        if supported is None:
            # Farmer confirmed a crop (e.g. Tomato / Ragi) that this 5-crop model was NOT trained on -> abstain honestly!
            return (
                {
                    "plant_identification": {
                        "is_plant": True,
                        "crop": crop_hint.strip(),
                        "scientific_name": "",
                        "variety": "",
                        "identification_confidence": "medium",
                        "visible_features": [],
                        "candidate_crops": [],
                        "uncertain_reason": (
                            f"Local specialist model covers {', '.join(crops)} only and has no trained classes for '{crop_hint.strip()}'."
                        ),
                    },
                    "diagnosis": {
                        "problem_name": "Unable to identify",
                        "scientific_name": "",
                        "category": "unclear",
                        "affected_parts": ["leaf"],
                        "symptoms_observed": [],
                        "confidence": "low",
                        "alternatives": [],
                        "severity": "uncertain",
                        "severity_basis": "",
                        "missing_information": [
                            f"Cloud multimodal vision provider is needed to diagnose '{crop_hint.strip()}' (local specialist supports {', '.join(crops)})."
                        ],
                        "follow_up_questions": [],
                    },
                    "organic_and_cultural_measures": [],
                    "prevention": [],
                },
                f"{meta['model_id']} (Local Two-Stage ONNX)",
            )
        target_crop = supported

    # ---------------- STAGE B: CROP-CONDITIONED PROBLEM IDENTIFICATION ----------------
    eligible_idxs = crop_to_indices.get(target_crop, [])
    masked_logits = np.array([prob_logits[i] for i in eligible_idxs], dtype=np.float32)
    t_prob = float(cal.get("T_problem", 1.0))
    within_probs = _softmax_1d(masked_logits / max(t_prob, 0.1))
    local_order = np.argsort(-within_probs).tolist()

    best_local = int(local_order[0])
    best_prob_idx = eligible_idxs[best_local]
    best_prob_val = float(within_probs[best_local])
    best_meta = problems[best_prob_idx]
    best_proto_cos = float(cos_sims[best_prob_idx])

    prob_high_thr = float(cal.get("problem_high_prob", 0.82))
    prob_mod_thr = float(cal.get("problem_mod_prob", 0.52))

    if best_prob_val >= prob_high_thr and best_proto_cos >= in_domain_high_cos:
        diag_conf = "high"
    elif best_prob_val >= prob_mod_thr and best_proto_cos >= ood_thr + 0.04:
        diag_conf = "medium"
    else:
        diag_conf = "low"

    alternatives: List[Dict[str, str]] = []
    for runner_local in local_order[1:3]:
        runner_prob = float(within_probs[runner_local])
        if runner_prob >= 0.10:
            rm = problems[eligible_idxs[int(runner_local)]]
            syms = rm.get("typical_symptoms") or []
            alternatives.append({
                "name": rm["problem"],
                "why": syms[0] if syms else f"Alternative {target_crop} {rm['category']} condition to rule out in field scouting",
            })

    missing_info: List[str] = []
    # Critical Rice honesty guard: dataset has no Healthy Rice class
    if not crop_has_healthy.get(target_crop, True):
        if diag_conf == "high":
            diag_conf = "medium"
        alternatives.insert(0, {
            "name": f"Healthy {target_crop} leaf",
            "why": "Local reference set for Rice lacks a dedicated Healthy class; verify visible lesions on the blade before acting.",
        })
        missing_info.append("Confirm whether distinct spots, streaks, or stunting are visibly present across multiple plants")

    is_healthy = best_meta["category"] == "healthy"
    if diag_conf == "low":
        problem_name = "Unable to identify"
        category = "unclear"
        severity = "uncertain"
        severity_basis = ""
        missing_info.append("Close-up photo of both upper and lower leaf surfaces in natural daylight")
    else:
        problem_name = best_meta["problem"]
        category = best_meta["category"]
        severity = "healthy" if is_healthy else "moderate"
        severity_basis = (
            "No foliar disease lesions matched above threshold."
            if is_healthy
            else "Symptom pattern matched reference visual class; exact field severity requires whole-plot scouting."
        )

    parsed = {
        "plant_identification": {
            "is_plant": True,
            "crop": pred_crop,
            "scientific_name": meta.get("crop_scientific", {}).get(pred_crop, ""),
            "variety": "",
            "identification_confidence": plant_conf,
            "visible_features": meta.get("crop_visible_features", {}).get(pred_crop, []),
            "candidate_crops": candidate_crops,
            "uncertain_reason": uncertain_reason,
        },
        "diagnosis": {
            "problem_name": problem_name,
            "scientific_name": best_meta.get("scientific_name") or "",
            "category": category,
            "affected_parts": best_meta.get("affected_parts", ["leaf"]),
            "symptoms_observed": best_meta.get("typical_symptoms", []) if diag_conf != "low" else [],
            "confidence": diag_conf,
            "alternatives": alternatives[:4],
            "severity": severity,
            "severity_basis": severity_basis,
            "missing_information": missing_info,
            "follow_up_questions": [
                "How many plants or patches in the field show these same symptoms?",
                "Did symptoms start on older lower leaves or young emerging leaves?",
            ] if (not is_healthy and diag_conf != "low") else [],
        },
        "organic_and_cultural_measures": best_meta.get("organic_measures", []) if diag_conf != "low" else [],
        "prevention": best_meta.get("prevention", []) if diag_conf != "low" else [],
    }
    return parsed, f"{meta['model_id']} (Local Two-Stage ONNX)"
