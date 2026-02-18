import os
import re
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

# ======================
# LOAD DATA
# ======================
BASE_DIR = os.path.dirname(__file__)

granite = pd.read_csv(os.path.join(BASE_DIR, "granite_dataset.csv"), encoding="latin1")
marble  = pd.read_csv(os.path.join(BASE_DIR, "marble_dataset.csv"),  encoding="latin1")

# normalize column names
granite.columns = granite.columns.str.strip().str.lower()
marble.columns  = marble.columns.str.strip().str.lower()

# concat
df = pd.concat([granite, marble], ignore_index=True)
df.columns = df.columns.str.strip().str.lower()
df = df.loc[:, ~df.columns.duplicated()]

# convert price
df["price_min"] = pd.to_numeric(df.get("price_min"), errors="coerce")
df["price_max"] = pd.to_numeric(df.get("price_max"), errors="coerce")
df = df.dropna(subset=["price_min"])

# ======================
# NORMALIZE STYLE TAG -> style_tag_norm (เหลือ 4 แนวหลัก)
# ======================
CANON_STYLES = ["luxury", "minimal", "modern", "classic"]

def normalize_style_tag(val: str) -> str:
    if val is None:
        return ""
    s = str(val).lower().strip()
    if s in ["", "nan", "none", "-"]:
        return ""

    # split by comma/pipe/slash/underscore/space
    tokens = re.split(r"[,\|/]+|[\s_]+", s)
    tokens = [t.strip() for t in tokens if t.strip()]

    mapped = set()

    for t in tokens:
        # prefix (กันคำโดนตัด เช่น classic_luxu, artistic_luxur, bold_classi, ultra_luxur)
        if t.startswith("lux"):
            mapped.add("luxury")
        if t.startswith("min"):
            mapped.add("minimal")
        if t.startswith("mod"):
            mapped.add("modern")
        if t.startswith("cla"):
            mapped.add("classic")

        # synonyms (ปรับได้ตามที่อยากตีความ)
        if t in ["elegant", "premium", "resort"]:
            mapped.add("luxury")
        if t in ["rustic", "natural"]:
            mapped.add("classic")
        if t in ["artistic", "bold"]:
            mapped.add("modern")

    ordered = [x for x in CANON_STYLES if x in mapped]
    return "|".join(ordered)

if "style_tag" in df.columns:
    df["style_tag_norm"] = df["style_tag"].apply(normalize_style_tag)
else:
    df["style_tag_norm"] = ""

# combine text (ใช้ข้อมูลดิบ + norm ช่วยให้ similarity จับ intent ได้ดีขึ้น)
df["combined_text"] = df.astype(str).agg(" ".join, axis=1)

# ======================
# VECTORIZE
# ======================
vectorizer = TfidfVectorizer()
vectorizer.fit(df["combined_text"])

# ======================
# HELPERS
# ======================
def extract_budget(text: str):
    numbers = re.findall(r"\d+", text)
    return int(numbers[0]) if numbers else None

def _has_any(query_lower: str, keywords: list[str]) -> bool:
    return any(k in query_lower for k in keywords)

def _apply_style_filter(filtered_df: pd.DataFrame, query_lower: str) -> pd.DataFrame:
    col = "style_tag_norm" if "style_tag_norm" in filtered_df.columns else "style_tag"
    if col not in filtered_df.columns:
        return filtered_df

    STYLE_MAP = {
        "หรู": "luxury", "luxury": "luxury",
        "มินิมอล": "minimal", "minimal": "minimal",
        "โมเดิร์น": "modern", "modern": "modern",
        "คลาสสิก": "classic", "classic": "classic",
    }

    styles = []
    for k, v in STYLE_MAP.items():
        if k in query_lower and v not in styles:
            styles.append(v)

    if not styles:
        return filtered_df

    # AND logic: ต้อง match ทุกสไตล์ที่พิมพ์มา
    for s in styles:
        filtered_df = filtered_df[
            filtered_df[col].astype(str).str.contains(rf"(?:^|\|){s}(?:\||$)", na=False)
        ]
    return filtered_df

def parse_intent(q: str) -> dict:
    q = q.lower()
    return {
        "want_kitchen": _has_any(q, ["ครัว", "เคาน์เตอร์", "countertop", "kitchen", "island"]),
        "want_floor": _has_any(q, ["ปูพื้น", "พื้น", "floor"]),
        "want_wall": _has_any(q, ["ผนัง", "กรุผนัง", "wall", "cladding"]),
        "want_outdoor": _has_any(q, ["ภายนอก", "outdoor"]),
    }

def _select_diverse(result_df: pd.DataFrame, top_k: int) -> pd.DataFrame:
    """เลือก top_k แบบไม่ซ้ำกันเกินไป (ชื่อ/ประเทศ)"""
    if len(result_df) <= top_k:
        return result_df.head(top_k)

    picked_idx = []
    used_names = set()
    used_origins = set()

    for idx, r in result_df.iterrows():
        name = str(r.get("stone_name", "")).lower().strip()
        origin = str(r.get("origin_country", r.get("origin", ""))).lower().strip()

        if name and name in used_names:
            continue

        # กัน origin ซ้ำหนัก ๆ (ให้ซ้ำได้หลังเลือกไปแล้ว 2 ตัว)
        if origin and origin in used_origins and len(picked_idx) < 2:
            continue

        picked_idx.append(idx)
        if name:
            used_names.add(name)
        if origin:
            used_origins.add(origin)

        if len(picked_idx) >= top_k:
            break

    # ถ้าเลือกไม่ครบ ให้เติมเพิ่มจากอันดับถัดไป
    if len(picked_idx) < top_k:
        for idx in result_df.index:
            if idx not in picked_idx:
                picked_idx.append(idx)
            if len(picked_idx) >= top_k:
                break

    return result_df.loc[picked_idx].head(top_k)

