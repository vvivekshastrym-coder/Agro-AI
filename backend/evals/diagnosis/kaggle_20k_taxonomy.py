"""Verified canonical crop & disease taxonomy for `jawadali1045/20k-multi-class-crop-disease-images`.

Why this file exists:
- Raw folders in this public Kaggle dataset have inconsistent naming, typos ("Becterial", "thirps"),
  split-case duplicates across Train/Validation ("bacterial_blight in Cotton" vs "Bacterial Blight in cotton",
  "Wheat Brown leaf Rust" vs "Wheat Brown leaf rust"), nested folders ("Train/Healthy Wheat/Wheat___Healthy"),
  implicit-crop folder names ("Brownspot", "Tungro", "Common_Rust", "Gray_Leaf_Spot", "Leaf Curl",
  "Army worm", "Wilt", "Flag Smut", "Leaf smut"), and one 4-image class ("bollrot on Cotton").
- Note on Rice: this Kaggle dataset contains 5 Rice disease folders and ZERO "Healthy Rice" folder
  (`CROP_HAS_HEALTHY_CLASS["Rice"] = False`). Stage B must never claim HIGH confidence on Rice without
  an independent VLM check or lesion margin, and must list "Healthy Rice leaf" as an explicit alternative.
- All cultural/organic and preventive notes below are general, non-chemical, quantity-free agronomic
  sanitation/IPM practices (verified free of any dose/rate numbers).
"""
from typing import Any, Dict, List, Optional

CROP_SCIENTIFIC = {
    "Cotton": "Gossypium hirsutum",
    "Maize": "Zea mays",
    "Rice": "Oryza sativa",
    "Sugarcane": "Saccharum officinarum",
    "Wheat": "Triticum aestivum",
}

CROP_VISIBLE_FEATURES = {
    "Cotton": ["Broad palmately lobed leaf blade with 3-5 lobes and palmate main veins"],
    "Maize": ["Broad ribbon-like grass leaf blade with prominent pale central midrib and wavy margins"],
    "Rice": ["Narrow linear grass leaf blade with parallel venation and rough scabrid margins"],
    "Sugarcane": ["Long broad strap-shaped grass leaf blade with thick white midrib"],
    "Wheat": ["Narrow flat cereal leaf blade or awned spikelet head with parallel venation"],
}

# Crucial dataset limitation tracked honestly for inference gating
CROP_HAS_HEALTHY_CLASS = {
    "Cotton": True,
    "Maize": True,
    "Rice": False,  # No Healthy Rice folder exists in jawadali1045/20k-multi-class-crop-disease-images
    "Sugarcane": True,
    "Wheat": True,
}

# Generic non-chemical cultural/IPM guidance by category (strictly zero dosages or chemical names)
DEFAULT_CULTURAL_BY_CATEGORY: Dict[str, Dict[str, List[str]]] = {
    "healthy": {
        "organic": [],
        "prevention": [
            "Continue routine weekly field scouting across inner and border rows",
            "Maintain balanced soil nutrition and avoid waterlogging or prolonged drought stress",
        ],
    },
    "fungal": {
        "organic": [
            "Remove and destroy heavily infected leaves or plant debris away from the field border",
            "Avoid overhead irrigation late in the afternoon so foliage dries quickly",
            "Improve airflow through timely weeding and avoiding excessive nitrogen top-dressing",
        ],
        "prevention": [
            "Use certified disease-free seed or planting material suited to your agro-climatic zone",
            "Practice seasonal crop rotation with non-host crops and clear volunteer plants after harvest",
        ],
    },
    "bacterial": {
        "organic": [
            "Avoid working in or walking through the crop while foliage is wet with dew or rain",
            "Remove severely blighted plant debris and keep field drainage channels clear",
            "Avoid excess nitrogen application which promotes soft, susceptible foliar growth",
        ],
        "prevention": [
            "Sow clean, certified seed of locally recommended tolerant varieties",
            "Plow under or remove infected crop residue after harvest and rotate crops",
        ],
    },
    "viral": {
        "organic": [
            "Rogue out clearly stunted or virus-infected plants early to reduce field inoculum",
            "Remove weed hosts along bunds and field borders that shelter sap-sucking insect vectors",
            "Use yellow or blue sticky traps for monitoring sap-sucking vector populations",
        ],
        "prevention": [
            "Select virus-tolerant hybrids or varieties recommended by your state agricultural university",
            "Maintain clean bunds and avoid staggered sowing next to older infected plots",
        ],
    },
    "pest": {
        "organic": [
            "Hand-pick and destroy visible egg masses, webbed leaves, or gregarious larvae during scouting",
            "Install pheromone traps or bird perches to monitor pest activity and encourage natural predators",
            "Conserve beneficial insects such as ladybird beetles, lacewings, and spiders",
        ],
        "prevention": [
            "Deep summer plowing after harvest helps expose resting pupae in the soil",
            "Remove alternate weed hosts on bunds and practice timely synchronous sowing",
        ],
    },
}


