import base64
import json
import requests
import streamlit as st

st.set_page_config(
    page_title="지문.zip",
    page_icon="📚",
    layout="wide"
)

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "current_passage" not in st.session_state:
    st.session_state.current_passage = ""

if "exam_scope" not in st.session_state:
    st.session_state.exam_scope = []


def get_api_key():
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def extract_response_text(response_json):
    if isinstance(response_json.get("output_text"), str):
        return response_json["output_text"]

    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")

    return ""


def analyze_passage(passage="", image_bytes=None, image_type="image/png"):
    api_key = get_api_key()

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            "Streamlit의 Secrets에 OPENAI_API_KEY를 추가해주세요."
        )

    schema = {
        "type": "object",
        "properties": {
            "korean_title": {"type": "string"},
            "english_title": {"type": "string"},
            "summary": {"type": "string"},
            "vocabulary_grammar": {"type": "string"},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 3
            },
            "extracted_passage": {"type": "string"}
        },
        "required": [
            "korean_title",
            "english_title",
            "summary",
            "vocabulary_grammar",
            "keywords",
            "extracted_passage"
        ],
        "additionalProperties": False
    }

    instruction = """
너는 영어 내신 지문을 시험 직전에 빠르게 복습할 수 있도록 정리하는 학습 보조 AI다.

다음 규칙을 반드시 지켜라.
1. 지문의 내용에서 벗어나지 말 것.
2. 한글 제목은 지문의 핵심 내용을 정확히 드러내는 자연스러운 제목으로 작성할 것.
3. 영어 제목은 짧고 자연스러운 영어 제목으로 작성할 것.
4. 내용 요약은 핵심 주장과 흐름이 드러나도록 3~5문장으로 작성할 것.
5. 단어·문법은 내신 대비에 도움이 되는 중요한 어휘와 문법 표현을 '표현 - 뜻/설명' 형식으로 정리할 것.
6. 핵심키워드는 지문의 흐름을 기억하기 쉬운 3개의 핵심어로 작성할 것.
7. 이미지가 입력되면 이미지 속 영어 지문을 먼저 정확하게 읽고 분석할 것.
8. extracted_passage에는 AI가 읽은 영어 지문을 가능한 한 원문 그대로 작성할 것.
"""

    content = [{"type": "input_text", "text": instruction}]

    if passage.strip():
        content.append(
            {
                "type": "input_text",
                "text": "분석할 영어 지문:\n\n" + passage.strip()
            }
        )

    if image_bytes:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{image_type};base64,{encoded}"
        content.append(
            {
                "type": "input_image",
                "image_url": data_url,
                "detail": "high"
            }
        )

    payload = {
        "model": "gpt-5.6-luna",
        "store": False,
        "input": [
            {
                "role": "user",
                "content": content
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "passage_analysis",
                "strict": True,
                "schema": schema
            }
        }
    }

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"AI 요청에 실패했습니다: {detail}")

    text = extract_response_text(response.json())

    if not text:
        raise RuntimeError("AI의 분석 결과를 읽지 못했습니다.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI 결과 형식을 읽는 중 오류가 발생했습니다.") from exc


st.markdown(
    """
    <div style="margin-bottom: 0.2rem;">
        <div style="font-size: 2.1rem; font-weight: 800;">지문.zip</div>
        <div style="font-size: 1.05rem; color: #666;">영어 내신 지문을 한눈에 정리하다.</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()

st.subheader("📝 영어 지문")

input_method = st.radio(
    "입력 방법",
    ["텍스트 붙여넣기", "지문 사진 업로드"],
    horizontal=True
)

passage = ""
uploaded_image = None

if input_method == "텍스트 붙여넣기":
    passage = st.text_area(
        "분석할 영어 지문을 입력하세요.",
        height=250,
        placeholder="영어 지문을 여기에 붙여넣어 주세요."
    )
else:
    uploaded_image = st.file_uploader(
        "지문 사진을 올려주세요.",
        type=["png", "jpg", "jpeg", "webp"],
        help="교과서나 문제집의 영어 지문 사진을 업로드하면 AI가 글자를 읽고 분석합니다."
    )

    if uploaded_image:
        st.image(uploaded_image, caption="업로드한 지문", use_container_width=True)

analyze_button = st.button(
    "✨ 지문 분석하기",
    use_container_width=True,
    type="primary"
)

if analyze_button:
    has_text = bool(passage.strip())
    has_image = uploaded_image is not None

    if not has_text and not has_image:
        st.warning("영어 지문을 입력하거나 지문 사진을 업로드해주세요.")
    else:
        try:
            with st.spinner("지문을 읽고 분석하는 중..."):
                image_bytes = uploaded_image.getvalue() if uploaded_image else None
                image_type = uploaded_image.type if uploaded_image else "image/png"

                result = analyze_passage(
                    passage=passage,
                    image_bytes=image_bytes,
                    image_type=image_type
                )

            st.session_state.analysis_result = result
            st.session_state.current_passage = (
                result.get("extracted_passage", "").strip()
                or passage.strip()
            )
            st.success("지문 분석이 완료되었습니다!")

        except Exception as e:
            st.error(str(e))

result = st.session_state.analysis_result

if result:
    st.divider()
    st.subheader("📖 분석 결과")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🇰🇷 한글 제목")
        st.info(result["korean_title"])

    with col2:
        st.markdown("### 🇺🇸 English Title")
        st.info(result["english_title"])

    st.markdown("### 📌 내용 요약")
    st.info(result["summary"])

    st.markdown("### 🔤 단어 · 문법")
    st.info(result["vocabulary_grammar"])

    st.markdown("### 🔑 3단 핵심키워드")
    keyword_text = "  →  ".join(
        f"**{keyword}**" for keyword in result["keywords"]
    )
    st.markdown(keyword_text)

    with st.expander("📄 AI가 읽은 원문 확인"):
        st.write(st.session_state.current_passage)

    st.divider()

    st.subheader("📚 시험범위")

    if st.button("➕ 내 시험범위에 저장", use_container_width=True):
        saved_item = {
            "title": result["korean_title"],
            "english_title": result["english_title"],
            "passage": st.session_state.current_passage,
            "summary": result["summary"],
            "keywords": result["keywords"]
        }

        if not any(
            item["passage"] == saved_item["passage"]
            for item in st.session_state.exam_scope
        ):
            st.session_state.exam_scope.append(saved_item)
            st.success("내 시험범위에 저장했습니다.")
        else:
            st.info("이미 저장된 지문입니다.")

if st.session_state.exam_scope:
    st.divider()
    st.subheader("📚 내 시험범위")

    for index, item in enumerate(st.session_state.exam_scope):
        with st.expander(f"{index + 1}. {item['title']}"):
            st.markdown(f"**{item['english_title']}**")
            st.write(item["summary"])
            st.caption(" · ".join(item["keywords"]))

    if st.button("🗑️ 시험범위 전체 비우기"):
        st.session_state.exam_scope = []
        st.rerun()
