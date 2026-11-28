"""Agro AI Leaf Diagnosis Engine v3 — two-stage, uncertainty-first.

Stage A  plant identification   (is it a plant? which crop? how sure?)
Stage B  problem identification (disease / pest / deficiency / stress / healthy)
Gate     deterministic safety layer applied AFTER the vision model answers:
         - the farmer's crop hint is a claim to verify, never ground truth
         - plant ID uncertain or contradicting the hint -> ask the farmer to confirm the crop
         - confidence is CATEGORICAL (HIGH / MODERATE / LOW) and capped by plant-ID and photo quality;
           no invented percentages
         - chemical treatment is NEVER generated: no CIBRC/label library is connected, so doses and
           products would be unverified; the farmer is pointed to the label / KVK instead
         - any organic/prevention line containing a dose or quantity is withheld (same rule as AgroGPT)
There is intentionally NO local colour-threshold fallback: it picked a disease from a hardcoded list
(defaulting to tomato) and attached fixed 0.86-0.94 confidences, which was fabrication.
"""
import base64
import io
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .answer_guard import DOSE

logger = logging.getLogger(__name__)

ENGINE_VERSION = "3.0-two-stage"
VISION_TIMEOUT_SECONDS = 30.0

CHEMICAL_GUIDANCE = {
    "en": "No verified chemical recommendation is available. Do not use any pesticide or fungicide based on this "
          "app alone. Consult your local Krishi Vigyan Kendra (KVK) or agriculture officer and follow the "
          "registered product label for your crop.",
    "kn": "ಪರಿಶೀಲಿತ ರಾಸಾಯನಿಕ ಶಿಫಾರಸು ಲಭ್ಯವಿಲ್ಲ. ಈ ಆ್ಯಪ್ ಆಧಾರದ ಮೇಲೆ ಮಾತ್ರ ಯಾವುದೇ ಕೀಟನಾಶಕ ಅಥವಾ "
          "ಶಿಲೀಂಧ್ರನಾಶಕ ಬಳಸಬೇಡಿ. ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ಅಥವಾ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು "
          "ಸಂಪರ್ಕಿಸಿ ಮತ್ತು ನಿಮ್ಮ ಬೆಳೆಗೆ ನೋಂದಾಯಿತ ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಅನುಸರಿಸಿ.",
    "hi": "कोई सत्यापित रासायनिक सिफारिश उपलब्ध नहीं है। केवल इस ऐप के आधार पर कोई कीटनाशक या फफूंदनाशक "
          "न डालें। अपने स्थानीय कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से सलाह लें और अपनी फसल के "
          "पंजीकृत उत्पाद का लेबल देखें।",
}

