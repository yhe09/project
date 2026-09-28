import streamlit as st


# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="지문.zip",
    page_icon="📚",
    layout="wide"
)


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
# 지문 분석 결과 생성
# 현재는 AI 없이 임시 결과를 보여주는 단계
# -----------------------------
def analyze_passage(passage):
    words = passage.split()

    if len(words) < 3:
        return None

    return {
        "korean_title": "지문의 핵심 내용을 정리한 제목",
        "english_title": "A Summary of the Passage",
        "summary": (
            "현재는 AI API가 연결되지 않은 상태입니다. "
            "입력한 지문을 바탕으로 앞으로 AI가 제목과 내용을 분석하도록 구현할 예정입니다."
        ),
        "vocabulary": [
            "중요 단어 1",
            "중요 단어 2",
            "중요 단어 3"
        ],
        "grammar": [
            "중요 문법 표현 1",
            "중요 문법 표현 2"
        ],
        "keywords": [
            "핵심어 1",
            "핵심어 2",
            "핵심어 3"
        ]
    }


# -----------------------------
# 시험범위 저장
# -----------------------------
def save_to_exam_scope(passage, result):
    if not passage.strip():
        return False

    # 같은 지문이 이미 저장되어 있는지 확인
    for item in st.session_state.exam_scope:
        if item["passage"] == passage:
            return False

    st.session_state.exam_scope.append({
        "passage": passage,
        "result": result
    })

    return True


# -----------------------------
# 제목
# -----------------------------
st.title("📚 지문.zip")
st.caption("영어 내신 지문을 한눈에 정리하다.")

st.divider()


# -----------------------------
# 입력 영역
# -----------------------------
st.subheader("📝 영어 지문")

input_method = st.radio(
    "지문 입력 방법",
    ["직접 입력", "사진 업로드"],
    horizontal=True
)


passage = ""


# 직접 입력
if input_method == "직접 입력":

    passage = st.text_area(
        "분석할 영어 지문을 입력하세요.",
        height=260,
        placeholder=(
            "영어 지문을 여기에 붙여넣어 주세요.\n\n"
            "예시:\n"
            "Learning from mistakes is an important part of..."
        )
    )


# 사진 업로드
else:

    uploaded_image = st.file_uploader(
        "영어 지문 사진을 업로드하세요.",
        type=["png", "jpg", "jpeg"],
        help="현재 버전에서는 사진을 업로드하고 확인할 수 있습니다. OCR/AI 분석은 추후 추가됩니다."
    )

    if uploaded_image is not None:

        st.image(
            uploaded_image,
            caption="업로드한 지문",
            use_container_width=True
        )

        st.info(
            "사진 업로드 기능은 구현되어 있습니다. "
            "사진 속 영어 지문을 자동으로 읽는 기능은 AI/OCR 연결 단계에서 추가됩니다."
        )

        passage = st.text_area(
            "사진 속 지문을 아래에 입력해주세요.",
            height=200,
            placeholder="사진 속 영어 지문을 직접 입력하세요."
        )


# -----------------------------
# 분석 버튼
# -----------------------------
if st.button(
    "✨ 지문 분석하기",
    use_container_width=True,
    type="primary"
):

    if not passage.strip():

        st.warning("먼저 영어 지문을 입력해주세요.")

    else:

        result = analyze_passage(passage)

        if result is None:

            st.warning(
                "지문이 너무 짧습니다. 영어 지문을 조금 더 입력해주세요."
            )

        else:

            st.session_state.current_passage = passage
            st.session_state.analysis_result = result

            st.success("지문이 입력되었습니다.")


# -----------------------------
# 분석 결과
# -----------------------------
if st.session_state.analysis_result is not None:

    result = st.session_state.analysis_result

    st.divider()

    st.subheader("📖 분석 결과")

    # 제목
    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### 🇰🇷 한글 제목")

        st.info(result["korean_title"])

    with col2:

        st.markdown("### 🇺🇸 English Title")

        st.info(result["english_title"])


    # 요약
    st.markdown("### 📌 내용 요약")

    st.write(result["summary"])


    # 단어 / 문법
    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### 🔤 중요 단어")

        for word in result["vocabulary"]:
            st.write(f"• {word}")


    with col2:

        st.markdown("### 📐 중요 문법")

        for grammar in result["grammar"]:
            st.write(f"• {grammar}")


    # 핵심 키워드
    st.markdown("### 🔑 3단 핵심키워드")

    keyword_cols = st.columns(3)

    for i, keyword in enumerate(result["keywords"]):

        with keyword_cols[i]:
            st.info(keyword)


    # 시험범위 저장
    st.divider()

    st.subheader("📚 시험범위")

    if st.button(
        "➕ 내 시험범위에 저장",
        use_container_width=True
    ):

        saved = save_to_exam_scope(
            st.session_state.current_passage,
            result
        )

        if saved:
            st.success("시험범위에 저장되었습니다!")

        else:
            st.warning("이미 저장된 지문입니다.")


# -----------------------------
# 저장된 시험범위
# -----------------------------
st.divider()

st.subheader("📚 내 시험범위")

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

            st.markdown("### 🇰🇷 한글 제목")

            st.write(
                saved_result["korean_title"]
            )

            st.markdown("### 🇺🇸 English Title")

            st.write(
                saved_result["english_title"]
            )

            st.markdown("### 📌 내용 요약")

            st.write(
                saved_result["summary"]
            )

            st.markdown("### 🔑 핵심키워드")

            st.write(
                " · ".join(
                    saved_result["keywords"]
                )
            )

            st.markdown("### 📄 원문")

            st.write(
                item["passage"]
            )

            if st.button(
                "🗑️ 이 지문 삭제",
                key=f"delete_{index}"
            ):

                st.session_state.exam_scope.pop(index)

                st.rerun()
