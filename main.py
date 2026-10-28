import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from streamlit_cropper import st_cropper
from streamlit_local_storage import LocalStorage
import json
import time
from logo_data import LOGO_DATA

st.set_page_config(page_title="지문.zip", page_icon="logo.png", layout="wide")

try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=gemini_api_key)
except Exception:
    client = None

try:
    local_storage = LocalStorage()
except Exception:
    local_storage = None

if "exam_scope" not in st.session_state:
    st.session_state.exam_scope = []
if "exam_scope_storage_loaded" not in st.session_state:
    st.session_state.exam_scope_storage_loaded = False
if "exam_scope_storage_attempts" not in st.session_state:
    st.session_state.exam_scope_storage_attempts = 0
if "current_passage" not in st.session_state:
    st.session_state.current_passage = ""
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "uploaded_image_bytes" not in st.session_state:
    st.session_state.uploaded_image_bytes = None
if "uploaded_image_name" not in st.session_state:
    st.session_state.uploaded_image_name = ""

EXAM_SCOPE_STORAGE_KEY = "jipmunzip_exam_scope"


def load_exam_scope_from_browser():
    if local_storage is None or st.session_state.exam_scope_storage_loaded:
        return
    try:
        saved_scope = local_storage.getItem(EXAM_SCOPE_STORAGE_KEY)
        st.session_state.exam_scope_storage_attempts += 1
        if saved_scope:
            if isinstance(saved_scope, str):
                saved_scope = json.loads(saved_scope)
            if isinstance(saved_scope, list):
                st.session_state.exam_scope = saved_scope
            st.session_state.exam_scope_storage_loaded = True
        elif st.session_state.exam_scope_storage_attempts >= 2:
            st.session_state.exam_scope_storage_loaded = True
    except Exception:
        st.session_state.exam_scope_storage_loaded = True


def save_exam_scope_to_browser():
    if local_storage is None:
        return False
    try:
        local_storage.setItem(
            EXAM_SCOPE_STORAGE_KEY,
            json.dumps(st.session_state.exam_scope, ensure_ascii=False),
        )
        return True
    except Exception:
        return False


load_exam_scope_from_browser()

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "original_text": {"type": "string", "description": "입력되거나 사진에서 읽은 영어 지문의 원문"},
        "korean_title": {"type": "string", "description": "지문의 핵심 주제를 보여주는 한국어 제목"},
        "english_title": {"type": "string", "description": "지문의 핵심 주제를 보여주는 영어 제목"},
        "logical_flow": {
            "type": "object",
            "properties": {
                "beginning": {"type": "string", "description": "처음 부분의 주제·문제·상황 제시를 자연스럽게 의역한 설명"},
                "middle": {"type": "string", "description": "중간 부분의 핵심 주장·설명·근거 전개를 자연스럽게 의역한 설명"},
                "end": {"type": "string", "description": "끝부분의 결론·핵심 메시지를 자연스럽게 의역한 설명"},
                "examples": {"type": "array", "items": {"type": "string"}, "description": "지문에 실제로 등장하는 예시. 없으면 빈 배열"}
            },
            "required": ["beginning", "middle", "end", "examples"]
        },
        "key_sentence": {"type": "string", "description": "지문의 주제를 가장 잘 보여주는 원문 문장 1개"},
        "vocabulary": {"type": "array", "items": {"type": "string"}, "description": "내신에 중요한 영어 단어와 한국어 뜻 5개"},
        "grammar": {"type": "array", "items": {"type": "string"}, "description": "지문에서 중요한 문법 또는 표현 3개와 설명"},
        "keywords": {"type": "array", "items": {"type": "string"}, "description": "지문 전체 내용을 기억하기 위한 핵심 키워드 3개"}
    },
    "required": ["original_text", "korean_title", "english_title", "logical_flow", "key_sentence", "vocabulary", "grammar", "keywords"]
}