TWO_STAGE_PROMPT = """You are a careful plant pathologist helping Indian farmers (especially Karnataka).
Look ONLY at the attached photograph. Work in two separate stages and output ONE JSON object, no prose, no code fences.

STAGE A - PLANT IDENTIFICATION (do this first, independently of any disease)
Decide whether the photo shows a plant/leaf at all, then identify the crop from leaf shape, venation, arrangement,
fruit/flower if visible. The farmer's crop hint may be WRONG: treat it as a claim to verify, never as truth.
If you cannot tell the crop apart from lookalikes, say so and list candidates.

STAGE B - PROBLEM IDENTIFICATION
Only after stage A, describe what is visibly wrong. Consider ALL of: fungal, bacterial, viral, insect/mite damage,
nutrient deficiency, water stress, heat/cold damage, herbicide injury, mechanical damage, natural senescence, healthy.
Spots or yellowing alone do NOT prove a disease. Do not force a disease label; "healthy" and "unclear" are valid.

RULES
- Never invent. If unsure, set the confidence to "low" and explain why.
- Do NOT include pesticide/fungicide names, doses, concentrations, or spray schedules anywhere.
- Organic/cultural measures: only general, widely accepted practices, without quantities.
- Confidence values must be exactly "low", "medium" or "high" (no percentages).

JSON SCHEMA
{
 "plant_identification": {
   "is_plant": true,
   "crop": "common crop name or empty string",
   "scientific_name": "or empty string",
   "variety": "only if identifiable, else empty string",
   "identification_confidence": "low|medium|high",
   "visible_features": ["leaf/plant features that support the identification"],
   "candidate_crops": ["other crops it could be, if uncertain"],
   "uncertain_reason": "why, if not high"
 },
 "diagnosis": {
   "problem_name": "disease/pest/deficiency/stress name, or 'Healthy', or 'Unable to identify'",
   "scientific_name": "pathogen/pest scientific name only if the problem is specific, else empty string",
   "category": "fungal|bacterial|viral|pest|nutrient_deficiency|water_stress|temperature_stress|herbicide_injury|mechanical|natural_senescence|healthy|unclear",
   "affected_parts": ["leaf|stem|fruit|whole_plant ..."],
   "symptoms_observed": ["concrete visual symptoms seen in THIS photo"],
   "confidence": "low|medium|high",
   "alternatives": [{"name": "other possible problem", "why": "what would distinguish it"}],
   "severity": "healthy|mild|moderate|severe|uncertain",
   "severity_basis": "visual evidence for the severity",
   "missing_information": ["what extra photo/info would settle it"],
   "follow_up_questions": ["short questions to ask the farmer"]
 },
 "organic_and_cultural_measures": ["general measures without quantities"],
 "prevention": ["general prevention steps without quantities"]
}
"""

# Words that mean the same crop. Used only to compare the farmer's hint with the model's identification.
_CROP_ALIASES = {
    "rice": {"rice", "paddy", "bhatta", "akki", "dhan"},
    "ragi": {"ragi", "finger", "millet", "mandua"},
    "maize": {"maize", "corn", "makka"},
    "tur": {"tur", "arhar", "pigeon", "redgram"},
    "chilli": {"chilli", "chili", "pepper", "mirchi", "capsicum"},
    "cotton": {"cotton"},
    "tomato": {"tomato", "tamatar"},
    "potato": {"potato", "aloo"},
    "onion": {"onion", "eerulli", "pyaz"},
    "wheat": {"wheat", "gehu"},
    "sugarcane": {"sugarcane", "cane", "kabbu"},
    "coconut": {"coconut", "tenginakayi", "copra"},
    "arecanut": {"arecanut", "areca", "betelnut", "adike"},
    "groundnut": {"groundnut", "peanut"},
}

_LEVEL = {"low": 0, "medium": 1, "high": 2}
_CATEGORY = {0: "LOW", 1: "MODERATE", 2: "HIGH"}


# --------------------------------------------------------------------------- image handling
def assess_image_quality(image_bytes: bytes) -> Dict[str, Any]:
    """Cheap, honest photo checks. Thresholds are uncalibrated heuristics: they cap confidence, they do not diagnose."""
    out: Dict[str, Any] = {"decodable": False, "width": 0, "height": 0, "sharpness": None, "brightness": None,
                           "issues": [], "reject": False}
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))
        out["width"], out["height"] = im.size
        out["decodable"] = True
        gray = im.convert("L")
        gray.thumbnail((512, 512))
        out["sharpness"] = round(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0], 1)
        out["brightness"] = round(ImageStat.Stat(gray).mean[0], 1)
    except Exception:
        out["reject"] = True
        out["issues"].append("unreadable_image")
        return out

    if min(out["width"], out["height"]) < 160:
        out["reject"] = True
        out["issues"].append("resolution_too_low")
    elif min(out["width"], out["height"]) < 400:
        out["issues"].append("low_resolution")
    if out["sharpness"] is not None and out["sharpness"] < 20:
        out["issues"].append("possibly_blurry")
    if out["brightness"] is not None and out["brightness"] < 40:
        out["issues"].append("too_dark")
    if out["brightness"] is not None and out["brightness"] > 235:
        out["issues"].append("overexposed")
    return out


def prepare_image_for_vision(image_bytes: bytes, max_side: int = 1280) -> Tuple[bytes, str]:
    """Orient by EXIF, convert to RGB and bound the long side so every provider sees a consistent image."""
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
        im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return image_bytes, "image/jpeg"


