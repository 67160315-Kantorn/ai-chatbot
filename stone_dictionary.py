STONE_TRANSLATIONS = {

    # =========================
    # Stone Type
    # =========================
    "stone_type": {
        "granite": "หินแกรนิต",
        "marble": "หินอ่อน"
    },

    # =========================
    # Origin Country
    # =========================
    "origin_country": {
        "italy": "อิตาลี",
        "spain": "สเปน",
        "brazil": "บราซิล",
        "india": "อินเดีย",
        "china": "จีน",
        "vietnam": "เวียดนาม",
        "turkey": "ตุรกี",
        "greece": "กรีซ",
        "norway": "นอร์เวย์"
    },

    # =========================
    # Colors
    # =========================
    "color": {
        "white": "ขาว",
        "black": "ดำ",
        "grey": "เทา",
        "gray": "เทา",
        "beige": "เบจ",
        "cream": "ครีม",
        "brown": "น้ำตาล",
        "gold": "ทอง",
        "red": "แดง",
        "green": "เขียว",
        "blue": "น้ำเงิน"
    },

    # =========================
    # Tone
    # =========================
    "color_tone": {
        "warm": "โทนอุ่น",
        "cool": "โทนเย็น",
        "neutral": "โทนกลาง"
    },

    # =========================
    # Pattern
    # =========================
    "pattern_type": {
        "solid": "สีพื้น",
        "speckled": "ลายเกล็ด",
        "veined": "ลายเส้น",
        "cloudy": "ลายเมฆ",
        "marbled": "ลายหินอ่อน",
        "granular": "ลายเม็ด"
    },

    # =========================
    # Style
    # =========================
    "style_tag": {
        "modern": "โมเดิร์น",
        "luxury": "หรูหรา",
        "classic": "คลาสสิก",
        "minimal": "มินิมอล",
        "industrial": "อินดัสเทรียล",
        "contemporary": "ร่วมสมัย"
    },

    # =========================
    # Popular Use
    # =========================
    "popular_use": {
        "flooring": "ปูพื้น",
        "staircase": "บันได",
        "outdoor_paving": "ปูพื้นภายนอก",
        "wall_cladding": "กรุผนัง",
        "countertop": "เคาน์เตอร์ครัว",
        "vanity_top": "ท็อปอ่างล้างหน้า",
        "feature_wall": "ผนังตกแต่ง",
        "table_top": "ท็อปโต๊ะ",
        "kitchen_counter": "เคาน์เตอร์ครัว",
        "stairs": "บันได",
        "floor": "พื้น",
        "wall": "ผนัง",
        "island": "เคาน์เตอร์ครัวกลางห้อง",
        "bathroom": "ห้องน้ำ",
        "classic_space": "พื้นที่สไตล์คลาสสิก",
        "bar_counter": "เคาน์เตอร์บาร์",
    },

    # =========================
    # Indoor / Outdoor
    # =========================
    "indoor_outdoor": {
        "indoor": "ใช้ภายใน",
        "outdoor": "ใช้ภายนอก",
        "both": "ใช้ได้ทั้งภายในและภายนอก"
    },

    # =========================
    # Luxury Level
    # =========================
    "luxury_level": {
        "standard": "มาตรฐาน",
        "mid": "ระดับกลาง",
        "high": "ระดับสูง",
        "premium": "พรีเมียม"
    },

    # =========================
    # Marble Specific
    # =========================
    "vein_intensity": {
        "low": "ลายเส้นน้อย",
        "medium": "ลายเส้นปานกลาง",
        "high": "ลายเส้นชัดเจน"
    },

    "vein_direction": {
        "horizontal": "ลายแนวนอน",
        "vertical": "ลายแนวตั้ง",
        "diagonal": "ลายเฉียง",
        "random": "ลายอิสระ"
    },

    "background_cleanliness": {
        "clean": "พื้นสะอาดเรียบ",
        "moderate": "พื้นมีลวดลายเล็กน้อย",
        "busy": "พื้นลวดลายชัดเจน"
    },

    "bookmatch_potential": {
        "low": "ไม่เหมาะทำบุ๊คแมทช์",
        "medium": "ทำบุ๊คแมทช์ได้",
        "high": "เหมาะทำบุ๊คแมทช์"
    },

    "translucency_level": {
        "none": "ไม่โปร่งแสง",
        "low": "โปร่งแสงเล็กน้อย",
        "high": "โปร่งแสงสูง"
    },

    "surface_recommendation": {
        "polished": "ผิวขัดเงา",
        "honed": "ผิวด้าน",
        "flamed": "ผิวไฟลน",
        "leathered": "ผิวสัมผัสหนัง",
        "brushed": "ผิวขัดแปรง"
    }
}
def translate_field(field_name, value):
    if not value:
        return "-"

    dictionary = STONE_TRANSLATIONS.get(field_name)

    if not dictionary:
        return value  # ไม่มี dictionary ก็คืนค่าเดิม

    # รองรับ comma-separated values
    if isinstance(value, str) and "," in value:
        items = [v.strip().lower() for v in value.split(",")]
        translated = [dictionary.get(v, v) for v in items]
        return ", ".join(translated)

    return dictionary.get(str(value).lower(), value)