# ======================
# RETRIEVE (FULL VERSION)
# ======================
def retrieve_stones(user_query: str, top_k: int = 3, stone_type: str | None = None) -> pd.DataFrame:
    filtered_df = df.copy()
    query_lower = user_query.lower()

    # 0) Stone Type Filter
    if stone_type in ["granite", "marble"] and "stone_type" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["stone_type"].astype(str).str.strip().str.lower() == stone_type
        ]

    # 1) Style Filter (จากคำถาม)
    filtered_df = _apply_style_filter(filtered_df, query_lower)

    # 2) Budget Filter (ถ้างบแล้วว่าง -> คืนว่างทันที)
    budget = extract_budget(user_query)
    budget_applied = False
    if budget:
        budget_applied = True
        filtered_df = filtered_df[filtered_df["price_min"] <= budget]

    # 3) Outdoor Filter
    want_outdoor = _has_any(query_lower, ["ภายนอก", "outdoor"])
    if want_outdoor and "indoor_outdoor" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["indoor_outdoor"].astype(str).str.lower().isin(["outdoor", "both"])
        ]

    # 4) Floor Filter
    want_floor = _has_any(query_lower, ["ปูพื้น", "floor"])
    if want_floor and "popular_use" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["popular_use"].astype(str).str.lower().str.contains("floor", na=False)
        ]

    # fallback เฉพาะกรณีไม่มีงบ
    if len(filtered_df) == 0:
        if budget_applied:
            return filtered_df.head(0)

        filtered_df = df.copy()
        if stone_type in ["granite", "marble"] and "stone_type" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["stone_type"].astype(str).str.strip().str.lower() == stone_type
            ]
        filtered_df = _apply_style_filter(filtered_df, query_lower)

        if len(filtered_df) == 0:
            return filtered_df.head(0)

    # =========================
    # Special Price Intent (ถูกสุด/แพงสุด) -> sort ตามราคาโดยตรง
    # =========================
    want_cheapest = _has_any(query_lower, ["ถูกสุด", "ถูกที่สุด", "ราคาต่ำสุด", "ต่ำสุด", "cheapest", "lowest"])
    want_expensive = _has_any(query_lower, ["แพงสุด", "แพงที่สุด", "ราคาสูงสุด", "สูงสุด", "most expensive", "highest"])

    if want_cheapest:
        result = filtered_df.sort_values(by="price_min", ascending=True)
        picked = _select_diverse(result, top_k)
        picked.attrs["confidence"] = None
        return picked

    if want_expensive:
        result = filtered_df.sort_values(by="price_min", ascending=False)
        picked = _select_diverse(result, top_k)
        picked.attrs["confidence"] = None
        return picked

    # =========================
    # Similarity + Rule Scoring (ADVANCED RANKING)
    # =========================
    temp_vectors = vectorizer.transform(filtered_df["combined_text"])
    query_vec = vectorizer.transform([user_query])
    similarity = cosine_similarity(query_vec, temp_vectors).flatten()

    filtered_df = filtered_df.copy()
    filtered_df["similarity"] = similarity

    intent = parse_intent(user_query)

    # usage score
    usage_score = pd.Series(0.0, index=filtered_df.index)
    if "popular_use" in filtered_df.columns:
        pu = filtered_df["popular_use"].astype(str).str.lower()
        if intent["want_kitchen"]:
            usage_score += pu.str.contains("counter|kitchen|island", na=False).astype(float) * 1.0
        if intent["want_floor"]:
            usage_score += pu.str.contains("floor", na=False).astype(float) * 1.0
        if intent["want_wall"]:
            usage_score += pu.str.contains("wall|cladding", na=False).astype(float) * 1.0

    # outdoor score
    outdoor_score = pd.Series(0.0, index=filtered_df.index)
    if intent["want_outdoor"] and "indoor_outdoor" in filtered_df.columns:
        io = filtered_df["indoor_outdoor"].astype(str).str.lower()
        outdoor_score += io.isin(["outdoor", "both"]).astype(float) * 1.0

    # budget closeness score (ถ้ามีงบ)
    budget_score = pd.Series(0.0, index=filtered_df.index)
    if budget:
        diff = (budget - filtered_df["price_min"]).clip(lower=0)
        denom = diff.max() if diff.max() > 0 else 1
        budget_score = 1 - (diff / denom)

    filtered_df["usage_score"] = usage_score
    filtered_df["outdoor_score"] = outdoor_score
    filtered_df["budget_score"] = budget_score

    # ✅ final score (ปรับน้ำหนักได้)
    filtered_df["final_score"] = (
        filtered_df["similarity"] * 0.55
        + usage_score * 0.25
        + outdoor_score * 0.10
        + budget_score * 0.10
    )

    result = filtered_df.sort_values(by="final_score", ascending=False)

    # confidence (ต่างคะแนน top1-top2)
    top_scores = result["final_score"].head(2).tolist()
    confidence = (top_scores[0] - top_scores[1]) if len(top_scores) > 1 else (top_scores[0] if top_scores else 0.0)

    picked = _select_diverse(result, top_k)
    picked.attrs["confidence"] = float(confidence) if confidence is not None else None
    return picked