# --------------------------------------------------------------------------- provider calls
def _parse_json(raw_text: str) -> Optional[dict]:
    try:
        text = (raw_text or "").replace("```json", "").replace("```", "").strip()
        s, e = text.find("{"), text.rfind("}")
        if s == -1 or e == -1:
            return None
        parsed = json.loads(text[s:e + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


async def _call_providers(image_bytes: bytes, mime: str, prompt: str, user_text: str) -> Tuple[Optional[dict], Optional[str]]:
    from .ai_service import get_gemini_api_key, get_openai_api_key, get_anthropic_api_key
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    gk = get_gemini_api_key()
    if gk and len(gk) > 10 and not gk.startswith("your-"):
        for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                payload = {
                    "contents": [{"parts": [{"text": prompt + "\n" + user_text},
                                            {"inline_data": {"mime_type": mime, "data": b64}}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 3000,
                                         "responseMimeType": "application/json"},
                }
                async with httpx.AsyncClient(timeout=VISION_TIMEOUT_SECONDS) as c:
                    r = await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                     headers={"x-goog-api-key": gk}, json=payload)
                if r.status_code == 200:
                    txt = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = _parse_json(txt)
                    if parsed:
                        return parsed, f"{model} (Google AI Studio)"
                else:
                    logger.warning("Gemini vision %s returned HTTP %s", model, r.status_code)
            except Exception as exc:
                logger.warning("Gemini vision %s failed: %s", model, type(exc).__name__)

    ok = get_openai_api_key()
    if ok and len(ok) > 10:
        try:
            payload = {
                "model": "gpt-4o-mini", "temperature": 0.1, "max_tokens": 2000,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "auto"}}]},
                ],
            }
            async with httpx.AsyncClient(timeout=VISION_TIMEOUT_SECONDS) as c:
                r = await c.post("https://api.openai.com/v1/chat/completions",
                                 headers={"Authorization": f"Bearer {ok}", "Content-Type": "application/json"}, json=payload)
            if r.status_code == 200:
                parsed = _parse_json(r.json()["choices"][0]["message"]["content"])
                if parsed:
                    return parsed, "GPT-4o-mini Vision"
            else:
                logger.warning("OpenAI vision returned HTTP %s", r.status_code)
        except Exception as exc:
            logger.warning("OpenAI vision failed: %s", type(exc).__name__)

    ak = get_anthropic_api_key()
    if ak and len(ak) > 10:
        try:
            payload = {
                "model": "claude-3-5-haiku-20241022", "max_tokens": 2000, "temperature": 0.1, "system": prompt,
                "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": user_text}]}],
            }
            async with httpx.AsyncClient(timeout=VISION_TIMEOUT_SECONDS) as c:
                r = await c.post("https://api.anthropic.com/v1/messages",
                                 headers={"x-api-key": ak, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"}, json=payload)
            if r.status_code == 200:
                parsed = _parse_json(r.json().get("content", [{}])[0].get("text", ""))
                if parsed:
                    return parsed, "Claude 3.5 Haiku Vision"
            else:
                logger.warning("Claude vision returned HTTP %s", r.status_code)
        except Exception as exc:
            logger.warning("Claude vision failed: %s", type(exc).__name__)

    return None, None


# --------------------------------------------------------------------------- deterministic gate
def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z]+", (text or "").lower()))


def crops_match(hint: str, identified: str) -> bool:
    """True when the farmer's hint and the model's crop are plausibly the same crop (alias-aware)."""
    a, b = _tokens(hint), _tokens(identified)
    if not a or not b:
        return True
    if a & b:
        return True
    for group in _CROP_ALIASES.values():
        if (a & group) and (b & group):
            return True
    return False


def _clean_list(items: Any, limit: int = 8) -> Tuple[List[str], int]:
    """Keep short text items; withhold any line that states a dose/quantity (no label/KB to verify it)."""
    kept: List[str] = []
    withheld = 0
    for it in (items if isinstance(items, list) else []):
        s = str(it).strip()
        if not s:
            continue
        if DOSE.search(s):
            withheld += 1
            continue
        kept.append(s[:300])
        if len(kept) >= limit:
            break
    return kept, withheld


def _clean_alternatives(items: Any) -> List[Dict[str, str]]:
    out = []
    for it in (items if isinstance(items, list) else [])[:4]:
        if isinstance(it, dict) and it.get("name"):
            out.append({"name": str(it["name"])[:120], "why": str(it.get("why", ""))[:240]})
        elif isinstance(it, str) and it.strip():
            out.append({"name": it.strip()[:120], "why": ""})
    return out


def _level(value: Any) -> int:
    return _LEVEL.get(str(value or "").strip().lower(), 0)


def finalize_diagnosis(parsed: dict, crop_hint: str, quality: Dict[str, Any], model_used: str, language: str = "en") -> Dict[str, Any]:
    """Turns the raw two-stage model output into a safe, honest result. Pure function (unit-testable)."""
    plant = parsed.get("plant_identification") or {}
    diag = parsed.get("diagnosis") or {}
    hint = (crop_hint or "").strip()
    crop = str(plant.get("crop") or "").strip()
    issues = quality.get("issues", [])

    base: Dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "model_used": model_used,
        "is_ai_vision": True,
        "image_quality": {"issues": issues, "width": quality.get("width"), "height": quality.get("height")},
        "plant_identification": {
            "is_plant": plant.get("is_plant") is not False,
            "crop": crop or None,
            "scientific_name": str(plant.get("scientific_name") or "") or None,
            "variety": str(plant.get("variety") or "") or None,
            "identification_confidence": _CATEGORY[_level(plant.get("identification_confidence"))],
            "visible_features": _clean_list(plant.get("visible_features"))[0],
            "candidate_crops": [str(c)[:60] for c in (plant.get("candidate_crops") or [])[:5] if str(c).strip()],
            "uncertain_reason": str(plant.get("uncertain_reason") or "") or None,
            "farmer_hint": hint or None,
        },
        "sources": [],
        "knowledge_base_verified": False,
        "chemical_treatment": [],
        "dosage": [],
        "chemical_guidance": CHEMICAL_GUIDANCE.get(language, CHEMICAL_GUIDANCE["en"]),
        "confidence": None,
        "confidence_basis": "categorical_uncalibrated",
    }

    # Gate 1: not a plant at all
    if plant.get("is_plant") is False:
        return {**base, "status": "not_a_plant", "confidence_category": "LOW",
                "message": "This photo does not appear to show a plant or leaf.",
                "next_action": "Take a clear, close photo of one affected leaf with the whole leaf in frame."}

    # Gate 2: crop unknown, uncertain, or contradicting the farmer's selection -> ask, never guess
    plant_level = _level(plant.get("identification_confidence"))
    mismatch = bool(hint and crop and not crops_match(hint, crop))
    if not crop or plant_level == 0 or mismatch:
        if mismatch:
            msg = (f"You selected '{hint}', but the photo looks more like '{crop}'. "
                   "Treatment depends on the exact crop, so please confirm which crop this is.")
        else:
            msg = "I could not identify the crop from this photo with enough confidence. Please confirm the crop."
        cands = [c for c in ([crop] if crop else []) + base["plant_identification"]["candidate_crops"] if c]
        return {**base, "status": "needs_crop_confirmation", "confidence_category": "LOW",
                "message": msg, "crop_candidates": list(dict.fromkeys(cands))[:5],
                "next_action": "Select the correct crop and analyse again, or upload a photo of the whole plant.",
                "follow_up_questions": ["Which crop is this?"]}

    # Stage B confidence is capped by plant-ID confidence and photo quality
    level = min(_level(diag.get("confidence")), plant_level)
    if any(i in issues for i in ("possibly_blurry", "too_dark", "overexposed", "low_resolution")):
        level = min(level, 1)
    category = _CATEGORY[level]

    problem = str(diag.get("problem_name") or "").strip()
    unidentified = (not problem) or problem.lower().startswith("unable") or str(diag.get("category")) == "unclear"
    missing, _ = _clean_list(diag.get("missing_information"), 6)
    followups, _ = _clean_list(diag.get("follow_up_questions"), 6)
    if "possibly_blurry" in issues:
        missing.append("A sharper close-up photo of the affected leaf")
    if "too_dark" in issues or "overexposed" in issues:
        missing.append("A photo in even natural daylight")

    detail = {
        "crop": crop,
        "disease": problem or "Unable to identify confidently",
        "scientific_name": (str(diag.get("scientific_name") or "").strip() or None) if level == 2 else None,
        "disease_category": str(diag.get("category") or "unclear"),
        "affected_parts": [str(p)[:40] for p in (diag.get("affected_parts") or [])[:6]],
        "evidence": _clean_list(diag.get("symptoms_observed"))[0],
        "severity": str(diag.get("severity") or "uncertain"),
        "severity_basis": str(diag.get("severity_basis") or "") or None,
        "alternatives": _clean_alternatives(diag.get("alternatives")),
        "missing_information": list(dict.fromkeys(missing)),
        "follow_up_questions": followups,
        "confidence_category": category,
    }

    # Gate 3: low confidence or unidentified -> no diagnosis-specific treatment at all
    if level == 0 or unidentified:
        return {**base, **detail, "status": "low_confidence", "confidence_category": "LOW",
                "organic_treatment": [], "prevention": [],
                "message": "Unable to identify the problem confidently from this photo.",
                "next_action": "Upload a close-up of the affected leaf, the underside of the leaf, and the whole plant; "
                               "or consult your local KVK / agriculture officer."}

    organic, w1 = _clean_list(parsed.get("organic_and_cultural_measures"))
    prevention, w2 = _clean_list(parsed.get("prevention"))
    result = {**base, **detail,
              "organic_treatment": organic, "prevention": prevention,
              "withheld_quantity_items": w1 + w2,
              "warnings": ["AI image assessment only; not a laboratory or expert confirmation."],
              "spray_window": None, "expected_recovery_days": None}

    if level == 1:
        # Gate 4: moderate confidence -> show possibilities, general measures only, ask for more evidence
        return {**result, "status": "moderate_confidence",
                "message": "Several problems are possible. Treat the result below as a guide, not a confirmed diagnosis.",
                "next_action": "Share the extra photos/answers listed below for a more reliable result."}
    return {**result, "status": "ok"}