SYSTEM_PROMPT = """
너는 영어 내신 지문을 분석하는 학습 보조 AI이다.

목적은 지문을 단순히 짧게 요약하는 것이 아니라, 학생이 시험 직전에 지문의 주제와 논리적 흐름을 빠르게 떠올릴 수 있도록 분석지를 만드는 것이다.

반드시 다음 원칙을 지킨다.
1. 지문에 없는 내용을 임의로 추가하지 않는다.
2. 원문의 의미를 왜곡하지 않는다.
3. 지문의 전개를 '처음 → 중간 → 끝'의 흐름으로 파악한다.
4. 처음에는 주제·문제·상황이 어떻게 제시되는지 설명한다.
5. 중간에는 핵심 주장, 설명, 근거가 어떤 관계로 이어지는지 설명한다.
6. 끝에는 앞의 내용이 어떤 결론이나 핵심 메시지로 이어지는지 설명한다.
7. 지문에 실제 예시가 있는 경우 examples에 넣고, 그 예시가 무엇을 설명하거나 뒷받침하는지도 반영한다.
8. 지문에 예시가 없으면 examples는 빈 배열로 둔다. 예시를 새로 만들지 않는다.
9. key_sentence는 새로 만든 문장이 아니라 반드시 원문에 실제로 존재하는 문장을 그대로 반환한다.
10. 여러 문장이 핵심이면 주제를 가장 직접적으로 드러내는 원문 문장 1개를 선택한다.
11. 영어 단어는 지문에 실제로 등장하거나 지문 이해에 직접적으로 중요한 단어를 선정한다.
12. 문법은 지문에 실제로 나타난 문법이나 표현을 선정한다.
13. 사진 입력의 경우 사진 속 영어 문장을 최대한 정확하게 그대로 옮긴다.
14. 논리 흐름은 문장별 번역이 아니라 '왜 다음 내용이 나오는지'가 보이도록 작성한다.
15. 논리 흐름은 영어 문장을 한국어로 직역하는 번역문이 아니라, 원문의 의미와 논리 관계를 학생이 이해하기 쉽게 설명하는 자연스러운 한국어 의역으로 작성한다.
16. 영어의 비유적 표현, 관용 표현, 구어적 표현은 한국어 문맥에서 자연스럽게 이해되는 표현으로 바꾼다. 단어의 사전적 의미를 그대로 옮겼을 때 한국어로 어색하면 문맥상 의미를 우선한다.
17. '쌈짓돈', '주머니 돈'처럼 영어 표현을 단어 그대로 옮긴 듯한 구어적·부자연스러운 표현은 피한다. 문맥에 맞게 '소액 자금', '개인의 소액 자금', '대중의 소액 투자금' 등 자연스럽고 정확한 표현을 선택한다.
18. 의역하더라도 원문에 없는 새로운 사실, 사례, 주장, 평가를 추가하지 않는다. 자연스럽게 바꾸는 것과 내용을 새로 만드는 것을 구분한다.
19. 논리 흐름의 각 단계는 시험 직전에 읽었을 때 글의 전개가 바로 떠오를 정도로 간결하게 작성한다.
20. 불필요하게 길게 쓰지 말고 시험 직전 복습에 적합한 정도로 압축한다.

결과 항목:
original_text: 입력된 영어 지문 원문
korean_title: 핵심 주제를 보여주는 자연스러운 한국어 제목
english_title: 핵심 주제를 보여주는 자연스러운 영어 제목
logical_flow: 처음·중간·끝의 논리적 전개를 자연스럽게 의역한 설명과 실제 예시
key_sentence: 원문에 실제로 존재하는 핵심 주제문장 1개
vocabulary: 중요한 영어 단어 5개, '영어 단어 - 한국어 뜻' 형식
grammar: 중요한 문법 또는 표현 3개와 짧은 설명
keywords: 전체 내용을 기억하기 위한 핵심 키워드 3개
"""

def generate_with_gemini(contents):
    if client is None:
        return None, "Gemini API 키가 설정되지 않았습니다."
    for model in ["gemini-3.8-flash", "gemini-3.7-flash"]:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=RESULT_SCHEMA
                    )
                )
                if response.text:
                    return response, None
            except Exception as e:
                error_message = str(e)
                if "503" in error_message or "UNAVAILABLE" in error_message:
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    break
                if "429" in error_message or "quota" in error_message.lower() or "resource exhausted" in error_message.lower():
                    return None, "Gemini 무료 사용량 또는 요청 한도에 도달했어요. 잠시 후 다시 시도해주세요."
                return None, "AI 분석 중 오류가 발생했습니다.\n\n오류 내용: " + error_message
    return None, "현재 Gemini AI 서버가 혼잡해서 분석을 완료하지 못했어요.\n\n잠시 후 다시 '지문 분석하기'를 눌러주세요."

