import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import json
import time
import html
import re

st.set_page_config(page_title="지문.zip", page_icon="📚", layout="wide")

try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=gemini_api_key)
except Exception:
    client = None

if "exam_scope" not in st.session_state:
    st.session_state.exam_scope = []
if "current_passage" not in st.session_state:
    st.session_state.current_passage = ""
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "original_text": {"type": "string", "description": "입력되거나 사진에서 읽은 영어 지문의 원문"},
        "korean_title": {"type": "string", "description": "지문의 핵심 주제를 보여주는 한국어 제목"},
        "english_title": {"type": "string", "description": "지문의 핵심 주제를 보여주는 영어 제목"},
        "logical_flow": {
            "type": "object",
            "properties": {
                "beginning": {"type": "string", "description": "처음 부분의 주제·문제·상황 제시"},
                "middle": {"type": "string", "description": "중간 부분의 핵심 주장·설명·근거 전개"},
                "end": {"type": "string", "description": "끝부분의 결론·핵심 메시지"},
                "examples": {"type": "array", "items": {"type": "string"}, "description": "지문에 실제로 등장하는 예시. 없으면 빈 배열"}
            },
            "required": ["beginning", "middle", "end", "examples"]
        },
        "key_sentence": {"type": "string", "description": "지문의 주제를 가장 잘 보여주는 문장 1개. 반드시 원문에 실제로 존재하는 문장을 그대로 반환"},
        "vocabulary": {"type": "array", "items": {"type": "string"}, "description": "내신에 중요한 영어 단어와 한국어 뜻 5개"},
        "grammar": {"type": "array", "items": {"type": "string"}, "description": "지문에서 중요한 문법 또는 표현 3개와 간단한 설명"},
        "keywords": {"type": "array", "items": {"type": "string"}, "description": "지문 전체 내용을 기억하기 위한 핵심 키워드 3개"}
    },
    "required": ["original_text", "korean_title", "english_title", "logical_flow", "key_sentence", "vocabulary", "grammar", "keywords"]
}

