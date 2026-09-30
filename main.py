import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import json
import time


# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="지문.zip",
    page_icon="📚",
    layout="wide"
)


# -----------------------------
# Gemini 설정
# -----------------------------
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]

    client = genai.Client(
        api_key=gemini_api_key
    )

except Exception:
    client = None


# -----------------------------
# 세션 상태 초기화
# -----------------------------
if "exam_scope" not in st.session_state:
    st.session_state.exam_scope = []

if "current_passage" not in st.session_state:
    st.session_state.current_passage = ""

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None


# -----------------------------
# AI가 반환할 결과 형식
# -----------------------------
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "original_text": {
            "type": "string",
            "description": "사진이나 입력된 영어 지문의 원문"
        },
        "korean_title": {
            "type": "string",
            "description": "지문의 핵심 내용을 보여주는 자연스러운 한국어 제목"
        },
        "english_title": {
            "type": "string",
            "description": "지문의 핵심 내용을 보여주는 자연스러운 영어 제목"
        },
        "summary": {
            "type": "string",
            "description": "시험 직전에 읽고 지문 내용을 떠올릴 수 있는 한국어 요약"
        },
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "내신에 중요한 영어 단어와 한국어 뜻 5개"
        },
        "grammar": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "지문에서 중요한 문법 또는 표현 3개와 간단한 설명"
        },
        "keywords": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "지문 내용을 기억하기 위한 핵심 키워드 3개"
        }
    },
    "required": [
        "original_text",
        "korean_title",
        "english_title",
        "summary",
        "vocabulary",
        "grammar",
        "keywords"
    ]
}


# -----------------------------
# AI 분석 프롬프트
# -----------------------------
SYSTEM_PROMPT = """
너는 영어 내신 지문을 분석하는 학습 보조 AI이다.

사용자가 제공한 영어 지문을 정확하게 읽고 분석한다.

다음 원칙을 반드시 지킨다.

1. 지문에 없는 내용을 임의로 추가하지 않는다.
2. 원문의 의미를 왜곡하지 않는다.
3. 시험 직전에 빠르게 복습할 수 있도록 핵심 내용을 중심으로 정리한다.
4. 영어 단어는 지문에 실제로 등장하거나 지문 이해에 직접적으로 중요한 단어를 선정한다.
5. 문법은 지문에 실제로 나타난 문법이나 표현을 선정한다.
6. 사진으로 입력된 경우 사진 속 영어 문장을 최대한 정확하게 그대로 옮긴다.

결과 항목:

original_text
- 입력된 영어 지문 원문
- 사진이라면 사진에서 읽은 영어 지문

korean_title
- 핵심 내용을 보여주는 자연스러운 한국어 제목

english_title
- 핵심 내용을 보여주는 자연스러운 영어 제목

summary
- 학생이 시험 직전에 읽고 내용을 떠올릴 수 있도록 한국어로 핵심 내용을 정리

vocabulary
- 중요한 영어 단어 5개
- 반드시 "영어 단어 - 한국어 뜻" 형식

grammar
- 중요한 문법 또는 표현 3개
- 왜 중요한지 짧게 설명

keywords
- 전체 내용을 기억하는 데 도움이 되는 핵심 키워드 3개
"""


# -----------------------------
# Gemini 호출 함수
# -----------------------------
def generate_with_gemini(contents):
    """
    1차: Gemini 3.8 Flash
    2차: Gemini 3.7 Flash
    일시적인 503 오류가 발생하면 다음 모델로 전환
    """

    if client is None:
        return None, "Gemini API 키가 설정되지 않았습니다."

    models = [
        "gemini-3.8-flash",
        "gemini-3.7-flash"
    ]

    last_error = ""

    for model in models:

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

                last_error = "AI가 분석 결과를 반환하지 않았습니다."

            except Exception as e:

                error_message = str(e)
                last_error = error_message

                # 503: 서버가 일시적으로 처리할 수 없는 경우
                if "503" in error_message or "UNAVAILABLE" in error_message:

                    # 첫 번째 모델에서 잠시 기다린 후 재시도
                    if attempt == 0:
                        time.sleep(2)
                        continue

                    # 두 번째 모델로 넘어감
                    break

                # 429: 무료 사용량/요청 제한
                if (
                    "429" in error_message
                    or "quota" in error_message.lower()
                    or "resource exhausted" in error_message.lower()
                ):
                    return None, (
                        "Gemini 무료 사용량 또는 요청 한도에 도달했어요. "
                        "잠시 후 다시 시도해주세요."
                    )

                # API 키나 요청 형식 등의 오류
                return None, (
                    "AI 분석 중 오류가 발생했습니다.\n\n"
                    + error_message
                )

    return None, (
        "현재 Gemini AI 서버가 혼잡해서 분석을 완료하지 못했어요.\n\n"
        "잠시 후 다시 '지문 분석하기'를 눌러주세요."
    )