def analyze_with_ai(passage=None, image=None):
    if client is None:
        return None, "Gemini API 키가 설정되지 않았습니다."
    if passage is not None:
        response, error = generate_with_gemini(SYSTEM_PROMPT + "\n\n다음 영어 지문을 분석해줘.\n\n" + passage)
    elif image is not None:
        response, error = generate_with_gemini([SYSTEM_PROMPT + "\n\n첨부된 사진 속 영어 지문을 읽고 분석해줘.", image])
    else:
        return None, "분석할 지문이 없습니다."
    if error:
        return None, error
    try:
        result = json.loads(response.text)
    except Exception:
        return None, "AI의 분석 결과를 읽는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    for key in ["original_text", "korean_title", "english_title", "logical_flow", "key_sentence", "vocabulary", "grammar", "keywords"]:
        if key not in result:
            return None, f"AI 분석 결과에 '{key}' 항목이 없습니다. 다시 분석해주세요."
    return result, None

def optimize_image(image):
    image = image.convert("RGB")
    max_side = 2800
    if max(image.size) > max_side:
        ratio = max_side / max(image.size)
        image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=92, optimize=True)
    return Image.open(BytesIO(buffer.getvalue())), buffer.getvalue()

def save_to_exam_scope(passage, result):
    if not passage.strip():
        return False
    for item in st.session_state.exam_scope:
        if item["passage"] == passage:
            return False
    st.session_state.exam_scope.append({"passage": passage, "result": result})
    save_exam_scope_to_browser()
    return True

st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:0.5rem;">
        <img src="{LOGO_DATA}" style="width:72px; height:72px; object-fit:contain;">
        <span style="font-size:2.5rem; font-weight:700;">지문.zip</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("영어 내신 지문을 한눈에 정리하다.")
st.divider()

st.subheader("📝 영어 지문")
input_method = st.radio("지문 입력 방법", ["직접 입력", "사진 업로드"], horizontal=True)
st.caption("⚡ 빠른 분석을 원한다면 직접 입력을 추천해요. 사진 업로드는 이미지 처리 과정이 추가되어 조금 더 시간이 걸릴 수 있어요.")
passage = ""
uploaded_image = None

if input_method == "직접 입력":
    st.session_state.uploaded_image_bytes = None
    passage = st.text_area("분석할 영어 지문을 입력하세요.", height=260, placeholder="영어 지문을 여기에 붙여넣어 주세요.")
else:
    uploaded_image = st.file_uploader("영어 지문 사진을 업로드하세요.", type=["png", "jpg", "jpeg"], help="영어 지문이 잘 보이도록 사진을 업로드하세요.")
    if uploaded_image is not None:
        try:
            original_image = Image.open(uploaded_image)
            st.session_state.uploaded_image_name = uploaded_image.name
            st.markdown("**✂️ 지문 영역을 맞춰주세요**")
            st.caption("영어 지문이 포함된 부분만 남기면 인식과 분석이 더 효율적이에요.")
            cropped_image = st_cropper(original_image, realtime_update=True, box_color="#ff5a5f", aspect_ratio=None, return_type="image")
            optimized_image, optimized_bytes = optimize_image(cropped_image)
            st.session_state.uploaded_image_bytes = optimized_bytes
            st.image(optimized_image, caption="AI 분석에 사용할 이미지", use_container_width=True)
            st.info("사진 속 영어 지문을 AI가 직접 읽고 분석합니다. 글자가 흐려지지 않도록 인식에 필요한 해상도는 유지해요.")
        except Exception as e:
            st.error("사진을 처리하는 중 오류가 발생했습니다: " + str(e))
    elif st.session_state.uploaded_image_bytes is not None:
        st.info(f"사진이 준비되어 있습니다: {st.session_state.uploaded_image_name}")

if st.button("✨ 지문 분석하기", use_container_width=True, type="primary"):
    if input_method == "직접 입력":
        if not passage.strip():
            st.session_state.analysis_result = None
            st.session_state.current_passage = ""
            st.warning("⚠️ 분석할 영어 지문이 없습니다. 지문을 입력한 후 다시 눌러주세요.")
        elif len(passage.strip()) < 10:
            st.warning("⚠️ 지문이 너무 짧습니다. 영어 지문을 조금 더 입력해주세요.")
        else:
            with st.spinner("🤖 AI가 지문의 주제와 논리 흐름을 분석하고 있어요..."):
                result, error = analyze_with_ai(passage=passage.strip())
            if error:
                st.error("❌ AI 분석에 실패했습니다.")
                st.caption(error)
                st.info("잠시 후 다시 '지문 분석하기'를 눌러주세요.")
            else:
                st.session_state.current_passage = result["original_text"]
                st.session_state.analysis_result = result
                st.success("✨ 지문 분석이 완료되었습니다!")
    else:
        image_bytes = st.session_state.uploaded_image_bytes
        if image_bytes is None:
            st.session_state.analysis_result = None
            st.session_state.current_passage = ""
            st.warning("⚠️ 먼저 영어 지문 사진을 업로드해주세요.")
        else:
            try:
                image = Image.open(BytesIO(image_bytes))
                with st.spinner("🤖 AI가 사진 속 지문의 주제와 논리 흐름을 분석하고 있어요..."):
                    result, error = analyze_with_ai(image=image)
                if error:
                    st.error("❌ 사진 속 지문 AI 분석에 실패했습니다.")
                    st.caption(error)
                    st.info("사진의 글자가 잘 보이는지 확인한 후 다시 시도해주세요.")
                else:
                    st.session_state.current_passage = result["original_text"]
                    st.session_state.analysis_result = result
                    st.success("✨ 사진 속 지문 분석이 완료되었습니다!")
            except Exception as e:
                st.error("❌ 사진을 처리하는 중 오류가 발생했습니다.")
                st.caption("오류 내용: " + str(e))

