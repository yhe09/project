import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go


# ============================================================
# 1. 기본 설정
# ============================================================

st.set_page_config(
    page_title="전국 고령화 지도",
    page_icon="👵",
    layout="wide"
)

st.title("🇰🇷 전국 고령화 지도")
st.caption("시군구별 65세 이상 인구 비율 · 최신 연도 기준")


# ============================================================
# 2. 데이터 주소
# ============================================================

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/population_yearly.csv.gz"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/"
    "data/boundaries/sigungu_kr.geojson"
)


# ============================================================
# 3. 인구 데이터 불러오기
# ============================================================

@st.cache_data
def load_population():
    """전국 읍·면·동 인구 데이터를 불러옵니다."""

    df = pd.read_csv(
        POPULATION_URL,
        compression="gzip",
        dtype={"코드": str}
    )

    # 행정동 코드는 계산하는 숫자가 아니라 이름표이므로
    # 반드시 문자열로 처리합니다.
    df["코드"] = df["코드"].astype(str).str.zfill(8)

    # 데이터에 들어 있는 가장 최신 연도를 사용합니다.
    latest_year = df["연도"].max()

    df = df[df["연도"] == latest_year].copy()

    return df, latest_year


# ============================================================
# 4. 지도 경계 데이터 불러오기
# ============================================================

@st.cache_data
def load_geojson():
    """전국 시군구 경계 GeoJSON을 불러옵니다."""

    response = requests.get(GEOJSON_URL, timeout=30)
    response.raise_for_status()

    geojson = response.json()

    # GeoJSON의 시군구 코드도 문자열로 통일합니다.
    for feature in geojson["features"]:
        code = feature["properties"].get("코드")
        feature["properties"]["코드"] = str(code).zfill(5)

    return geojson


# ============================================================
# 5. 시군구별 고령화율 계산
# ============================================================

@st.cache_data
def calculate_elderly_rate(df):
    """읍·면·동 인구를 시군구 단위로 합쳐 고령화율을 계산합니다."""

    df = df.copy()

    # 행정동 코드의 앞 5자리가 시군구 코드입니다.
    df["시군구코드"] = df["코드"].str[:5]

    # --------------------------------------------------------
    # 65세 이상 인구 열 찾기
    # --------------------------------------------------------

    elderly_columns = []

    for age in range(65, 100):
        column = f"계_{age}세"

        if column in df.columns:
            elderly_columns.append(column)

    if "계_100세 이상" in df.columns:
        elderly_columns.append("계_100세 이상")

    # --------------------------------------------------------
    # 전체 인구 열 찾기
    # --------------------------------------------------------

    # '계_'로 시작하는 열은 남녀 합계입니다.
    # 모든 연령의 계_ 열을 더하면 전체 인구가 됩니다.
    total_columns = [
        column
        for column in df.columns
        if column.startswith("계_")
    ]

    # 숫자형으로 확실하게 변환합니다.
    for column in elderly_columns + total_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0)

    # 65세 이상 인구
    df["65세이상인구"] = df[elderly_columns].sum(axis=1)

    # 전체 인구
    df["전체인구"] = df[total_columns].sum(axis=1)

    # --------------------------------------------------------
    # 시군구별 합계
    # --------------------------------------------------------

    result = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            시군구=("시군구", "first"),
            시도=("시도", "first"),
            전체인구=("전체인구", "sum"),
            **{"65세이상인구": ("65세이상인구", "sum")}
        )
    )

    # 고령화율 계산
    result["고령화율"] = (
        result["65세이상인구"]
        / result["전체인구"]
        * 100
    )

    return result


# ============================================================
# 6. 데이터 불러오기
# ============================================================

try:
    population_df, latest_year = load_population()
    geojson = load_geojson()
    elderly_df = calculate_elderly_rate(population_df)

except Exception as e:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.code(str(e))
    st.stop()


# ============================================================
# 7. 지도용 데이터 준비
# ============================================================

# GeoJSON과 인구 데이터를 시군구 코드로 연결합니다.
# 이름으로 연결하지 않습니다.
map_df = elderly_df.copy()

map_df["시군구코드"] = (
    map_df["시군구코드"]
    .astype(str)
    .str.zfill(5)
)

# 지도에 넣을 추가 정보
map_df["고령화율표시"] = map_df["고령화율"].map(
    lambda x: f"{x:.2f}%"
)


# ============================================================
# 8. 5단계 색상 설정
# ============================================================

# 구간:
# 19% 미만
# 19% 이상 ~ 23% 미만
# 23% 이상 ~ 28% 미만
# 28% 이상 ~ 38% 미만
# 38% 이상

colors = [
    "#edf8fb",
    "#b2e2e2",
    "#66c2a4",
    "#2ca25f",
    "#006d2c"
]

labels = [
    "19% 미만",
    "19% 이상 ~ 23% 미만",
    "23% 이상 ~ 28% 미만",
    "28% 이상 ~ 38% 미만",
    "38% 이상"
]


