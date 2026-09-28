import streamlit as st

# -------------------------
# 기본 설정
# -------------------------
st.set_page_config(
    page_title="English Study",
    page_icon="📚",
    layout="wide"
)

# -------------------------
# 제목
# -------------------------
st.title("📚 English Study")
st.write("영어 내신 지문을 한눈에 정리하고 시험 전에 빠르게 복습해보세요.")

st.divider()

# -------------------------
# 지문 입력
# -------------------------
st.subheader("📝 영어 지문")

passage = st.text_area(
    "분석할 영어 지문을 입력하세요.",
    height=250,
    placeholder="영어 지문을 여기에 붙여넣어 주세요."
)

if st.button("✨ 지문 분석하기", use_container_width=True):

    if passage.strip() == "":
        st.warning("먼저 영어 지문을 입력해주세요.")

    else:
        st.success("지문이 입력되었습니다!")

        st.divider()

        # -------------------------
        # 분석 결과
        # -------------------------
        st.subheader("📖 분석 결과")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🇰🇷 한글 제목")
            st.info("AI가 지문의 핵심 내용을 바탕으로 제목을 생성합니다.")

        with col2:
            st.markdown("### 🇺🇸 English Title")
            st.info("AI가 지문의 핵심 내용을 영어 제목으로 정리합니다.")

        st.markdown("### 📌 내용 요약")
        st.info("AI가 지문의 주요 내용을 간단하게 정리합니다.")

        st.markdown("### 🔤 단어 · 문법")
        st.info("중요한 단어와 문법 표현을 정리합니다.")

        st.markdown("### 🔑 3단 핵심키워드")
        st.info("지문을 기억하기 위한 핵심 키워드 3개를 정리합니다.")

        st.divider()

        # -------------------------
        # 시험범위 저장
        # -------------------------
        st.subheader("📚 시험범위")

        if st.button("➕ 내 시험범위에 저장", use_container_width=True):
            st.success("시험범위에 저장되었습니다!")