# --------------------------------------------------------------------------- public entry
async def analyze_leaf_image_v3(image_bytes: bytes, mime_type: str, crop_hint: str = "", language: str = "en") -> Dict[str, Any]:
    quality = assess_image_quality(image_bytes)
    if quality["reject"]:
        reason = "The image could not be read." if "unreadable_image" in quality["issues"] else "The photo resolution is too low."
        return {"status": "low_confidence", "confidence_category": "LOW", "engine_version": ENGINE_VERSION,
                "image_quality": {"issues": quality["issues"]}, "message": reason,
                "next_action": "Take a sharp close-up photo (hold the camera 10-15 cm from the leaf in daylight)."}

    prepared, mime = prepare_image_for_vision(image_bytes)
    lang_note = {"kn": "Write all free-text strings in Kannada (ಕನ್ನಡ) script.",
                 "hi": "Write all free-text strings in Hindi (हिंदी) script."}.get(language, "Write in English.")
    user_text = (f"Farmer's crop hint (UNVERIFIED claim, may be wrong): '{crop_hint or 'none given'}'.\n{lang_note}\n"
                 "Return the JSON object only.")
    parsed, model_used = await _call_providers(prepared, mime, TWO_STAGE_PROMPT, user_text)
    if not parsed:
        return {"status": "unavailable", "engine_version": ENGINE_VERSION,
                "message": "The diagnosis service is temporarily unavailable. No diagnosis was generated.",
                "next_action": "Please retry in a few minutes."}
    return finalize_diagnosis(parsed, crop_hint, quality, model_used or "vision-model", language)
