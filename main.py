import streamlit as st
from openai import OpenAI
import json


# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="지문.zip",
    page_icon="📚",
    layout="wide"
)


# -----------------------------
# OpenAI 설정
# -----------------------------
try:
    client = OpenAI(
        api_key=st.secrets["OPENAI_API_KEY"]
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
# AI 분석 함수
# -----------------------------
def analyze_with_ai(passage=None, image_data=None):

    if client is None:
        return None, "OpenAI API 키가 설정되지 않았습니다."

    system_prompt = """
너는 영어 내신 지문을 분석하는 학습 보조 AI이다.

사용자가 제공한 영어 지문을 바탕으로 다음 항목을 정확하게 분석한다.

1. korean_title
   - 지문의 핵심 내용을 잘 보여주는 자연스러운 한국어 제목
   - 너무 길지 않게 작성

2. english_title
   - 지문의 핵심 내용을 보여주는 자연스러운 영어 제목

3. summary
   - 학생이 시험 직전에 읽고 내용을 떠올릴 수 있도록 핵심 내용을 한국어로 정리
   - 지나치게 길게 쓰지 말 것

4. vocabulary
   - 내신 공부에 중요할 만한 영어 단어 5개
   - 반드시 "영어 단어 - 한국어 뜻" 형식

5. grammar
   - 지문에서 주목할 만한 문법 또는 표현 3개
   - 해당 표현이 왜 중요한지 짧게 설명

6. keywords
   - 지문 전체 내용을 기억하는 데 도움이 되는 핵심 키워드 3개
   - 짧은 단어나 구로 작성

반드시 아래 JSON 형식으로만 답한다.
마크다운 코드블록이나 추가 설명을 사용하지 않는다.

{
    "korean_title": "...",
    "english_title": "...",
    "summary": "...",
    "vocabulary": ["...", "...", "...", "...", "..."],
    "grammar": ["...", "...", "..."],
    "keywords": ["...", "...", "..."]
}
"""

    user_prompt = """
이 영어 지문을 분석해줘.
지문의 내용에 없는 정보를 임의로 추가하지 말고,
실제 지문을 근거로 분석해줘.
"""

    try:

        # -----------------------------
        # 직접 입력한 지문
        # -----------------------------
        if passage is not None:

            response = client.responses.create(
                model="gpt-5.6-luna",
                input=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt + "\n\n영어 지문:\n" + passage
                    }
                ]
            )

        # -----------------------------
        # 사진으로 입력한 지문
        # -----------------------------
        elif image_data is not None:

            response = client.responses.create(
                model="gpt-5.6-luna",
                input=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    user_prompt
                                    + "\n\n사진 속 영어 지문을 읽고 분석해줘."
                                )
                            },
                            {
                                "type": "input_image",
                                "image_url": image_data
                            }
                        ]
                    }
                ]
            )

        else:
            return None, "분석할 지문이 없습니다."

        # AI 응답 가져오기
        answer = response.output_text.strip()

        # 혹시 AI가 코드블록으로 감싸서 답한 경우 제거
        if answer.startswith("```"):
            answer = answer.replace("```json", "")
            answer = answer.replace("```", "")
            answer = answer.strip()

        result = json.loads(answer)

        # -----------------------------
        # 결과 형식 확인
        # -----------------------------
        required_keys = [
            "korean_title",
            "english_title",
            "summary",
            "vocabulary",
            "grammar",
            "keywords"
        ]

        for key in required_keys:
            if key not in result:
                return None, "AI가 필요한 분석 결과를 모두 반환하지 않았습니다."

        return result, None

    except json.JSONDecodeError:
        return None, "AI의 분석 결과 형식을 읽는 중 문제가 발생했습니다."

    except Exception as e:
        return None, f"AI 분석 중 오류가 발생했습니다: {str(e)}"


# -----------------------------
# 시험범위 저장
# -----------------------------
def save_to_exam_scope(passage, result):

    if not passage.strip():
        return False

    # 같은 지문 중복 저장 방지
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
st.caption("영어 내신 지문을 한눈에 정리하다.")

