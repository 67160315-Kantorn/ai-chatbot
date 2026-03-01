import os
import time
import csv
import random

import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

# ==========================================================
# PAGE CONFIG + CSS
# ==========================================================
st.set_page_config(
    page_title="AI Stone Advisor",
    page_icon="🪨",
    layout="wide",
)

st.markdown(
    """
<style>
.block-container {
  padding-top: 1.3rem;
  padding-bottom: 2.2rem;
  max-width: 1100px;
}

/* hide default chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* hero */
.hero {
  padding: 18px 20px;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}
.hero-title {
  font-weight: 800;
  font-size: 2.2rem;
  background: linear-gradient(90deg, #6EE7F9, #A78BFA);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 20px rgba(167,139,250,0.35);
}
.hero p {
  margin: 6px 0 0;
  opacity: 0.85;
  line-height: 1.5;
}

/* section title (แนะนำคำถาม) */
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

/* card (เผื่อจะใช้ในอนาคต) */
.card {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.03);
  box-shadow: 0 8px 22px rgba(0,0,0,0.22);
  margin-bottom: 12px;
}
.card h3 {
  margin: 0 0 6px 0;
  font-size: 1.12rem;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
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

/* make buttons look like chips */
div.stButton > button {
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.04);
}
div.stButton > button:hover {
  background: rgba(255,255,255,0.08);
}

/* chat input spacing */
.stChatInput {
  margin-top: 8px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# CONFIG GEMINI
# ==========================================================
load_dotenv()

api_key = None
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("ไม่พบ GEMINI_API_KEY (ใน Secrets หรือ .env) ทำงานต่อไม่ได้", icon="🚨")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-2.0-flash")

BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "siamtak_granite.csv")  # ใช้ไฟล์ scrape ของมึง

# ==========================================================
# SESSION STATE
# ==========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role": "user"/"assistant", "content": "..."}]
if "prefill" not in st.session_state:
    st.session_state.prefill = ""

# ==========================================================
# HELPERS
# ==========================================================
def load_products_context() -> str:
    """
    โหลดข้อมูลหินจาก siamtak_granite.csv
    รวมเป็นข้อความยาว ๆ ให้ Gemini ใช้เป็น knowledge
    """
    if not os.path.exists(CSV_PATH):
        return ""

    lines: list[str] = []
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("product_title") or "").strip()
            desc = (row.get("product_description") or "").strip()
            price = (row.get("product_price") or "").strip().replace(",", "")

            if not title:
                continue

            lines.append(
                f"- ชื่อ: {title} | ราคา: {price} บาท/ตร.ม. | รายละเอียด: {desc}"
            )

    if not lines:
        return ""

    block = "\n".join(lines)

    context = (
        "คุณเป็นผู้เชี่ยวชาญด้านหินแกรนิตและงานตกแต่งภายในของโชว์รูมหินในประเทศไทย\n"
        "ต่อไปนี้คือรายการหินแกรนิตทั้งหมดที่มีอยู่ในระบบ (ข้อมูลจริงจากไฟล์ CSV):\n"
        f"{block}\n\n"
        "ให้คุณใช้ข้อมูลด้านบนในการแนะนำลูกค้าเท่านั้น ห้ามสร้างชื่อหินหรือราคาขึ้นมาเอง\n"
    )
    return context


def stream_chat_markdown(text: str):
    """ให้ assistant พิมพ์แบบค่อย ๆ ขึ้นเหมือน ChatGPT"""
    container = st.chat_message("assistant")
    placeholder = container.empty()

    rendered = ""
    for chunk in text.split(" "):  # พิมพ์ทีละคำ
        rendered += chunk + " "
        placeholder.markdown(rendered)
        time.sleep(0.03)
    placeholder.markdown(rendered)


def call_gemini_with_retry(prompt: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            resp = model.generate_content(prompt)
            return resp.text or ""
        except Exception as e:
            msg = str(e)
            is_429 = ("429" in msg) or ("Resource exhausted" in msg)
            if is_429 and attempt < max_retries - 1:
                # backoff เบา ๆ กันโดน spam
                time.sleep((2 ** attempt) + random.random())
                continue
            return f"ขออภัย ระบบ AI มีปัญหาชั่วคราว: {e}"
    return "ขออภัย ระบบ AI ตอบไม่ได้ในตอนนี้"

# ==========================================================
# HERO
# ==========================================================
st.markdown(
    """
<div class="hero">
  <h1 class="hero-title">🪨 AI Stone Advisor</h1>
  <p>เวอร์ชันใช้ Gemini + CSV จาก siamtak_granite โดยตรง (ไม่ใช้ RAG) — พิมพ์ความต้องการ แล้วระบบจะช่วยเลือกหินให้</p>
</div>
""",
    unsafe_allow_html=True,
)
st.write("")

# ==========================================================
# CONTROLS / EXAMPLES
# ==========================================================
left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("⚙️ ตั้งค่า")
    st.caption("ตอนนี้ demo ใช้เฉพาะหินแกรนิตจากไฟล์ siamtak_granite.csv")

with right:
    st.markdown(
        "<div class='section-title'>✨ แนะนำคำถามยอดนิยม</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='section-sub'>คลิกเพื่อใส่คำถามอัตโนมัติ หรือพิมพ์เองในช่องด้านล่าง</div>",
        unsafe_allow_html=True,
    )
    st.write("")

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

st.divider()

# ==========================================================
# แสดงประวัติแชทเดิม
# ==========================================================
for m in st.session_state.messages:
    st.chat_message(m["role"]).markdown(m["content"])

# ==========================================================
# CHAT INPUT (แก้จากของเดิม: ไม่ใช้ value= แล้ว)
# ==========================================================
prefill = st.session_state.get("prefill", "")

# chat_input ไม่มีพารามิเตอร์ value → เลยใช้ pattern นี้แทน
user_input_raw = st.chat_input("พิมพ์งบ / การใช้งาน / สไตล์ หรือคำถามเกี่ยวกับหินแกรนิตได้เลย")
user_input = user_input_raw

# ถ้ามี prefill (จากปุ่มตัวอย่าง) และผู้ใช้ยังไม่พิมพ์อะไร → ใช้ prefill เป็นข้อความ
if prefill and not user_input_raw:
    user_input = prefill
    st.session_state.prefill = ""  # ใช้แล้วเคลียร์

if user_input:
    # เก็บประวัติ
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").markdown(user_input)

    # โหลด context จาก CSV
    context = load_products_context()
    if not context:
        msg = "ยังไม่มีข้อมูลหินในระบบ (อ่านไฟล์ siamtak_granite.csv ไม่ได้)"
        st.chat_message("assistant").write(msg)
        st.session_state.messages.append({"role": "assistant", "content": msg})
    else:
        prompt = f"""
{context}

ตอนนี้ลูกค้าถามว่า:
\"\"\"{user_input}\"\"\"

ให้คุณ:
1) สรุปความต้องการของลูกค้าแบบสั้น ๆ
2) เลือกหินที่เหมาะสมที่สุด 1–3 แบบ จาก "รายการด้านบนเท่านั้น" (ห้ามสร้างชื่อหินใหม่)
   - ระบุชื่อหินให้ตรงตามรายการ
   - ระบุช่วงราคาให้ตรงตามข้อมูล
3) อธิบายเหตุผล (เรื่องงบประมาณ การใช้งาน พื้น/ผนัง/ครัว ภายใน/ภายนอก สไตล์ ฯลฯ)
4) บอกข้อดี/ข้อเสียอย่างย่อ และแนะนำการดูแลรักษา
5) ถ้าไม่มีหินที่อยู่ในงบ ให้บอกตรง ๆ ว่า "ไม่มีในงบ" และแนะนำช่วงงบที่เหมาะสมแทน

ตอบเป็นภาษาไทยทั้งหมด จัดรูปแบบให้อ่านง่ายเป็นหัวข้อ/รายการ
"""

        answer = call_gemini_with_retry(prompt)

        # แสดงแบบค่อย ๆ พิมพ์
        stream_chat_markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})






