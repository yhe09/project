import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 트렌드 시각화",
    page_icon="👵",
    layout="wide"
)

st.title("👵 한눈에 보는 전국 시군구 고령화 구조")
st.caption("인구 규모(상자 크기)와 고령화율(색상)을 동시에 분석할 수 있는 시각화 대시보드입니다.")

# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 (캐싱 처리로 속도 최적화)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # '코드' 열은 앞자리 '0'이 유지되도록 문자열(str) 유형으로 읽어옵니다.
    df = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 가장 최신 연도 추출
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 시군구 코드 추출 (10자리 행정동 코드 중 앞 5자리)
    df_latest['sigungu_code'] = df_latest['코드'].str[:5]
    
    # 65세 이상 '계_' 열 이름 찾기
    age_cols = [col for col in df_latest.columns if col.startswith('계_')]
    
    def get_age(col_name):
        age_str = col_name.replace('계_', '').replace('세 이상', '').replace('세', '')
        return int(age_str)
    
    col_total = [col for col in age_cols if get_age(col) >= 0]     # 전체 인구
    col_65plus = [col for col in age_cols if get_age(col) >= 65]  # 65세 이상 인구
    
    # 시군구 코드별로 인구 합산
    df_latest['total_pop'] = df_latest[col_total].sum(axis=1)
    df_latest['pop_65plus'] = df_latest[col_65plus].sum(axis=1)
    
    # 시군구 단위 그룹화
    grouped = df_latest.groupby('sigungu_code').agg({
        '시도': 'first',
        '시군구': 'first',
        'total_pop': 'sum',
        'pop_65plus': 'sum'
    }).reset_index()
    
    # 고령화 비율 계산 (%)
    grouped['고령화율'] = (grouped['pop_65plus'] / grouped['total_pop']) * 100
    grouped['고령화율'] = grouped['고령화율'].round(2)
    
    return latest_year, grouped

with st.spinner("최신 인구 데이터를 분석하고 시각화 요소를 생성하는 중입니다..."):
    latest_year, df_sigungu = load_data()

st.sidebar.markdown(f"**기준 연도**: {latest_year}년")

# -----------------------------------------------------------------------------
# 3. 5단계 구간 나누기 (19%, 23%, 28%, 38% 기준)
# -----------------------------------------------------------------------------
bins = [0, 19, 23, 28, 38, 100]
labels = [
    "19% 미만",
    "19% 이상 ~ 23% 미만",
    "23% 이상 ~ 28% 미만",
    "28% 이상 ~ 38% 미만",
    "38% 이상"
]

df_sigungu['고령화_구간'] = pd.cut(
    df_sigungu['고령화율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# -----------------------------------------------------------------------------
# 4. 시군구 인구수 x 고령화 비율 트리맵(Treemap)
# -----------------------------------------------------------------------------
st.subheader("📦 시도/시군구별 인구 규모 및 고령화율 트리맵")
st.markdown("""
- **상자 크기**: 시군구 전체 인구수 (인구가 많을수록 상자가 큼)
- **상자 색상**: 고령화 비율 (%) 연속형 컬러 스케일 (붉은색일수록 고령화 심각)
""")

# 오류 발생 위험 요소를 모두 배제한 가장 안정적인 연속형 트리맵 생성
fig_treemap = px.treemap(
    df_sigungu,
    path=[px.Constant("전국"), '시도', '시군구'],
    values='total_pop',
    color='고령화율',
    color_continuous_scale="Reds"
)

fig_treemap.update_layout(
    margin=dict(t=20, l=10, r=10, b=10),
    height=600
)

st.plotly_chart(fig_treemap, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. 시도별 고령화 구간 분포 히트맵 매트릭스
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🧩 광역지자체(시도)별 고령화 구간 분포 매트릭스")

pivot_df = pd.crosstab(df_sigungu['시도'], df_sigungu['고령화_구간'])
pivot_df = pivot_df.reindex(columns=labels, fill_value=0)

fig_heatmap = px.imshow(
    pivot_df,
    labels=dict(x="고령화 비율 구간", y="시도", color="시군구 수"),
    x=labels,
    y=pivot_df.index,
    color_continuous_scale="YlOrRd",
    aspect="auto",
    text_auto=True
)

fig_heatmap.update_layout(
    height=500,
    margin=dict(t=20, l=10, r=10, b=10)
)

st.plotly_chart(fig_heatmap, use_container_width=True)

# -----------------------------------------------------------------------------
# 6. 상위 10개 / 하위 10개 시군구 표 나란히 출력
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 고령화 비율 극단값 비교 (상위 / 하위 10개 지역)")

top10 = df_sigungu.sort_values(by='고령화율', ascending=False).head(10)[['시도', '시군구', 'total_pop', '고령화율']]
top10 = top10.reset_index(drop=True)
top10.index = top10.index + 1

bottom10 = df_sigungu.sort_values(by='고령화율', ascending=True).head(10)[['시도', '시군구', 'total_pop', '고령화율']]
bottom10 = bottom10.reset_index(drop=True)
bottom10.index = bottom10.index + 1

col1, col2 = st.columns(2)

with col1:
    st.markdown("##### 🔴 고령화 비율이 가장 높은 지역 TOP 10")
    st.dataframe(
        top10.rename(columns={'total_pop': '총인구수'}).style.format({
            '총인구수': '{:,}명',
            '고령화율': '{:.2f}%'
        }),
        use_container_width=True
    )

with col2:
    st.markdown("##### 🟢 고령화 비율이 가장 낮은 지역 TOP 10")
    st.dataframe(
        bottom10.rename(columns={'total_pop': '총인구수'}).style.format({
            '총인구수': '{:,}명',
            '고령화율': '{:.2f}%'
        }),
        use_container_width=True
    )
