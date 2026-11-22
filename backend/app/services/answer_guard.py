"""Deterministic answer guard for AgroGPT (G2).

Until the verified knowledge library exists (G4) NO answer can be traced to an approved
source, so any specific pesticide/fertilizer quantity is treated as unsupported and replaced
by a safe message. Also blocks prompt leakage and flags certainty claims. This is a safety
net, not proof of correctness.
"""
import re
from typing import Dict, List, Tuple

DOSE = re.compile(
    r"\b\d+(\.\d+)?\s*(-|–|to)?\s*(\d+(\.\d+)?)?\s*(ml|mL|g|gm|gms|kg|kgs|l|litres?|liters?|ppm|grams?|quintals?)\b"
    r"|\d+\s*%\s*(EC|WP|SC|SL|solution)|\bper\s+acre\b|\bper\s+hectare\b|/\s*(acre|ha)\b"
    r"|ಎಕರೆಗೆ\s*\d+|\d+\s*(ಮಿ\.?\s?ಲೀ|ಕೆ\.?\s?ಜಿ|ಗ್ರಾಂ|ಲೀಟರ್)|प्रति\s*एकड़|\d+\s*(किलो|ग्राम|मिली)",
    re.I,
)
LEAK = re.compile(r"FARMER REAL-TIME CONTEXT|CRITICAL LANGUAGE INSTRUCTION|You are Agro GPT, an expert|system prompt\s*[:=]",
                  re.I)
CERTAIN = re.compile(r"\b100\s*%\s*(sure|certain|accurate)|guaranteed|definitely (is|has)|ಖಂಡಿತವಾಗಿ", re.I)

SAFE_DOSE = {
    "en": ("I can't give a specific pesticide or fertilizer quantity without an approved source. "
           "Please follow the product label and the package of practices for your crop and area, "
           "and confirm with your local Krishi Vigyan Kendra (KVK) or agriculture officer. "
           "If you tell me your crop, its growth stage and your location, I can explain what to check."),
    "kn": ("ಅನುಮೋದಿತ ಮೂಲವಿಲ್ಲದೆ ಕೀಟನಾಶಕ ಅಥವಾ ಗೊಬ್ಬರದ ನಿರ್ದಿಷ್ಟ ಪ್ರಮಾಣವನ್ನು ನಾನು ಹೇಳಲಾರೆ. "
           "ದಯವಿಟ್ಟು ಉತ್ಪನ್ನದ ಲೇಬಲ್ ಮತ್ತು ನಿಮ್ಮ ಬೆಳೆ ಹಾಗೂ ಪ್ರದೇಶಕ್ಕೆ ಅನ್ವಯಿಸುವ ಶಿಫಾರಸುಗಳನ್ನು ಅನುಸರಿಸಿ, "
           "ನಿಮ್ಮ ಸ್ಥಳೀಯ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ಅಥವಾ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ. "
           "ನಿಮ್ಮ ಬೆಳೆ, ಬೆಳವಣಿಗೆಯ ಹಂತ ಮತ್ತು ಸ್ಥಳ ತಿಳಿಸಿದರೆ ಏನನ್ನು ಪರಿಶೀಲಿಸಬೇಕೆಂದು ವಿವರಿಸುತ್ತೇನೆ."),
    "hi": ("बिना मान्य स्रोत के मैं कीटनाशक या खाद की सटीक मात्रा नहीं बता सकता। कृपया उत्पाद के लेबल और अपनी फसल व क्षेत्र "
           "की अनुशंसाओं का पालन करें, और अपने स्थानीय कृषि विज्ञान केंद्र (KVK) या कृषि अधिकारी से पुष्टि करें।"),
}
SAFE_LEAK = {
    "en": "I can't share my internal instructions. I can help with your farming questions, though.",
    "kn": "ನನ್ನ ಆಂತರಿಕ ಸೂಚನೆಗಳನ್ನು ನಾನು ಹಂಚಿಕೊಳ್ಳಲಾರೆ. ನಿಮ್ಮ ಕೃಷಿ ಪ್ರಶ್ನೆಗಳಿಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
    "hi": "मैं अपने आंतरिक निर्देश साझा नहीं कर सकता। खेती से जुड़े सवालों में मदद कर सकता हूँ।",
}
FALLBACK_NOTICE = {
    "en": "Note: the AI service is temporarily unavailable, so this is general guidance, not a personalised or source-checked answer.\n\n",
    "kn": "ಸೂಚನೆ: AI ಸೇವೆ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ, ಆದ್ದರಿಂದ ಇದು ಸಾಮಾನ್ಯ ಮಾರ್ಗದರ್ಶನ ಮಾತ್ರ; ವೈಯಕ್ತಿಕ ಅಥವಾ ಮೂಲ-ಪರಿಶೀಲಿತ ಉತ್ತರವಲ್ಲ.\n\n",
    "hi": "सूचना: AI सेवा अस्थायी रूप से उपलब्ध नहीं है, इसलिए यह सामान्य मार्गदर्शन है, व्यक्तिगत या स्रोत-जाँचा हुआ उत्तर नहीं।\n\n",
}


def _l(d: Dict[str, str], lang: str) -> str:
    return d.get(lang) or d["en"]


def guard_reply(text: str, lang: str = "en", tier: str = "llm",
                verified_sources: bool = False) -> Tuple[str, List[str]]:
    """Returns (safe_text, flags). `verified_sources` becomes True only once G4 supplies approved evidence."""
    flags: List[str] = []
    out = text or ""
    if LEAK.search(out):
        return _l(SAFE_LEAK, lang), ["prompt_leak_blocked"]
    if not verified_sources and DOSE.search(out):
        out = _l(SAFE_DOSE, lang)
        flags.append("unsourced_dose_blocked")
    if CERTAIN.search(out):
        flags.append("certainty_claim")
    if tier == "rule_based_fallback":
        out = _l(FALLBACK_NOTICE, lang) + out
        flags.append("ai_unavailable_fallback")
    return out, flags
