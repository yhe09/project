import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="전국 고령화 지도",
    page_icon="👵",
    layout="wide"
)

st.title("🇰🇷 전국 시군구 고령화 지도")
st.caption("65세 이상 인구 비율을 기준으로 전국 시군구의 고령화 정도를 보여 줍니다.")


# ============================================================
# 데이터 주소
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
# 데이터 불러오기
# ============================================================

@st.cache_data
def load_population():
    """인구 데이터를 불러오고 최신 연도 자료만 남깁니다."""

    # gzip 압축 CSV도 pandas가 바로 읽을 수 있습니다.
    df = pd.read_csv(
        POPULATION_URL,
        compression="gzip",
        dtype={"코드": str}
    )

    # 코드가 숫자로 바뀌지 않도록 문자열로 다시 확실하게 처리합니다.
    df["코드"] = df["코드"].astype(str).str.zfill(8)

    # 데이터에 들어 있는 가장 최신 연도를 자동으로 찾습니다.
    latest_year = df["연도"].max()

    # 최신 연도 자료만 사용합니다.
    df = df[df["연도"] == latest_year].copy()

    return df, latest_year


@st.cache_data
def load_geojson():
    """시군구 경계 GeoJSON을 불러옵니다."""

    response = requests.get(GEOJSON_URL, timeout=30)
    response.raise_for_status()

    return response.json()


# ============================================================
# 데이터 처리
# ============================================================

@st.cache_data
def make_elderly_data(df):
    """
    읍·면·동 자료를 시군구 단위로 합칩니다.

    코드 앞 5자리가 시군구 코드이므로
    이름이 아니라 코드로 지역을 연결합니다.
    """

    # 코드 앞 5자리가 시군구 코드입니다.
    df["시군구코드"] = df["코드"].str[:5]

    # 65세 이상 나이 열 찾기
    elderly_columns = []

    for age in range(65, 100):
        elderly_columns.append(f"계_{age}세")

    # '100세 이상'도 포함합니다.
    elderly_columns.append("계_100세 이상")

    # 실제 데이터에 존재하는 열만 사용합니다.
    elderly_columns = [
        col for col in elderly_columns
        if col in df.columns
    ]

    # 전체 인구 열
    total_column = "계_0세"

    # 계_0세는 0세 인구이므로 전체 인구를 뜻하지 않습니다.
    # 따라서 모든 '계_나이' 열을 합쳐 전체 인구를 계산합니다.
    total_columns = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    # 65세 이상 인구
    df["65세이상"] = df[elderly_columns].sum(axis=1)

    # 전체 연령 인구
    df["전체인구"] = df[total_columns].sum(axis=1)

    # 시군구별로 인구를 합칩니다.
    result = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            시군구=("시군구", "first"),
            시도=("시도", "first"),
            전체인구=("전체인구", "sum"),
            **{"65세이상": ("65세이상", "sum")}
        )
    )

    # 고령화율 = 65세 이상 인구 / 전체 인구 × 100
    result["고령화율"] = (
        result["65세이상"] / result["전체인구"] * 100
    )

    return result


# ============================================================
# 색상 단계
# ============================================================

def get_color(value):
    """
    고령화율을 5단계 색으로 나눕니다.

    19%, 23%, 28%, 38%를 경계값으로 사용합니다.
    """

    if value < 19:
        return "#edf8fb"
    elif value < 23:
        return "#b2e2e2"
    elif value < 28:
        return "#66c2a4"
    elif value < 38:
        return "#2ca25f"
    else:
        return "#006d2c"


# ============================================================
# 지도 만들기
# ============================================================

