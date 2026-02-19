import os
import time
import random
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

from rag_system import retrieve_stones
from stone_dictionary import translate_field

# ==========================================================
# PAGE CONFIG + THEME
# ==========================================================
st.set_page_config(
    page_title="AI Stone Advisor",
    page_icon="🪨",
    layout="wide",
)

st.markdown(
    """
<style>
/* container width + spacing */
.block-container { padding-top: 1.3rem; padding-bottom: 2.2rem; max-width: 1100px; }

/* hide streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.hero-title {
  font-weight: 800;
  font-size: 2.2rem;
  background: linear-gradient(90deg, #6EE7F9, #A78BFA);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.section-title {
  font-weight: 700;
  font-size: 1.3rem;
  background: linear-gradient(90deg, #6EE7F9, #A78BFA);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 4px;
}
.section-sub {
  font-size: 0.9rem;
  opacity: 0.7;
}


/* hero */
.hero {
  padding: 18px 20px;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}
.hero h1 { margin: 0; font-size: 2.1rem; }
.hero p { margin: 6px 0 0; opacity: 0.85; line-height: 1.5; }

/* cards */
.card {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.03);
  box-shadow: 0 8px 22px rgba(0,0,0,0.22);
  margin-bottom: 12px;
}
.card h3 { margin: 0 0 6px 0; font-size: 1.12rem; }
.meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.badge {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.04);
  opacity: 0.95;
}
.dim { opacity: 0.8; }

/* chat spacing */
.stChatInput { margin-top: 8px; }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# CONFIG (Gemini key: secrets -> env)
# ==========================================================
load_dotenv()

api_key = None
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name="models/gemini-2.0-flash")
else:
    model = None

# ==========================================================
# SESSION STATE
# ==========================================================
if "await_requirements" not in st.session_state:
    st.session_state.await_requirements = False
if "prefill" not in st.session_state:
    st.session_state.prefill = ""

# ==========================================================
# HELPERS
# ==========================================================
def call_gemini_with_retry(_model, prompt: str, max_retries: int = 4) -> str | None:
    if _model is None:
        return None

    for attempt in range(max_retries):
        try:
            return _model.generate_content(prompt).text
        except Exception as e:
            msg = str(e)
            is_429 = ("429" in msg) or ("Resource exhausted" in msg) or ("ResourceExhausted" in msg)
            if is_429:
                time.sleep((2 ** attempt) + random.random())
                continue
            return None
    return None


def is_knowledge_question(text: str) -> bool:
    t = text.lower()
    keywords = ["ต่างกัน", "แตกต่าง", "คืออะไร", "ข้อดี", "ข้อเสีย", "ดีกว่า", "เปรียบเทียบ", "compare"]
    return any(k in t for k in keywords)


def looks_like_granite_vs_marble(text: str) -> bool:
    t = text.lower()
    has_granite = ("แกรนิต" in t) or ("granite" in t)
    has_marble = ("หินอ่อน" in t) or ("marble" in t)
    return has_granite and has_marble


def fallback_explain_granite_vs_marble() -> str:
    return (
        "สรุปความต่าง **หินแกรนิต vs หินอ่อน** แบบเข้าใจง่าย:\n"
        "- **ความแข็ง/ทนรอย**: แกรนิตมักทนรอยขีดข่วนและแรงกระแทกได้ดีกว่า\n"
        "- **ทนกรด/คราบ**: หินอ่อนแพ้กรด (เช่น มะนาว/น้ำส้มสายชู) มีโอกาสด่าง/เป็นรอยกัดผิวง่ายกว่า\n"
        "- **ลวดลาย**: หินอ่อนเด่นเรื่องลายเส้น (vein) ดูหรู แต่ต้องดูแลมากกว่า\n"
        "- **งานครัว**: ถ้าใช้งานหนัก/ทำอาหารบ่อย → มักเหมาะกับแกรนิตมากกว่า\n"
    )


def render_stone(row):
    stone_type_th = translate_field("stone_type", row.get("stone_type"))
    origin_th = translate_field("origin_country", row.get("origin_country"))
    usage_th = translate_field("indoor_outdoor", row.get("indoor_outdoor"))
    popular_use_th = translate_field("popular_use", row.get("popular_use"))

    style_val = row.get("style_tag_norm", row.get("style_tag", ""))
    style_val = str(style_val).replace("|", ", ")

    price = "-"
    try:
        price = f"{int(float(row.get('price_min'))):,}"
    except Exception:
        pass

    name = row.get("stone_name", "-")

    st.markdown(
        f"""
<div class="card">
  <h3>🪨 {stone_type_th} — <span class="dim">{name}</span></h3>
  <div class="meta">
    <span class="badge">💰 เริ่ม {price} บาท/ตร.ม.</span>
    <span class="badge">🌍 {origin_th}</span>
    <span class="badge">🏠 {popular_use_th}</span>
    <span class="badge">🌤 {usage_th}</span>
    <span class="badge">🎨 {style_val if style_val and style_val!='nan' else "-"}</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def build_facts_table(df):
    lines = []
    for _, r in df.iterrows():
        style_val = r.get("style_tag_norm", r.get("style_tag", ""))
        lines.append(
            f"- {r.get('stone_name')} | price_min={r.get('price_min')} | use={r.get('popular_use')} "
            f"| io={r.get('indoor_outdoor')} | style={style_val}"
        )
    return "\n".join(lines)


# ==========================================================
# HERO
# ==========================================================
st.markdown("""
<div class="hero">
  <h1 class="hero-title">🪨 AI Stone Advisor</h1>
  <p>พิมพ์งบประมาณ / การใช้งาน / สไตล์ หรือถามความรู้ได้เลย — ระบบจะแนะนำหินที่เหมาะ (พร้อมเหตุผลและการดูแล)</p>
</div>
""", unsafe_allow_html=True)

st.write("")

# ==========================================================
# CONTROLS (2 columns)
# ==========================================================
left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("⚙️ ตั้งค่า")
    stone_choice = st.radio(
        "เลือกประเภทหิน",
        ["Granite(หินแกรนิต)", "Marble(หินอ่อน)", "ไม่แน่ใจ (ให้ระบบเลือก)"],
        horizontal=True,
    )

    use_gemini = st.toggle("ใช้ AI อธิบาย (Gemini)", value=False, help="ถ้าเปิด อาจเจอโควต้า 429 ได้เวลาทดสอบถี่ ๆ")

    if not api_key:
        st.warning("ยังไม่พบ GEMINI_API_KEY (Secrets/Environment) — โหมด AI อธิบายจะใช้งานไม่ได้", icon="⚠️")

    st.caption("Tip: ตอนทดสอบหลายคำถาม แนะนำปิด Gemini กันโควต้า 429")

with right:
    st.markdown("<div class='section-title'>✨ แนะนำคำถามยอดนิยม</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-sub'>คลิกเพื่อทดลองแนะนำหินทันที หรือพิมพ์คำถามเองด้านล่าง</div>", unsafe_allow_html=True)


    st.write("")

    # ใช้ 2 แถว 2 คอลัมน์ แทน 3 คอลัมน์
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)

    if r1c1.button("ทำครัว งบ 3000 minimal", use_container_width=True):
        st.session_state.prefill = "ทำครัว งบ 3000 minimal"

    if r1c2.button("งบ 2500 ปูพื้นภายนอก modern", use_container_width=True):
        st.session_state.prefill = "งบ 2500 ปูพื้นภายนอก modern"

    if r2c1.button("ขอหินแกรนิตที่ถูกที่สุด", use_container_width=True):
        st.session_state.prefill = "ขอหินแกรนิตที่ถูกที่สุด"

    if r2c2.button("หินแกรนิตกับหินอ่อนต่างกันยังไง", use_container_width=True):
        st.session_state.prefill = "หินแกรนิตกับหินอ่อนต่างกันยังไง"

    st.write("")
    st.caption("ถามความรู้ก็ได้ เช่น เปรียบเทียบข้อดีข้อเสีย")