def make_discrete_colorscale():
    """
    Plotly에서 색이 부드럽게 이어지지 않고
    5단계로 딱 끊어지도록 색상표를 만듭니다.
    """

    # 지도 색상 범위의 최대값
    max_value = max(
        40,
        float(np.ceil(map_df["고령화율"].max() / 5) * 5)
    )

    # 각 경계값을 0~1 사이 위치로 바꿉니다.
    boundaries = [
        0,
        19,
        23,
        28,
        38,
        max_value
    ]

    normalized = [
        min(1, value / max_value)
        for value in boundaries
    ]

    colorscale = []

    # 같은 위치에 두 색을 연속해서 넣으면
    # 그 지점에서 색이 부드럽게 섞이지 않고 딱 바뀝니다.
    for i in range(5):
        start = normalized[i]
        end = normalized[i + 1]

        colorscale.append([start, colors[i]])
        colorscale.append([end, colors[i]])

    return colorscale, max_value


colorscale, map_max = make_discrete_colorscale()


# ============================================================
# 9. 지도 만들기
# ============================================================

fig = go.Figure()

fig.add_trace(
    go.Choropleth(
        # GeoJSON 경계
        geojson=geojson,

        # 인구 데이터와 GeoJSON을 연결할 코드
        locations=map_df["시군구코드"],

        # GeoJSON properties 안의 '코드'와 연결
        featureidkey="properties.코드",

        # 색칠할 값
        z=map_df["고령화율"],

        # 5단계 색상
        colorscale=colorscale,
        zmin=0,
        zmax=map_max,

        # 경계선
        marker_line_color="white",
        marker_line_width=0.7,

        # 마우스를 올렸을 때 표시할 정보
        customdata=map_df[
            ["시군구", "시도", "고령화율"]
        ].values,

        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "시도: %{customdata[1]}<br>"
            "고령화율: %{customdata[2]:.2f}%"
            "<extra></extra>"
        ),

        # Plotly 기본 색상 범례는 사용하지 않습니다.
        showscale=False
    )
)


# ============================================================
# 10. 지도 화면 설정
# ============================================================

fig.update_geos(
    # 대한민국을 중심으로 표시
    center=dict(
        lat=36.3,
        lon=127.8
    ),

    # 지도 확대 정도
    projection_scale=5.3,

    # 배경 지도 타일 없음
    showland=False,
    showocean=False,
    showcountries=False,
    showcoastlines=False,
    showframe=False,

    # GeoJSON에 맞춰 화면을 잡습니다.
    fitbounds="locations"
)

fig.update_layout(
    height=700,
    margin=dict(
        l=0,
        r=0,
        t=10,
        b=0
    ),
    paper_bgcolor="white"
)


# ============================================================
# 11. 최신 연도 표시
# ============================================================

st.info(
    f"📌 {latest_year}년 기준 · 전국 시군구 65세 이상 인구 비율"
)


# ============================================================
# 12. 지도 출력
# ============================================================

st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "displayModeBar": False
    }
)


# ============================================================
# 13. 범례
# ============================================================

st.markdown("### 🎨 고령화율 범례")

# HTML을 통째로 한 번에 넣지 않고
# Streamlit의 columns를 이용해서 안전하게 표시합니다.

legend_columns = st.columns(5)

for column, label, color in zip(
    legend_columns,
    labels,
    colors
):
    with column:

        st.markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                gap:8px;
                margin-bottom:15px;
            ">
                <div style="
                    width:22px;
                    height:22px;
                    min-width:22px;
                    background-color:{color};
                    border:1px solid #999;
                    border-radius:3px;
                "></div>

                <div style="
                    font-size:14px;
                    white-space:nowrap;
                ">
                    {label}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# 14. TOP 10 / 하위 10 데이터
# ============================================================

high_df = (
    elderly_df
    .sort_values("고령화율", ascending=False)
    .head(10)
    .copy()
)

low_df = (
    elderly_df
    .sort_values("고령화율", ascending=True)
    .head(10)
    .copy()
)


# ============================================================
# 15. 표 모양 정리
# ============================================================

def format_table(df):
    """표에 표시할 열과 숫자 형식을 정리합니다."""

    table = df[
        ["시도", "시군구", "고령화율"]
    ].copy()

    table["고령화율"] = table["고령화율"].map(
        lambda x: f"{x:.2f}%"
    )

    table.index = range(1, len(table) + 1)

    return table


# ============================================================
# 16. 높은 지역 / 낮은 지역 표
# ============================================================

st.markdown("### 📊 시군구별 고령화율")

left, right = st.columns(2)

with left:

    st.subheader("고령화율 높은 곳 TOP 10")

    st.dataframe(
        format_table(high_df),
        use_container_width=True,
        height=430
    )


with right:

    st.subheader("고령화율 낮은 곳 TOP 10")

    st.dataframe(
        format_table(low_df),
        use_container_width=True,
        height=430
    )


# ============================================================
# 17. 계산 방법
# ============================================================

st.caption(
    "고령화율 = 65세 이상 인구 ÷ 전체 인구 × 100"
)

st.caption(
    "읍·면·동 인구를 행정동 코드 앞 5자리인 시군구 코드 기준으로 합산했습니다."
)