st.divider()


# -----------------------------
# 지문 입력
# -----------------------------
st.subheader("📝 영어 지문")

input_method = st.radio(
    "지문 입력 방법",
    ["직접 입력", "사진 업로드"],
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
            "영어 지문을 여기에 붙여넣어 주세요.\n\n"
            "예시:\n"
            "Learning from mistakes is an important part of..."
        )
    )


# -----------------------------
# 사진 업로드
# -----------------------------
else:

    uploaded_image = st.file_uploader(
        "영어 지문 사진을 업로드하세요.",
        type=["png", "jpg", "jpeg"],
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

    # -----------------------------
    # 직접 입력
    # -----------------------------
    if input_method == "직접 입력":

        if not passage.strip():

            st.warning(
                "먼저 영어 지문을 입력해주세요."
            )

        elif len(passage.strip()) < 10:

            st.warning(
                "지문이 너무 짧습니다. 영어 지문을 조금 더 입력해주세요."
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

                st.session_state.current_passage = passage.strip()
                st.session_state.analysis_result = result

                st.success(
                    "✨ 지문 분석이 완료되었습니다!"
                )


    # -----------------------------
    # 사진 입력
    # -----------------------------
    else:

        if uploaded_image is None:

            st.warning(
                "먼저 영어 지문 사진을 업로드해주세요."
            )

        else:

            try:

                # 이미지 → Base64 Data URL
                import base64

                image_bytes = uploaded_image.getvalue()

                base64_image = base64.b64encode(
                    image_bytes
                ).decode("utf-8")

                image_data = (
                    f"data:{uploaded_image.type};base64,"
                    f"{base64_image}"
                )

                with st.spinner(
                    "🤖 AI가 사진 속 지문을 읽고 분석하고 있어요..."
                ):

                    result, error = analyze_with_ai(
                        image_data=image_data
                    )

                if error:

                    st.error(error)

                else:

                    # AI가 읽은 원문을 저장하기 위해
                    # 제목과 요약 등을 기준으로 저장
                    extracted_passage = (
                        "사진으로 입력된 영어 지문"
                    )

                    st.session_state.current_passage = (
                        extracted_passage
                    )

                    st.session_state.analysis_result = result

                    st.success(
                        "✨ 사진 속 지문 분석이 완료되었습니다!"
                    )

            except Exception as e:

                st.error(
                    f"사진을 처리하는 중 오류가 발생했습니다: {str(e)}"
                )


# -----------------------------
# 분석 결과
# -----------------------------
if st.session_state.analysis_result is not None:

    result = st.session_state.analysis_result

    st.divider()

    st.subheader("📖 분석 결과")


    # -----------------------------
    # 제목
    # -----------------------------
    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### 🇰🇷 한글 제목")

        st.info(
            result["korean_title"]
        )

    with col2:

        st.markdown("### 🇺🇸 English Title")

        st.info(
            result["english_title"]
        )


    # -----------------------------
    # 요약
    # -----------------------------
    st.markdown("### 📌 내용 요약")

    st.write(
        result["summary"]
    )


    # -----------------------------
    # 단어 / 문법
    # -----------------------------
    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### 🔤 중요 단어")

        for word in result["vocabulary"]:

            st.write(
                f"• {word}"
            )


    with col2:

        st.markdown("### 📐 중요 문법")

        for grammar in result["grammar"]:

            st.write(
                f"• {grammar}"
            )


    # -----------------------------
    # 핵심 키워드
    # -----------------------------
    st.markdown("### 🔑 3단 핵심키워드")

    keyword_cols = st.columns(3)

    for i, keyword in enumerate(
        result["keywords"][:3]
    ):

        with keyword_cols[i]:

            st.info(
                keyword
            )


    # -----------------------------
    # 시험범위 저장
    # -----------------------------
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

                st.session_state.exam_scope.pop(
                    index
                )

                st.rerun()