def _entry(
    crop: str,
    problem: str,
    category: str,
    scientific_name: Optional[str] = None,
    affected_parts: Optional[List[str]] = None,
    symptoms: Optional[List[str]] = None,
    exclude_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "crop": crop,
        "crop_scientific": CROP_SCIENTIFIC[crop],
        "problem": problem,
        "canonical_key": f"{crop}::{problem}",
        "category": category,
        "scientific_name": scientific_name,
        "affected_parts": affected_parts or ["leaf"],
        "typical_symptoms": symptoms or [],
        "exclude_reason": exclude_reason,
    }


# Exact mapping of all 45 raw folder names (keyed by lowercased single-space-normalized folder name)
RAW_FOLDER_TAXONOMY: Dict[str, Dict[str, Any]] = {
    # ---------------- COTTON ----------------
    "healthy cotton": _entry("Cotton", "Healthy", "healthy", None, ["leaf"], ["Uniform green palmate leaf blade without necrotic lesions or pest feeding"]),
    "bacterial blight in cotton": _entry("Cotton", "Bacterial Blight", "bacterial", "Xanthomonas citri pv. malvacearum", ["leaf", "boll"], ["Angular water-soaked to dark brown lesions bounded by leaf veins"]),
    "bacterial_blight in cotton": _entry("Cotton", "Bacterial Blight", "bacterial", "Xanthomonas citri pv. malvacearum", ["leaf", "boll"], ["Angular water-soaked to dark brown lesions bounded by leaf veins"]),
    "anthracnose on cotton": _entry("Cotton", "Anthracnose", "fungal", "Colletotrichum gossypii", ["leaf", "boll", "stem"], ["Sunken reddish-brown circular spots on bolls or foliage"]),
    "leaf curl": _entry("Cotton", "Cotton Leaf Curl Virus", "viral", "Cotton leaf curl virus", ["leaf", "whole_plant"], ["Upward or downward cupping of leaves with thickened veins and enations"]),
    "wilt": _entry("Cotton", "Fusarium Wilt", "fungal", "Fusarium oxysporum f. sp. vasinfectum", ["leaf", "whole_plant"], ["Marginal yellowing, zonal necrosis, and drooping of leaves"]),
    "army worm": _entry("Cotton", "Armyworm Damage", "pest", "Spodoptera litura", ["leaf"], ["Skeletonized leaf patches and irregular defoliation with caterpillar presence"]),
    "american bollworm on cotton": _entry("Cotton", "American Bollworm", "pest", "Helicoverpa armigera", ["boll", "leaf"], ["Circular bore holes on squares or bolls with larva feeding"]),
    "bollworm on cotton": _entry("Cotton", "Bollworm Damage", "pest", None, ["boll", "leaf"], ["Boll and square feeding injury"], exclude_reason="ambiguous_overlap_with_american_and_pink_bollworm"),
    "pink bollworm in cotton": _entry("Cotton", "Pink Bollworm", "pest", "Pectinophora gossypiella", ["boll", "flower"], ["Rosetted flowers, stained lint, and internal boll feeding"]),
    "cotton aphid": _entry("Cotton", "Cotton Aphid", "pest", "Aphis gossypii", ["leaf", "shoot"], ["Curling tender leaves with clustered aphids on undersides and honeydew sheen"]),
    "cotton mealy bug": _entry("Cotton", "Cotton Mealybug", "pest", "Phenacoccus solenopsis", ["stem", "shoot", "leaf"], ["White waxy mealybug colonies clustered along stems and petioles"]),
    "cotton whitefly": _entry("Cotton", "Cotton Whitefly", "pest", "Bemisia tabaci", ["leaf"], ["Tiny white winged insects on leaf undersides with chlorotic stippling or sooty mold"]),
    "red cotton bug": _entry("Cotton", "Red Cotton Bug", "pest", "Dysdercus cingulatus", ["boll", "leaf"], ["Reddish-orange nymphs and adults with black wing markings feeding on bolls"]),
    "thirps on cotton": _entry("Cotton", "Thrips Damage", "pest", "Thrips tabaci", ["leaf"], ["Silvery-bronze rasping streaks and crinkled upward-curled young leaves"]),
    "bollrot on cotton": _entry("Cotton", "Boll Rot", "fungal", None, ["boll"], ["Rotting discoloured cotton bolls"], exclude_reason="insufficient_samples_lt_20"),

    # ---------------- MAIZE ----------------
    "healthy maize": _entry("Maize", "Healthy", "healthy", None, ["leaf"], ["Uniform green maize blade with clean central midrib and intact margins"]),
    "common_rust": _entry("Maize", "Common Rust", "fungal", "Puccinia sorghi", ["leaf"], ["Cinnamon-brown oval to elongated pustules scattered across leaf surfaces"]),
    "gray_leaf_spot": _entry("Maize", "Gray Leaf Spot", "fungal", "Cercospora zeae-maydis", ["leaf"], ["Rectangular tan to grey necrotic lesions restricted strictly between parallel veins"]),
    "maize ear rot": _entry("Maize", "Maize Ear Rot", "fungal", "Fusarium verticillioides", ["fruit"], ["White, pinkish, or powdery mold growth on kernels of the maize cob"]),
    "maize fall armyworm": _entry("Maize", "Fall Armyworm", "pest", "Spodoptera frugiperda", ["leaf", "whorl"], ["Ragged elongated windowpane feeding holes in the whorl with moist frass"]),
    "maize stem borer": _entry("Maize", "Maize Stem Borer", "pest", "Chilo partellus", ["stem", "leaf"], ["Shot-hole rows across unfolding leaves and dead-heart or stalk tunneling"]),

    # ---------------- RICE ----------------
    "becterial blight in rice": _entry("Rice", "Bacterial Leaf Blight", "bacterial", "Xanthomonas oryzae pv. oryzae", ["leaf"], ["Water-soaked yellowish stripes along leaf tips and margins drying to straw-white"]),
    "brownspot": _entry("Rice", "Brown Spot", "fungal", "Bipolaris oryzae", ["leaf", "grain"], ["Small oval to sesame-shaped dark brown spots often with a yellow halo"]),
    "leaf smut": _entry("Rice", "Leaf Smut", "fungal", "Entyloma oryzae", ["leaf"], ["Small slightly raised angular black spots scattered along the rice leaf blade"]),
    "rice blast": _entry("Rice", "Rice Blast", "fungal", "Magnaporthe oryzae", ["leaf", "stem"], ["Diamond or spindle-shaped lesions with grey-white centers and dark brown borders"]),
    "tungro": _entry("Rice", "Rice Tungro Disease", "viral", "Rice tungro bacilliform/spherical virus", ["leaf", "whole_plant"], ["Yellow-orange discolouration starting from leaf tips with stunted tillers"]),

    # ---------------- SUGARCANE ----------------
    "sugarcane healthy": _entry("Sugarcane", "Healthy", "healthy", None, ["leaf"], ["Clean green sugarcane leaf blade with prominent white midrib"]),
    "mosaic sugarcane": _entry("Sugarcane", "Sugarcane Mosaic Virus", "viral", "Sugarcane mosaic virus", ["leaf"], ["Irregular pale green to yellowish chlorotic islands mottling the green blade"]),
    "redrot sugarcane": _entry("Sugarcane", "Red Rot", "fungal", "Colletotrichum falcatum", ["leaf", "stem"], ["Reddish lesions along the midrib or internal stalk reddening with white patches"]),
    "redrust sugarcane": _entry("Sugarcane", "Brown / Orange Rust", "fungal", "Puccinia melanocephala", ["leaf"], ["Elongated reddish-brown to orange pustules erupting on leaf undersides"]),
    "yellow rust sugarcane": _entry("Sugarcane", "Yellow Leaf / Rust", "fungal", None, ["leaf"], ["Yellowing of midrib and lamina spreading toward leaf margins"]),

    # ---------------- WHEAT ----------------
    "healthy wheat": _entry("Wheat", "Healthy", "healthy", None, ["leaf", "head"], ["Healthy green wheat foliage or clean developing cereal spike"]),
    "wheat___healthy": _entry("Wheat", "Healthy", "healthy", None, ["leaf"], ["Healthy green wheat leaf blade without pustules or blotches"]),
    "wheat brown leaf rust": _entry("Wheat", "Brown (Leaf) Rust", "fungal", "Puccinia triticina", ["leaf"], ["Small circular orange-brown pustules scattered on the upper leaf surface"]),
    "wheat___yellow_rust": _entry("Wheat", "Yellow (Stripe) Rust", "fungal", "Puccinia striiformis", ["leaf"], ["Bright yellow-orange pustules arranged in narrow linear stripes along veins"]),
    "wheat black rust": _entry("Wheat", "Black (Stem) Rust", "fungal", "Puccinia graminis", ["stem", "leaf"], ["Dark reddish-brown to black elongated erumpent pustules on stems and sheaths"]),
    "flag smut": _entry("Wheat", "Flag / Loose Smut", "fungal", None, ["head", "leaf"], ["Dark brown to black powdery spore masses replacing spikelets or forming leaf streaks"]),
    "wheat powdery mildew": _entry("Wheat", "Powdery Mildew", "fungal", "Blumeria graminis", ["leaf", "stem"], ["Fluffy white to grey powdery fungal patches on upper leaf surfaces"]),
    "wheat leaf blight": _entry("Wheat", "Leaf Blight", "fungal", "Bipolaris sorokiniana", ["leaf"], ["Oval to irregular tan-brown necrotic blotches coalescing across the leaf blade"]),
    "wheat scab": _entry("Wheat", "Fusarium Head Blight (Scab)", "fungal", "Fusarium graminearum", ["head"], ["Prematurely bleached tan spikelets on an otherwise green wheat head"]),
    "wheat aphid": _entry("Wheat", "Wheat Aphid", "pest", "Sitobion avenae", ["leaf", "head"], ["Clusters of green to dark aphids feeding along wheat blades and spikes"]),
    "wheat stem fly": _entry("Wheat", "Wheat Stem Fly", "pest", "Atherigona naqvii", ["stem", "whole_plant"], ["Dead-heart drying of central shoot in young wheat seedlings"]),
    "wheat mite": _entry("Wheat", "Wheat Mite", "pest", "Petrobia latens", ["leaf"], ["Fine pale stippling and bronzing/yellowing of wheat leaves from mite feeding"]),
}


def normalize_folder_key(folder_name: str) -> str:
    return " ".join(folder_name.strip().lower().split())


def lookup_folder_taxonomy(folder_name: str) -> Optional[Dict[str, Any]]:
    return RAW_FOLDER_TAXONOMY.get(normalize_folder_key(folder_name))