def make_map(data, geojson):
    """시군구별 고령화율을 지도에 표시합니다."""

    fig = go.Figure()

    # GeoJSON의 각 지역을 하나씩 그립니다.
    for feature in geojson["features"]:

        properties = feature.get("properties", {})

        # 경계 데이터의 시군구 코드
        code = str(properties.get("코드", "")).zfill(5)

        # 해당 지역의 인구 데이터를 찾습니다.
        row = data[data["시군구코드"] == code]

        # 인구 데이터가 없는 지역은 표시하지 않습니다.
        if row.empty:
            continue

        row = row.iloc[0]

        value = float(row["고령화율"])
        color = get_color(value)

        geometry = feature["geometry"]

        # Polygon과 MultiPolygon을 모두 처리합니다.
        if geometry["type"] == "Polygon":
            polygons = [geometry["coordinates"]]

        elif geometry["type"] == "MultiPolygon":
            polygons = geometry["coordinates"]

        else:
            continue

        for polygon in polygons:

            # Polygon의 첫 번째 좌표가 외곽선입니다.
            outer_ring = polygon[0]

            lons = [point[0] for point in outer_ring]
            lats = [point[1] for point in outer_ring]

            fig.add_trace(
                go.Scattergeo(
                    lon=lons,
                    lat=lats,
                    mode="lines",
                    fill="toself",
                    fillcolor=color,
                    line=dict(
                        color="white",
                        width=0.6
                    ),
                    hovertemplate=(
                        f"<b>{row['시군구']}</b><br>"
                        f"시도: {row['시도']}<br>"
                        f"고령화율: {value:.2f}%"
                        "<extra></extra>"
                    ),
                    showlegend=False
                )
            )

    # 배경 타일 없이 대한민국 경계만 표시합니다.
    fig.update_geos(
        scope="asia",
        projection_type="mercator",
        showland=False,
        showocean=False,
        showcountries=False,
        showcoastlines=False,
        showframe=False,
        fitbounds="locations"
    )

    fig.update_layout(
        height=700,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="white",
        geo=dict(
            center=dict(
                lat=36.3,
                lon=127.8
            ),
            projection_scale=5.5
        )
    )

    return fig


# ============================================================
# 실행
# ============================================================

try:
    population_df, latest_year = load_population()
    geojson = load_geojson()

    data = make_elderly_data(population_df)

except Exception as e:
    st.error("데이터를 불러오는 중 문제가 발생했습니다.")
    st.exception(e)
    st.stop()


# ============================================================
# 제목 아래 설명
# ============================================================

st.info(
    f"📌 {latest_year}년 기준 · 65세 이상 인구 비율 · 전국 시군구"
)


# ============================================================
# 지도
# ============================================================

st.plotly_chart(
    make_map(data, geojson),
    use_container_width=True,
    config={
        "displayModeBar": False
    }
)


# ============================================================
# 범례
# ============================================================

st.markdown("### 🎨 고령화율 범례")

legend_items = [
    ("19% 미만", "#edf8fb"),
    ("19% 이상 ~ 23% 미만", "#b2e2e2"),
    ("23% 이상 ~ 28% 미만", "#66c2a4"),
    ("28% 이상 ~ 38% 미만", "#2ca25f"),
    ("38% 이상", "#006d2c"),
]

legend_html = """
<div style="
    display:flex;
    flex-wrap:wrap;
    gap:12px;
    margin-bottom:20px;
">
"""

for label, color in legend_items:
    legend_html += f"""
    <div style="
        display:flex;
        align-items:center;
        gap:6px;
        font-size:14px;
    ">
        <div style="
            width:22px;
            height:22px;
            background:{color};
            border:1px solid #999;
        "></div>
        <span>{label}</span>
    </div>
    """

legend_html += "</div>"

st.markdown(legend_html, unsafe_allow_html=True)


# ============================================================
# 상위 / 하위 10개 지역
# ============================================================

st.markdown("### 📊 시군구별 고령화율")

high_data = (
    data.sort_values("고령화율", ascending=False)
    .head(10)
    .copy()
)

low_data = (
    data.sort_values("고령화율", ascending=True)
    .head(10)
    .copy()
)


# 표에 표시할 형태로 정리합니다.
def format_table(df):
    table = df[["시도", "시군구", "고령화율"]].copy()

    table["고령화율"] = table["고령화율"].map(
        lambda x: f"{x:.2f}%"
    )

    table.index = range(1, len(table) + 1)

    return table


col1, col2 = st.columns(2)

with col1:
    st.subheader("🔴 고령화율 높은 지역 TOP 10")
    st.dataframe(
        format_table(high_data),
        use_container_width=True
    )

with col2:
    st.subheader("🔵 고령화율 낮은 지역 TOP 10")
    st.dataframe(
        format_table(low_data),
        use_container_width=True
    )


# ============================================================
# 간단한 데이터 설명
# ============================================================

st.caption(
    "고령화율은 시군구 전체 인구 중 65세 이상 인구가 차지하는 비율입니다. "
    "읍·면·동 인구를 시군구 코드 기준으로 합산하여 계산했습니다."
)