SYSTEM_PROMPT = """
너는 영어 내신 지문을 분석하는 학습 보조 AI이다.

이 서비스의 목적은 지문을 단순히 짧게 요약하는 것이 아니라, 학생이 시험 직전에 지문의 주제와 논리적 흐름을 빠르게 떠올릴 수 있도록 분석지를 만드는 것이다.

반드시 다음 원칙을 지킨다.
1. 지문에 없는 내용을 임의로 추가하지 않는다.
2. 원문의 의미를 왜곡하지 않는다.
3. 지문의 전개를 '처음 → 중간 → 끝'의 흐름으로 파악한다.
4. 처음에는 주제·문제·상황이 어떻게 제시되는지 설명한다.
5. 중간에는 핵심 주장, 설명, 근거가 어떤 관계로 이어지는지 설명한다.
6. 끝에는 앞의 내용이 어떤 결론이나 핵심 메시지로 이어지는지 설명한다.
7. 지문에 실제 예시가 있는 경우 examples에 넣고, 그 예시가 무엇을 설명하거나 뒷받침하는지도 논리 흐름에 반영한다.
8. 지문에 예시가 없으면 examples는 빈 배열로 둔다. 예시를 새로 만들어내지 않는다.
9. key_sentence는 AI가 새로 만든 문장이 아니라 반드시 원문에 실제로 존재하는 문장 그대로 반환한다.
10. 여러 문장이 핵심이면 주제를 가장 직접적으로 드러내는 원문 문장 1개를 선택한다.
11. 영어 단어는 지문에 실제로 등장하거나 지문 이해에 직접적으로 중요한 단어를 선정한다.
12. 문법은 지문에 실제로 나타난 문법이나 표현을 선정한다.
13. 사진으로 입력된 경우 사진 속 영어 문장을 최대한 정확하게 그대로 옮긴다.
14. 논리 흐름은 문장별 번역이 아니라 '왜 다음 내용이 나오는지'가 보이도록 작성한다.
15. 불필요하게 길게 쓰지 말고 시험 직전 복습에 적합한 정도로 압축한다.

결과 항목:
original_text: 입력된 영어 지문 원문
korean_title: 핵심 주제를 보여주는 자연스러운 한국어 제목
english_title: 핵심 주제를 보여주는 자연스러운 영어 제목
logical_flow: 처음·중간·끝의 논리적 전개와 실제 예시
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
                return None, "AI 분석 중 오류가 발생했습니다.\n\n" + error_message
    return None, "현재 Gemini AI 서버가 혼잡해서 분석을 완료하지 못했어요.\n\n잠시 후 다시 '지문 분석하기'를 눌러주세요."

def analyze_with_ai(passage=None, image=None):
    if client is None:
        return None, "Gemini API 키가 설정되지 않았습니다."
    if passage is not None:
        prompt = SYSTEM_PROMPT + "\n\n다음 영어 지문을 분석해줘.\n\n" + passage
        response, error = generate_with_gemini(prompt)
    elif image is not None:
        prompt = SYSTEM_PROMPT + "\n\n첨부된 사진 속 영어 지문을 읽고 분석해줘."
        response, error = generate_with_gemini([prompt, image])
    else:
        return None, "분석할 지문이 없습니다."
    if error:
        return None, error
    try:
        result = json.loads(response.text)
    except Exception:
        return None, "AI의 분석 결과를 읽는 중 오류가 발생했습니다."
    for key in ["original_text", "korean_title", "english_title", "logical_flow", "key_sentence", "vocabulary", "grammar", "keywords"]:
        if key not in result:
            return None, f"AI 분석 결과에 '{key}' 항목이 없습니다."
    return result, None

def make_highlighted_text(original_text, key_sentence):
    if not original_text:
        return ""
    escaped_text = html.escape(original_text)
    escaped_key = html.escape(key_sentence.strip()) if key_sentence else ""
    if escaped_key and escaped_key in escaped_text:
        highlighted = escaped_text.replace(escaped_key, f'<mark style="background-color:#fff176; padding:2px 4px; border-radius:4px;">{escaped_key}</mark>', 1)
    else:
        normalized_key = re.sub(r"\s+", " ", key_sentence.strip()) if key_sentence else ""
        normalized_text = re.sub(r"\s+", " ", original_text)
        if normalized_key and normalized_key in normalized_text:
            pattern = re.escape(normalized_key).replace(r"\ ", r"\s+")
            match = re.search(pattern, original_text, flags=re.DOTALL)
            if match:
                start, end = match.span()
                highlighted = (
                    html.escape(original_text[:start])
                    + f'<mark style="background-color:#fff176; padding:2px 4px; border-radius:4px;">{html.escape(original_text[start:end])}</mark>'
                    + html.escape(original_text[end:])
                )
            else:
                highlighted = escaped_text
        else:
            highlighted = escaped_text
    return '<div style="white-space:pre-wrap; line-height:1.8; font-size:16px;">' + highlighted + '</div>'

def save_to_exam_scope(passage, result):
    if not passage.strip():
        return False
    for item in st.session_state.exam_scope:
        if item["passage"] == passage:
            return False
    st.session_state.exam_scope.append({"passage": passage, "result": result})
    return True

st.title("📚 지문.zip")
st.caption("영어 내신 지문을 한눈에 정리하다.")
st.divider()

st.subheader("📝 영어 지문")
input_method = st.radio("지문 입력 방법", ["직접 입력", "사진 업로드"], horizontal=True)
passage = ""
uploaded_image = None

if input_method == "직접 입력":
    passage = st.text_area("분석할 영어 지문을 입력하세요.", height=260, placeholder="영어 지문을 여기에 붙여넣어 주세요.")
else:
    uploaded_image = st.file_uploader("영어 지문 사진을 업로드하세요.", type=["png", "jpg", "jpeg"], help="영어 지문이 잘 보이도록 사진을 업로드하세요.")
    if uploaded_image is not None:
        st.image(uploaded_image, caption="업로드한 지문", use_container_width=True)
        st.info("사진 속 영어 지문을 AI가 직접 읽고 분석합니다.")

if st.button("✨ 지문 분석하기", use_container_width=True, type="primary"):
    if input_method == "직접 입력":
        if not passage.strip():
            st.warning("먼저 영어 지문을 입력해주세요.")
        elif len(passage.strip()) < 10:
            st.warning("지문이 너무 짧습니다. 영어 지문을 조금 더 입력해주세요.")
        else:
            with st.spinner("🤖 AI가 지문의 주제와 논리 흐름을 분석하고 있어요..."):
                result, error = analyze_with_ai(passage=passage.strip())
            if error:
                st.error(error)
            else:
                st.session_state.current_passage = result["original_text"]
                st.session_state.analysis_result = result
                st.success("✨ 지문 분석이 완료되었습니다!")
    else:
        if uploaded_image is None:
            st.warning("먼저 영어 지문 사진을 업로드해주세요.")
        else:
            try:
                image = Image.open(BytesIO(uploaded_image.getvalue()))
                with st.spinner("🤖 AI가 사진 속 지문의 주제와 논리 흐름을 분석하고 있어요..."):
                    result, error = analyze_with_ai(image=image)
                if error:
                    st.error(error)
                else:
                    st.session_state.current_passage = result["original_text"]
                    st.session_state.analysis_result = result
                    st.success("✨ 사진 속 지문 분석이 완료되었습니다!")
            except Exception as e:
                st.error("사진을 처리하는 중 오류가 발생했습니다: " + str(e))

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
    with st.expander("원문 펼쳐보기"):
        st.caption("🟨 형광펜 표시 = 핵심 주제문장")
        st.markdown(make_highlighted_text(result["original_text"], result["key_sentence"]), unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📚 시험범위")
    if st.button("➕ 현재 지문을 시험범위에 저장", use_container_width=True):
        saved = save_to_exam_scope(st.session_state.current_passage, result)
        if saved:
            st.success("시험범위에 저장했습니다!")
        else:
            st.warning("이미 시험범위에 저장된 지문입니다.")

st.divider()
st.subheader("📚 저장된 시험범위")
if not st.session_state.exam_scope:
    st.caption("아직 저장된 지문이 없습니다.")
else:
    for i, item in enumerate(st.session_state.exam_scope):
        saved_result = item["result"]
        with st.expander(f"{i + 1}. {saved_result['korean_title']}"):
            st.write(saved_result["english_title"])
            st.write(saved_result["key_sentence"])
            if st.button("🗑️ 삭제", key=f"delete_{i}"):
                st.session_state.exam_scope.pop(i)
                st.rerun()