if st.session_state.analysis_result is not None:
    result = st.session_state.analysis_result
    st.divider()
    st.subheader("📖 분석 결과")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🇰🇷 한글 제목")
        st.info(result["korean_title"])
    with col2:
        st.markdown("### 🇺🇸 English Title")
        st.info(result["english_title"])

    st.markdown("### 🧭 논리 흐름")
    flow = result["logical_flow"]
    st.markdown(f"**① 처음**  {flow['beginning']}")
    st.markdown(f"**② 중간**  {flow['middle']}")
    if flow.get("examples"):
        for example in flow["examples"]:
            st.markdown(f"**예시)** {example}")
    st.markdown(f"**③ 끝**  {flow['end']}")

    st.markdown("### 📌 핵심 주제문장")
    st.info(result["key_sentence"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔤 중요 단어")
        for word in result["vocabulary"]:
            st.write(f"• {word}")
    with col2:
        st.markdown("### 📐 중요 문법")
        for grammar in result["grammar"]:
            st.write(f"• {grammar}")

    st.markdown("### 🔑 3단 핵심키워드")
    keyword_cols = st.columns(3)
    for i, keyword in enumerate(result["keywords"][:3]):
        with keyword_cols[i]:
            st.info(keyword)

    st.markdown("### 📖 영어 원문 보기")
    with st.expander("원문 펼쳐보기", expanded=True):
        st.caption("입력하거나 사진에서 추출한 영어 원문입니다.")
        st.text(result["original_text"])

    st.divider()
    if st.button("📌 시험범위에 저장", use_container_width=True):
        if save_to_exam_scope(st.session_state.current_passage, result):
            st.success("시험범위에 저장했습니다!")
        else:
            st.warning("이미 저장된 지문입니다.")

st.divider()
st.subheader(f"📚 내 시험범위 ({len(st.session_state.exam_scope)}개)")

if not st.session_state.exam_scope:
    st.info("아직 저장된 지문이 없습니다.")
else:
    st.caption("저장한 지문을 다시 펼쳐서 제목, 주제문장, 논리 흐름, 어휘·문법, 원문을 확인할 수 있어요.")
    for i, item in enumerate(st.session_state.exam_scope):
        saved = item["result"]
        title = saved.get("korean_title", "저장된 지문")
        with st.expander(f"{i + 1}. {title}"):
            st.markdown(f"**English Title:** {saved.get('english_title', '')}")
            st.markdown("**📌 핵심 주제문장**")
            st.write(saved.get("key_sentence", ""))
            st.markdown("**🧭 논리 흐름**")
            saved_flow = saved.get("logical_flow", {})
            st.write("① 처음: " + saved_flow.get("beginning", ""))
            st.write("② 중간: " + saved_flow.get("middle", ""))
            if saved_flow.get("examples"):
                for example in saved_flow["examples"]:
                    st.write("예시: " + example)
            st.write("③ 끝: " + saved_flow.get("end", ""))

            st.markdown("**🔤 중요 단어**")
            for word in saved.get("vocabulary", []):
                st.write(f"• {word}")

            st.markdown("**📐 중요 문법**")
            for grammar in saved.get("grammar", []):
                st.write(f"• {grammar}")

            with st.expander("📖 영어 원문 보기"):
                st.text(saved.get("original_text", item.get("passage", "")))

            if st.button("🗑️ 삭제", key=f"delete_{i}"):
                st.session_state.exam_scope.pop(i)
                save_exam_scope_to_browser()
                st.rerun()