# -----------------------------
# AI 분석 함수
# -----------------------------
def analyze_with_ai(
    passage=None,
    image=None
):

    if client is None:
        return None, "Gemini API 키가 설정되지 않았습니다."

    if passage is not None:

        prompt = (
            SYSTEM_PROMPT
            + "\n\n"
            + "다음 영어 지문을 분석해줘.\n\n"
            + passage
        )

        response, error = generate_with_gemini(prompt)

    elif image is not None:

        prompt = (
            SYSTEM_PROMPT
            + "\n\n"
            + "첨부된 사진 속 영어 지문을 읽고 분석해줘."
        )

        response, error = generate_with_gemini(
            [
                prompt,
                image
            ]
        )

    else:

        return None, "분석할 지문이 없습니다."

    if error:
        return None, error

    try:

        result = json.loads(response.text)

    except Exception:
        return None, "AI의 분석 결과를 읽는 중 오류가 발생했습니다."

    required_keys = [
        "original_text",
        "korean_title",
        "english_title",
        "summary",
        "vocabulary",
        "grammar",
        "keywords"
    ]

    for key in required_keys:

        if key not in result:
            return None, (
                f"AI 분석 결과에 '{key}' 항목이 없습니다."
            )

    return result, None


# -----------------------------
# 시험범위 저장
# -----------------------------
def save_to_exam_scope(
    passage,
    result
):

    if not passage.strip():
        return False

    for item in st.session_state.exam_scope:

        if item["passage"] == passage:
            return False

    st.session_state.exam_scope.append(
        {
            "passage": passage,
            "result": result
        }
    )

    return True


# -----------------------------
# 제목
# -----------------------------
st.title("📚 지문.zip")

st.caption(
    "영어 내신 지문을 한눈에 정리하다."
)

st.divider()


# -----------------------------
# 지문 입력 영역
# -----------------------------
st.subheader("📝 영어 지문")

input_method = st.radio(
    "지문 입력 방법",
    [
        "직접 입력",
        "사진 업로드"
    ],
    horizontal=True
)

passage = ""
uploaded_image = None


# -----------------------------
# 직접 입력
# -----------------------------
if input_method == "직접 입력":

    passage = st.text_area(
        "분석할 영어 지문을 입력하세요.",
        height=260,
        placeholder=(
            "영어 지문을 여기에 붙여넣어 주세요."
        )
    )


# -----------------------------
# 사진 업로드
# -----------------------------
else:

    uploaded_image = st.file_uploader(
        "영어 지문 사진을 업로드하세요.",
        type=[
            "png",
            "jpg",
            "jpeg"
        ],
        help="영어 지문이 잘 보이도록 사진을 업로드하세요."
    )

    if uploaded_image is not None:

        st.image(
            uploaded_image,
            caption="업로드한 지문",
            use_container_width=True
        )

        st.info(
            "사진 속 영어 지문을 AI가 직접 읽고 분석합니다."
        )


# -----------------------------
# 분석 버튼
# -----------------------------
if st.button(
    "✨ 지문 분석하기",
    use_container_width=True,
    type="primary"
):

    # =========================
    # 직접 입력
    # =========================

    if input_method == "직접 입력":

        if not passage.strip():

            st.warning(
                "먼저 영어 지문을 입력해주세요."
            )

        elif len(passage.strip()) < 10:

            st.warning(
                "지문이 너무 짧습니다. "
                "영어 지문을 조금 더 입력해주세요."
            )

        else:

            with st.spinner(
                "🤖 AI가 지문을 분석하고 있어요..."
            ):

                result, error = analyze_with_ai(
                    passage=passage.strip()
                )

            if error:

                st.error(error)

            else:

                st.session_state.current_passage = (
                    result["original_text"]
                )

                st.session_state.analysis_result = (
                    result
                )

                st.success(
                    "✨ 지문 분석이 완료되었습니다!"
                )


    # =========================
    # 사진 입력
    # =========================

    else:

        if uploaded_image is None:

            st.warning(
                "먼저 영어 지문 사진을 업로드해주세요."
            )

        else:

            try:

                image_bytes = (
                    uploaded_image.getvalue()
                )

                image = Image.open(
                    BytesIO(image_bytes)
                )

                with st.spinner(
                    "🤖 AI가 사진 속 지문을 읽고 분석하고 있어요..."
                ):

                    result, error = analyze_with_ai(
                        image=image
                    )

                if error:

                    st.error(error)

                else:

                    st.session_state.current_passage = (
                        result["original_text"]
                    )

                    st.session_state.analysis_result = (
                        result
                    )

                    st.success(
                        "✨ 사진 속 지문 분석이 완료되었습니다!"
                    )

            except Exception as e:

                st.error(
                    "사진을 처리하는 중 오류가 발생했습니다: "
                    + str(e)
                )


