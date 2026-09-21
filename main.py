import streamlit as st
import pandas as pd


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="전국 고령화율 한눈에 보기",
    page_icon="🇰🇷",
    layout="wide"
)


# ============================================================
# 데이터 주소
# ============================================================

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)


# ============================================================
# 데이터 불러오기
# ============================================================

@st.cache_data
def load_data():

    # 코드가 숫자로 바뀌지 않도록 문자열로 읽습니다.
    df = pd.read_csv(
        POPULATION_URL,
        compression="gzip",
        dtype={"코드": str}
    )

    # 필요한 열이 있는지 확인합니다.
    required_columns = {
        "연도",
        "시도",
        "시군구",
        "코드"
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "필수 열이 없습니다: "
            + ", ".join(sorted(missing_columns))
        )

    # 코드 앞에 0이 필요한 경우를 대비합니다.
    df["코드"] = (
        df["코드"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(8)
    )

    # 가장 최신 연도만 사용합니다.
    latest_year = df["연도"].max()

    df = df[
        df["연도"] == latest_year
    ].copy()


    # ========================================================
    # 나이별 인구 열 찾기
    # ========================================================

    # '계_'로 시작하는 열은 남녀 합계입니다.
    total_columns = [
        column
        for column in df.columns
        if column.startswith("계_")
    ]

    # 65세 이상 열만 골라냅니다.
    elderly_columns = []

    for column in total_columns:

        age = column[2:]

        if age == "100세 이상":
            elderly_columns.append(column)

        elif age.endswith("세"):

            try:
                age_number = int(age[:-1])

                if age_number >= 65:
                    elderly_columns.append(column)

            except ValueError:
                pass


    if not total_columns:
        raise ValueError(
            "'계_'로 시작하는 나이별 인구 열을 찾지 못했습니다."
        )

    if not elderly_columns:
        raise ValueError(
            "65세 이상 인구 열을 찾지 못했습니다."
        )


    # ========================================================
    # 숫자형으로 변환
    # ========================================================

    for column in total_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0)


    # ========================================================
    # 전체 인구 / 65세 이상 인구 계산
    # ========================================================

    df["전체인구"] = df[
        total_columns
    ].sum(axis=1)

    df["65세이상"] = df[
        elderly_columns
    ].sum(axis=1)


    # ========================================================
    # 시군구 코드 만들기
    # ========================================================

    # 읍·면·동 코드의 앞 5자리가 시군구 코드입니다.
    df["시군구코드"] = df[
        "코드"
    ].str[:5]


    # ========================================================
    # 시군구별로 합치기
    # ========================================================

    result = (
        df.groupby(
            "시군구코드",
            as_index=False
        )
        .agg(
            시도=("시도", "first"),
            시군구=("시군구", "first"),
            전체인구=("전체인구", "sum"),
            **{
                "65세이상": (
                    "65세이상",
                    "sum"
                )
            }
        )
    )


    # ========================================================
    # 고령화율 계산
    # ========================================================

    result["고령화율"] = (
        result["65세이상"]
        / result["전체인구"]
        * 100
    )


    # 계산할 수 없는 지역 제거
    result = result[
        result["고령화율"].notna()
        & result["고령화율"].notnull()
    ].copy()

    return result, latest_year


# ============================================================
# 색상 정하기
# ============================================================

def get_color(rate):

    if rate < 19:
        return "#E8F4F8"

    elif rate < 23:
        return "#B7DFE3"

    elif rate < 28:
        return "#70C5B0"

    elif rate < 38:
        return "#32A866"

    else:
        return "#087F3F"


# ============================================================
# 시군구 색깔 격자 만들기
# ============================================================