# determine stone_type for retrieve
choice_lower = stone_choice.lower()
if "granite" in choice_lower:
    stone_type = "granite"
elif "marble" in choice_lower:
    stone_type = "marble"
else:
    stone_type = None

st.divider()

# ==========================================================
# CHAT
# ==========================================================
prefill = st.session_state.get("prefill", "")
user_input = st.chat_input("พิมพ์งบ / การใช้งาน / สไตล์ หรือถามความรู้ได้เลย")

# ถ้ากดตัวอย่าง: ใช้เป็น input รอบนี้
if prefill and not user_input:
    user_input = prefill
    st.session_state.prefill = ""

if user_input:
    st.chat_message("user").write(user_input)

    # ======================================
    # MODE A: กำลังรอ requirement (หลังตอบความรู้)
    # ======================================
    if st.session_state.await_requirements:
        st.session_state.await_requirements = False

        retrieved = retrieve_stones(user_input, stone_type=stone_type)

        if retrieved is None or len(retrieved) == 0:
            st.chat_message("assistant").write(
                "ไม่มีหินที่อยู่ในงบหรือเงื่อนไขนี้ครับ 🙏\n"
                "แนะนำให้เพิ่มงบ หรือปรับเงื่อนไข (การใช้งาน/สไตล์) แล้วลองใหม่อีกครั้ง"
            )
            st.stop()

        st.subheader("✅ ตัวเลือกที่แนะนำ")
        for _, row in retrieved.iterrows():
            render_stone(row)

        # optional: explain with Gemini using facts (กันเดามั่ว)
        if use_gemini:
            facts = build_facts_table(retrieved)
            prompt = f"""
ใช้ข้อมูลด้านล่างเท่านั้นในการสรุป ห้ามเดาราคาเอง ห้ามเปลี่ยนข้อมูล

ประเภทหินที่ผู้ใช้เลือก: {stone_choice}
ความต้องการ: {user_input}

ตัวเลือก:
{facts}

เลือก 1 ตัวที่เหมาะที่สุด
เหตุผลสั้น กระชับ ชัดเจน (อ้างอิงจาก ราคา/การใช้งาน/indoor_outdoor/style)
ข้อดี/ข้อเสีย
แนะนำการดูแลรักษา
ตอบภาษาไทย
"""
            answer = call_gemini_with_retry(model, prompt)
            if answer:
                st.chat_message("assistant").write(answer)
            else:
                st.chat_message("assistant").write(
                    "ตอนนี้ AI อธิบายติดโควต้า/ใช้งานไม่ได้ชั่วคราว แต่ตัวเลือกด้านบนคือ Top ที่เหมาะสุดแล้ว ✅"
                )

        st.stop()

    # ======================================
    # MODE B: Knowledge / Compare -> explain + ask follow-up
    # ======================================
    if is_knowledge_question(user_input) or looks_like_granite_vs_marble(user_input):
        if use_gemini:
            prompt = f"""
ตอบคำถามเชิงความรู้เกี่ยวกับหินก่อสร้างเป็นภาษาไทยแบบเข้าใจง่าย (จัดเป็นหัวข้อสั้น ๆ)

คำถาม: {user_input}

จากนั้นถามต่อ 1 ประโยค เพื่อเก็บความต้องการลูกค้าให้ครบ (ส่วนที่ใช้/งบ/สไตล์)
ให้ถามสั้น กระชับ แต่ครอบคลุม
"""
            answer = call_gemini_with_retry(model, prompt)
            if not answer:
                answer = fallback_explain_granite_vs_marble() + "\n\nอยากเอาไปใช้ทำส่วนไหน (ครัว/พื้น/ผนัง/ภายนอก) งบประมาณเท่าไหร่ และอยากได้สไตล์ไหนครับ?"
        else:
            if looks_like_granite_vs_marble(user_input):
                answer = fallback_explain_granite_vs_marble() + "\n\nอยากเอาไปใช้ทำส่วนไหน (ครัว/พื้น/ผนัง/ภายนอก) งบประมาณเท่าไหร่ และอยากได้สไตล์ไหนครับ?"
            else:
                answer = "ได้ครับ 👍 อยากเอาไปใช้ทำส่วนไหน (ครัว/พื้น/ผนัง/ภายนอก) งบประมาณเท่าไหร่ และอยากได้สไตล์ไหนครับ?"

        st.chat_message("assistant").write(answer)
        st.session_state.await_requirements = True
        st.stop()

    # ======================================
    # MODE C: Product recommendation (default)
    # ======================================
    retrieved = retrieve_stones(user_input, stone_type=stone_type)

    if retrieved is None or len(retrieved) == 0:
        st.chat_message("assistant").write(
            "ไม่มีหินที่อยู่ในงบหรือเงื่อนไขนี้ครับ 🙏\n"
            "แนะนำให้เพิ่มงบ หรือปรับเงื่อนไข (การใช้งาน/สไตล์) แล้วลองใหม่อีกครั้ง"
        )
        st.stop()

    st.subheader("✅ ตัวเลือกที่แนะนำ")
    for _, row in retrieved.iterrows():
        render_stone(row)

    if use_gemini:
        facts = build_facts_table(retrieved)
        prompt = f"""
ใช้ข้อมูลด้านล่างเท่านั้นในการสรุป ห้ามเดาราคาเอง ห้ามเปลี่ยนข้อมูล

ประเภทหินที่ผู้ใช้เลือก: {stone_choice}
ความต้องการ: {user_input}

ตัวเลือก:
{facts}

เลือก 1 ตัวที่เหมาะที่สุด
เหตุผลสั้น กระชับ ชัดเจน (อ้างอิงจาก ราคา/การใช้งาน/indoor_outdoor/style)
ข้อดี/ข้อเสีย
แนะนำการดูแลรักษา
ตอบภาษาไทย
"""
        answer = call_gemini_with_retry(model, prompt)
        if answer:
            st.chat_message("assistant").write(answer)
        else:
            st.chat_message("assistant").write(
                "ตอนนี้ AI อธิบายติดโควต้า/ใช้งานไม่ได้ชั่วคราว แต่ตัวเลือกด้านบนคือ Top ที่เหมาะสุดแล้ว ✅"
            )