# -----------------------------
# 분석 결과
# -----------------------------
if st.session_state.analysis_result is not None:

    result = st.session_state.analysis_result

    st.divider()

    st.subheader("📖 분석 결과")


    # -------------------------
    # 한글 / 영어 제목
    # -------------------------
    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "### 🇰🇷 한글 제목"
        )

        st.info(
            result["korean_title"]
        )

    with col2:

        st.markdown(
            "### 🇺🇸 English Title"
        )

        st.info(
            result["english_title"]
        )


    # -------------------------
    # 내용 요약
    # -------------------------
    st.markdown(
        "### 📌 내용 요약"
    )

    st.write(
        result["summary"]
    )


    # -------------------------
    # 중요 단어
    # -------------------------
    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "### 🔤 중요 단어"
        )

        for word in result["vocabulary"]:

            st.write(
                f"• {word}"
            )


    # -------------------------
    # 중요 문법
    # -------------------------
    with col2:

        st.markdown(
            "### 📐 중요 문법"
        )

        for grammar in result["grammar"]:

            st.write(
                f"• {grammar}"
            )


    # -------------------------
    # 핵심 키워드
    # -------------------------
    st.markdown(
        "### 🔑 3단 핵심키워드"
    )

    keyword_cols = st.columns(3)

    for i, keyword in enumerate(
        result["keywords"][:3]
    ):

        with keyword_cols[i]:

            st.info(
                keyword
            )


    # -------------------------
    # 원문
    # -------------------------
    with st.expander(
        "📄 읽어낸 영어 원문 보기"
    ):

        st.write(
            result["original_text"]
        )


    # -------------------------
    # 시험범위 저장
    # -------------------------
    st.divider()

    st.subheader(
        "📚 시험범위"
    )

    if st.button(
        "➕ 내 시험범위에 저장",
        use_container_width=True
    ):

        saved = save_to_exam_scope(
            st.session_state.current_passage,
            result
        )

        if saved:

            st.success(
                "시험범위에 저장되었습니다!"
            )

        else:

            st.warning(
                "이미 저장된 지문입니다."
            )


# -----------------------------
# 저장된 시험범위
# -----------------------------
st.divider()

st.subheader(
    "📚 내 시험범위"
)

if len(st.session_state.exam_scope) == 0:

    st.caption(
        "아직 저장된 지문이 없습니다."
    )

else:

    for index, item in enumerate(
        st.session_state.exam_scope
    ):

        with st.expander(
            f"지문 {index + 1}"
        ):

            saved_result = item["result"]

            st.markdown(
                "### 🇰🇷 한글 제목"
            )

            st.write(
                saved_result["korean_title"]
            )

            st.markdown(
                "### 🇺🇸 English Title"
            )

            st.write(
                saved_result["english_title"]
            )

            st.markdown(
                "### 📌 내용 요약"
            )

            st.write(
                saved_result["summary"]
            )

            st.markdown(
                "### 🔤 중요 단어"
            )

            for word in saved_result["vocabulary"]:

                st.write(
                    f"• {word}"
                )

            st.markdown(
                "### 📐 중요 문법"
            )

            for grammar in saved_result["grammar"]:

                st.write(
                    f"• {grammar}"
                )

            st.markdown(
                "### 🔑 핵심키워드"
            )

            st.write(
                " · ".join(
                    saved_result["keywords"]
                )
            )

            st.markdown(
                "### 📄 원문"
            )

            st.write(
                item["passage"]
            )

            if st.button(
                "🗑️ 이 지문 삭제",
                key=f"delete_{index}"
            ):

                st.session_state.exam_scope.pop(
                    index
                )

                st.rerun()