def show_color_grid(data):

    # 시도별로 묶습니다.
    grouped = data.groupby(
        "시도",
        sort=True
    )


    # --------------------------------------------------------
    # 화면에 들어갈 HTML
    # --------------------------------------------------------

    html_parts = []


    # 각 시도를 하나씩 만듭니다.
    for sido, group in grouped:

        # 같은 시도 안에서는 고령화율 순서로 정렬합니다.
        group = group.sort_values(
            ["고령화율", "시군구"]
        )


        # 시군구 타일을 담을 부분
        tiles = []


        for _, row in group.iterrows():

            name = str(row["시군구"])
            rate = float(row["고령화율"])

            color = get_color(rate)


            # 시군구 하나 = 타일 하나
            tile = f"""
            <div
                title="{name} · 고령화율 {rate:.2f}%"
                style="
                    width:104px;
                    min-height:48px;
                    box-sizing:border-box;
                    padding:7px 8px;
                    background:{color};
                    border:1px solid rgba(0,0,0,0.08);
                    border-radius:8px;
                    display:flex;
                    flex-direction:column;
                    justify-content:center;
                    line-height:1.15;
                "
            >
                <span
                    style="
                        font-size:12px;
                        overflow:hidden;
                        text-overflow:ellipsis;
                        white-space:nowrap;
                    "
                >
                    {name}
                </span>

                <span
                    style="
                        font-size:11px;
                        margin-top:4px;
                        opacity:0.8;
                    "
                >
                    {rate:.1f}%
                </span>
            </div>
            """

            tiles.append(tile)


        # 시도 하나의 행을 만듭니다.
        row_html = f"""
        <div style="margin-bottom:18px;">

            <div
                style="
                    font-size:15px;
                    font-weight:700;
                    margin-bottom:7px;
                "
            >
                {sido}
            </div>

            <div
                style="
                    display:flex;
                    flex-wrap:wrap;
                    gap:6px;
                "
            >
                {"".join(tiles)}
            </div>

        </div>
        """

        html_parts.append(row_html)


    # --------------------------------------------------------
    # 최종 출력
    # --------------------------------------------------------

    final_html = f"""
    <div style="width:100%;">
        {"".join(html_parts)}
    </div>
    """


    st.markdown(
        final_html,
        unsafe_allow_html=True
    )


# ============================================================
# 실행
# ============================================================

try:

    data, latest_year = load_data()

except Exception as error:

    st.error(
        "데이터를 불러오는 중 문제가 발생했습니다."
    )

    st.exception(error)

    st.stop()


# ============================================================
# 제목
# ============================================================

st.title("🇰🇷 전국 고령화율 한눈에 보기")

st.caption(
    f"{latest_year}년 기준 · 시군구별 65세 이상 인구 비율"
)


# ============================================================
# 색깔 격자
# ============================================================

st.markdown(
    "### 🎨 시도별 시군구 고령화율"
)

st.write(
    "각 칸은 하나의 시군구입니다. "
    "색이 진할수록 65세 이상 인구 비율이 높습니다."
)


show_color_grid(data)


# ============================================================
# 범례
# ============================================================

st.markdown(
    "### 범례"
)


legend = [
    ("19% 미만", "#E8F4F8"),
    ("19% 이상 ~ 23% 미만", "#B7DFE3"),
    ("23% 이상 ~ 28% 미만", "#70C5B0"),
    ("28% 이상 ~ 38% 미만", "#32A866"),
    ("38% 이상", "#087F3F"),
]


legend_columns = st.columns(5)


for column, (label, color) in zip(
    legend_columns,
    legend
):

    with column:

        st.markdown(
            f"""
            <div
                style="
                    display:flex;
                    align-items:center;
                    gap:7px;
                "
            >

                <span
                    style="
                        display:inline-block;
                        width:18px;
                        height:18px;
                        border-radius:4px;
                        background:{color};
                        border:1px solid #aaa;
                    "
                ></span>

                <span>
                    {label}
                </span>

            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# 간단한 요약
# ============================================================

st.markdown("---")

st.caption(
    "고령화율 = 65세 이상 인구 ÷ 전체 인구 × 100"
)

st.caption(
    "읍·면·동 인구를 행정동 코드 앞 5자리인 시군구 코드 기준으로 합산했습니다."
)
