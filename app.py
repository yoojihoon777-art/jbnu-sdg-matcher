from pathlib import Path
import base64

import pandas as pd
import streamlit as st

from boolean_engine import (
    Paper,
    Truth,
    evaluate_query_file,
    guide_query_file,
)


SDG_NAMES = {
    1: "빈곤퇴치",
    2: "기아종식",
    3: "건강과 웰빙",
    4: "양질의 교육",
    5: "성평등",
    6: "깨끗한 물과 위생",
    7: "모두를 위한 깨끗한 에너지",
    8: "양질의 일자리와 경제성장",
    9: "산업·혁신·인프라",
    10: "불평등 감소",
    11: "지속가능한 도시와 공동체",
    12: "책임있는 소비와 생산",
    13: "기후행동",
    14: "해양생태계 보전",
    15: "육상생태계 보전",
    16: "평화·정의·강한 제도",
    17: "목표를 위한 파트너십",
}

FIELD_LABELS = {
    "title": "제목",
    "abstract": "초록",
    "keywords": "저자키워드",
    "subject_area": "연구분야",
}

STATUS_LABEL = {
    Truth.TRUE: "해당",
    Truth.FALSE: "미해당",
    Truth.UNKNOWN: "판정 보류",
}

STATUS_ICON = {
    Truth.TRUE: "✅",
    Truth.FALSE: "❌",
    Truth.UNKNOWN: "⚠️",
}

GUIDE_STATUS_ICON = {
    "충족": "✅",
    "미충족": "❌",
    "위치 불일치": "⚠️",
    "근접조건 미충족": "↔️",
    "입력 확인 필요": "⚠️",
    "제외조건": "⛔",
}



def get_logo_data_uri(path: str = "logo.png"):
    logo_path = Path(path)
    if not logo_path.exists():
        return None

    encoded = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def get_sdg_logo_data_uri(sdg: int):
    """SDG 공식 아이콘 파일: logo-1_120x120_png.png ~ logo-17_120x120_png.png"""
    return get_logo_data_uri(f"logo-{sdg}_120x120_png.png")


def compact_notes(notes):
    seen = []
    for note in notes:
        if note not in seen:
            seen.append(note)
    return seen


@st.cache_resource(show_spinner=False)
def get_query_paths(query_dir: str):
    base = Path(query_dir)
    return {i: base / f"SDG{i:02d}.txt" for i in range(1, 17)}


def run_all_sdgs(paper: Paper, query_dir: str):
    query_paths = get_query_paths(query_dir)
    results = {}

    for sdg, path in query_paths.items():
        if not path.exists():
            results[sdg] = {
                "error": f"검색식 파일 없음: {path.name}",
                "result": None,
            }
            continue

        try:
            result = evaluate_query_file(path, paper)
            results[sdg] = {
                "error": None,
                "result": result,
            }
        except Exception as exc:
            results[sdg] = {
                "error": str(exc),
                "result": None,
            }

    return results


st.set_page_config(
    page_title="JBNU 연구성과 지속가능발전목표(SDGs) 매칭 시스템",
    page_icon="🌍",
    layout="wide",
)


# ============================================================
# JBNU UI 디자인
# 기본색: Burgundy #a6165f / Blue #004386
# 모든 페이지에서 밝은 배경 + 진한 글씨를 사용해 가독성을 확보합니다.
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --jbnu-blue: #004386;
        --jbnu-burgundy: #a6165f;
        --text-main: #172033;
        --text-sub: #4b5563;
        --surface: #ffffff;
        --surface-soft: #f3f4f6;
        --border: #d8dee8;
    }

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: var(--surface) !important;
        color: var(--text-main) !important;
    }

    .block-container {
        max-width: 1280px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }

    .stApp p,
    .stApp li,
    .stApp label,
    .stApp [data-testid="stMarkdownContainer"] {
        color: var(--text-main);
    }

    h1 {
        color: var(--jbnu-blue) !important;
        font-weight: 800 !important;
        letter-spacing: -0.035em;
        padding-bottom: 0.72rem !important;
        margin-bottom: 1rem !important;
        border-bottom: 2px solid var(--jbnu-blue);
        position: relative;
    }

    h1::after {
        content: "";
        position: absolute;
        left: 0;
        bottom: -2px;
        width: 90px;
        height: 3px;
        background: var(--jbnu-burgundy);
    }

    /* 메인 타이틀 안 전북대 로고 */
    .jbnu-main-title {
        display: flex;
        align-items: center;
        gap: 0.65rem;
    }

    .jbnu-main-title img {
        width: 46px;
        height: 46px;
        object-fit: contain;
        flex: 0 0 auto;
    }

    .jbnu-main-title span {
        color: var(--jbnu-blue) !important;
    }

    h2 {
        color: var(--jbnu-blue) !important;
        font-weight: 750 !important;
        letter-spacing: -0.02em;
        border-left: 5px solid var(--jbnu-burgundy);
        padding-left: 0.72rem !important;
        margin-top: 1.8rem !important;
    }

    h3 {
        color: var(--jbnu-blue) !important;
        font-weight: 700 !important;
    }

    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: var(--text-sub) !important;
    }

    [data-testid="stSidebar"] {
        background-color: #f2f5f9 !important;
        border-right: 1px solid var(--border);
    }

    /* ========================================================
       사이드바 메뉴 - 탭형(모던)
       ======================================================== */

    /* 사이드바 일반 텍스트 */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] li {
        color: var(--text-main) !important;
    }

    /* 사이드바 상단 브랜드 제목 */
    [data-testid="stSidebar"] .jbnu-sidebar-title {
        color: #004386 !important;
        font-weight: 800 !important;
    }

    /* '메뉴' 섹션 헤더 */
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        background: transparent !important;
        border: none !important;
        padding: 0.2rem 0 0.45rem 0.15rem !important;
        margin: 0.2rem 0 0.35rem 0 !important;
        box-shadow: none !important;
    }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        color: #004386 !important;
        font-weight: 800 !important;
        font-size: 0.86rem !important;
        letter-spacing: 0.04em;
        margin: 0 !important;
    }

    /* 탭 그룹 */
    [data-testid="stSidebar"] div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 0.18rem;
        border-left: 2px solid #cbd5e1;
        padding-left: 0.5rem;
        margin-top: 0.15rem;
    }

    /* 기본 탭 */
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        position: relative;
        display: flex !important;
        align-items: center !important;
        width: 100%;
        min-height: 2.9rem;
        padding: 0.62rem 0.78rem !important;
        margin: 0 !important;

        background: transparent !important;
        border: none !important;
        border-radius: 8px !important;
        box-shadow: none !important;

        transition:
            background-color 0.16s ease,
            color 0.16s ease,
            transform 0.16s ease;
    }

    /* 기본 라디오 원형 숨김 */
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }

    /* 기본 탭 텍스트 */
    [data-testid="stSidebar"] div[role="radiogroup"] label p {
        color: #334155 !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        line-height: 1.25;
        margin: 0 !important;
    }

    /* hover */
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: #eef4fa !important;
        transform: translateX(2px);
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label:hover p {
        color: #004386 !important;
    }

    /* 선택된 탭 */
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(
            90deg,
            rgba(0, 67, 134, 0.10) 0%,
            rgba(0, 67, 134, 0.035) 100%
        ) !important;
        border-radius: 8px !important;
        transform: translateX(2px);
    }

    /* 선택된 탭 왼쪽 버건디 포인트 바 */
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before {
        content: "";
        position: absolute;
        left: -0.62rem;
        top: 0.42rem;
        bottom: 0.42rem;
        width: 4px;
        border-radius: 0 4px 4px 0;
        background: #a6165f;
        box-shadow: 0 0 0 1px rgba(166, 22, 95, 0.08);
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: #004386 !important;
        font-weight: 800 !important;
    }

    [data-testid="stWidgetLabel"] p {
        color: var(--text-main) !important;
        font-weight: 650 !important;
    }

    [data-testid="stCheckbox"] p {
        color: var(--text-main) !important;
    }

    /* 제목 / 초록 / 저자키워드 / 숫자 입력칸: 밝은 회색 배경 */
    [data-testid="stTextArea"] textarea,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        background-color: #f2f3f5 !important;
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
        caret-color: #111111 !important;
        border-radius: 8px !important;
    }

    /* Streamlit/BaseWeb가 입력칸 바깥 div에 어두운 배경을 주는 경우까지 덮어쓰기 */
    [data-testid="stTextArea"] div[data-baseweb="textarea"],
    [data-testid="stTextArea"] div[data-baseweb="textarea"] > div,
    [data-testid="stTextInput"] div[data-baseweb="input"],
    [data-testid="stTextInput"] div[data-baseweb="input"] > div,
    [data-testid="stNumberInput"] div[data-baseweb="input"],
    [data-testid="stNumberInput"] div[data-baseweb="input"] > div {
        background-color: #f2f3f5 !important;
        color: #111111 !important;
        border-color: #cbd3df !important;
        border-radius: 8px !important;
    }

    /* placeholder는 중간 회색 */
    [data-testid="stTextArea"] textarea::placeholder,
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stNumberInput"] input::placeholder {
        color: #6b7280 !important;
        -webkit-text-fill-color: #6b7280 !important;
        opacity: 1 !important;
    }

    /* 브라우저/Streamlit 다크 입력 스타일 강제 해제 */
    [data-testid="stTextArea"] textarea,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        color-scheme: light !important;
    }

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within,
    [data-testid="stNumberInput"] > div:focus-within {
        border-color: var(--jbnu-blue) !important;
        box-shadow: 0 0 0 1px var(--jbnu-blue) !important;
    }

    [data-testid="stNumberInput"] button {
        background-color: #e6e8ec !important;
        color: #111111 !important;
        border-color: #cbd3df !important;
    }

    [data-testid="stNumberInput"] button svg {
        fill: #111111 !important;
        color: #111111 !important;
    }

    [data-testid="stCheckbox"] label {
        color: var(--text-main) !important;
    }

    .stButton > button {
        background-color: var(--jbnu-blue) !important;
        color: #ffffff !important;
        border: 1px solid var(--jbnu-blue) !important;
        border-radius: 8px !important;
        font-weight: 750 !important;
        min-height: 2.9rem;
        box-shadow: none !important;
    }

    .stButton > button p {
        color: #ffffff !important;
    }

    .stButton > button:hover {
        background-color: var(--jbnu-burgundy) !important;
        border-color: var(--jbnu-burgundy) !important;
        color: #ffffff !important;
    }

    /* 자료실 다운로드 버튼 */
    [data-testid="stDownloadButton"] > button {
        background-color: #ffffff !important;
        color: #004386 !important;
        border: 1px solid #b9cbe0 !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        min-height: 2.7rem;
    }

    [data-testid="stDownloadButton"] > button p {
        color: #004386 !important;
    }

    [data-testid="stDownloadButton"] > button:hover {
        background-color: #eef4fa !important;
        border-color: #004386 !important;
    }

    /* ========================================================
       자료실 - SDG 카드형 디자인
       ======================================================== */
    .sdg-card {
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(15, 23, 42, 0.08);
        background: #ffffff;
        margin-bottom: 0.9rem;
        min-height: 220px;
    }

    .sdg-card-top {
        min-height: 150px;
        padding: 0.9rem 0.9rem 0.75rem 0.9rem;
        color: #ffffff;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .sdg-card-head {
        display: flex;
        align-items: flex-start;
        gap: 0.55rem;
    }

    .sdg-card-number {
        font-size: 2rem;
        line-height: 1;
        font-weight: 850;
        letter-spacing: -0.04em;
        flex: 0 0 auto;
    }

    .sdg-card-title {
        color: #ffffff !important;
        font-size: 0.86rem;
        line-height: 1.25;
        font-weight: 800;
        word-break: keep-all;
        padding-top: 0.05rem;
    }

    .sdg-card-icon {
        font-size: 2.7rem;
        line-height: 1;
        text-align: center;
        margin-top: 0.55rem;
        filter: grayscale(1) brightness(0) invert(1);
    }

    .sdg-card-bottom {
        background: #ffffff;
        padding: 0.65rem;
    }

    .sdg-download-link {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.3rem;
        width: 100%;
        min-height: 2.65rem;
        border-radius: 9px;
        text-decoration: none !important;
        font-size: 0.82rem;
        font-weight: 800;
        transition: all 0.15s ease;
        box-sizing: border-box;
    }

    .sdg-download-link:hover {
        transform: translateY(-1px);
        background: #f8fafc !important;
        text-decoration: none !important;
    }

    .sdg-resource-quote {
        min-height: 220px;
        border-radius: 14px;
        border: 1px solid #d8e4f0;
        background:
            linear-gradient(135deg, rgba(0,67,134,0.06), rgba(166,22,95,0.035)),
            #ffffff;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.4rem 1.2rem;
        text-align: center;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
    }

    .sdg-resource-quote .quote-main {
        color: #004386 !important;
        font-size: 1.05rem;
        line-height: 1.65;
        font-weight: 750;
        word-break: keep-all;
    }

    .sdg-resource-quote .quote-sub {
        color: #6b7280 !important;
        font-size: 0.72rem;
        letter-spacing: 0.16em;
        margin-top: 0.9rem;
    }

    /* ========================================================
       UN SDG 소개 페이지
       ======================================================== */
    .sdg-intro-box {
        background:
            linear-gradient(135deg, rgba(0,67,134,0.07), rgba(166,22,95,0.035)),
            #ffffff;
        border: 1px solid #d8e4f0;
        border-left: 5px solid #004386;
        border-radius: 14px;
        padding: 1.25rem 1.35rem;
        margin: 0.35rem 0 1.45rem 0;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
    }

    .sdg-intro-box .intro-title {
        color: #004386 !important;
        font-size: 1.02rem;
        font-weight: 800;
        margin-bottom: 0.45rem;
    }

    .sdg-intro-box .intro-text {
        color: #253247 !important;
        font-size: 0.95rem;
        line-height: 1.7;
        margin: 0;
    }

    .sdg-goal-card {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(15, 23, 42, 0.08);
        background: #ffffff;
        box-shadow: 0 5px 14px rgba(15, 23, 42, 0.06);
        margin-bottom: 0.7rem;
        min-height: 118px;
    }

    .sdg-goal-card .goal-top {
        color: #ffffff;
        min-height: 82px;
        padding: 0.78rem 0.82rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .sdg-goal-card .goal-head {
        display: flex;
        align-items: flex-start;
        gap: 0.45rem;
    }

    .sdg-goal-card .goal-number {
        color: #ffffff !important;
        font-size: 1.45rem;
        line-height: 1;
        font-weight: 850;
        flex: 0 0 auto;
    }

    .sdg-goal-card .goal-title {
        color: #ffffff !important;
        font-size: 0.79rem;
        line-height: 1.25;
        font-weight: 800;
        word-break: keep-all;
    }

    .sdg-goal-card .goal-icon {
        color: #ffffff !important;
        font-size: 1.65rem;
        line-height: 1;
        text-align: right;
    }

    .sdg-goal-card .goal-bottom {
        color: #4b5563 !important;
        background: #ffffff;
        font-size: 0.69rem;
        font-weight: 700;
        padding: 0.42rem 0.7rem;
        text-align: center;
        letter-spacing: 0.02em;
    }

    .sdg-research-box {
        background: #f7f9fc;
        border: 1px solid #dce5ef;
        border-radius: 12px;
        padding: 1.1rem 1.2rem;
        margin-top: 0.5rem;
    }

    .sdg-research-box p {
        color: #253247 !important;
        line-height: 1.7;
        margin: 0;
    }

    /* ========================================================
       SDG 공식 120x120 이미지 기반 카드
       ======================================================== */
    .sdg-logo-grid-card {
        background: #ffffff;
        border: 1px solid #dce3ec;
        border-radius: 14px;
        padding: 0.8rem 0.65rem;
        margin-bottom: 0.8rem;
        min-height: 175px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        box-shadow: 0 5px 14px rgba(15, 23, 42, 0.05);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .sdg-logo-grid-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 9px 20px rgba(0, 67, 134, 0.09);
    }

    .sdg-logo-grid-card img {
        width: 132px;
        height: 132px;
        object-fit: contain;
        display: block;
    }

    .sdg-logo-grid-card .sdg-logo-missing {
        width: 132px;
        height: 132px;
        border-radius: 10px;
        background: #f3f4f6;
        color: #6b7280 !important;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-weight: 700;
        font-size: 0.78rem;
        padding: 0.5rem;
        box-sizing: border-box;
    }

    .sdg-resource-logo-card {
        background: #ffffff;
        border: 1px solid #dce3ec;
        border-radius: 14px;
        padding: 0.75rem;
        margin-bottom: 0.9rem;
        min-height: 210px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .sdg-resource-logo-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 22px rgba(0, 67, 134, 0.10);
    }

    .sdg-resource-logo-card img {
        width: 136px;
        height: 136px;
        object-fit: contain;
        display: block;
        margin: 0 auto 0.65rem auto;
    }

    .sdg-resource-logo-card .sdg-logo-missing {
        width: 136px;
        height: 136px;
        background: #f3f4f6;
        color: #6b7280 !important;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-weight: 700;
        font-size: 0.78rem;
        margin-bottom: 0.65rem;
    }

    .sdg-resource-logo-card .sdg-download-link {
        width: 100%;
        box-sizing: border-box;
        min-height: 2.6rem;
    }

    @media (max-width: 900px) {
        .sdg-logo-grid-card img,
        .sdg-logo-grid-card .sdg-logo-missing {
            width: 110px;
            height: 110px;
        }

        .sdg-resource-logo-card img,
        .sdg-resource-logo-card .sdg-logo-missing {
            width: 112px;
            height: 112px;
        }
    }

    @media (max-width: 900px) {
        .sdg-card {
            min-height: 200px;
        }

        .sdg-card-top {
            min-height: 135px;
        }
    }

    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid var(--border) !important;
        border-radius: 9px !important;
        overflow: hidden;
    }

    [data-testid="stExpander"] summary {
        background-color: #f8fafc !important;
        color: var(--text-main) !important;
    }

    [data-testid="stExpander"] summary:hover {
        background-color: #eef3f8 !important;
    }

    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] div {
        color: var(--text-main);
    }

    [data-testid="stAlert"] {
        border-radius: 8px !important;
        color: var(--text-main) !important;
    }

    [data-testid="stAlert"] p {
        color: var(--text-main) !important;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        background-color: #ffffff !important;
    }

    code {
        color: #7f1249 !important;
        background-color: #f8eaf1 !important;
        border: 1px solid #edd1df;
        border-radius: 5px;
        padding: 0.08rem 0.3rem;
    }

    a {
        color: var(--jbnu-blue) !important;
    }

    a:hover {
        color: var(--jbnu-burgundy) !important;
    }

    hr {
        border-color: #dfe5ed !important;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 1.3rem;
        }

        h1 {
            font-size: 1.8rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)



query_dir = "queries"

# ============================================================
# 좌측 메뉴
# 최초 접속 시 기존 분석 화면이 보이도록 index=1 설정
# ============================================================

sidebar_logo_uri = get_logo_data_uri("logo.png")

if sidebar_logo_uri:
    st.sidebar.markdown(
        f"""
        <div style="
            display:flex;
            align-items:center;
            gap:0.45rem;
            margin-bottom:0.65rem;
            white-space:nowrap;
        ">
            <img src="{sidebar_logo_uri}" alt="전북대학교 로고"
                 style="width:28px; height:28px; object-fit:contain; flex:0 0 auto;">
            <span class="jbnu-sidebar-title" style="
                font-size:0.98rem;
                font-weight:800;
                line-height:1;
                white-space:nowrap;
            ">JBNU 연구성과 SDGs 매칭 시스템</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        """
        <div class="jbnu-sidebar-title" style="
            font-size:0.98rem;
            font-weight:800;
            margin-bottom:0.65rem;
            white-space:nowrap;
        ">
            JBNU 연구성과 SDGs 매칭 시스템
        </div>
        """,
        unsafe_allow_html=True,
    )

menu = st.sidebar.radio(
    "메뉴",
    [
        "UN SDG란?",
        "연구성과 SDG 매칭 시스템",
        "시스템 이용방법",
        "자료실",
    ],
    index=1,
)


# ============================================================
# 1) UN SDG란?
# ============================================================

if menu == "UN SDG란?":
    st.title("🌍 UN SDG란?")

    st.subheader("1. UN 지속가능발전목표(SDGs)")
    st.markdown(
        """
        <div class="sdg-intro-box">
            <div class="intro-title">Sustainable Development Goals</div>
            <p class="intro-text">
                지속가능발전목표(Sustainable Development Goals, SDGs)는
                2015년 UN 회원국이 채택한 「2030 지속가능발전 의제」의 핵심 목표입니다.
                2030년까지 국제사회가 공동으로 해결해야 할 빈곤, 보건, 교육, 에너지,
                불평등, 기후변화 등 사회·경제·환경 분야의 17개 목표로 구성됩니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    def render_intro_goal(sdg: int):
        logo_uri = get_sdg_logo_data_uri(sdg)

        if logo_uri:
            logo_html = (
                f'<img src="{logo_uri}" '
                f'alt="SDG {sdg} {SDG_NAMES[sdg]}">'
            )
        else:
            logo_html = (
                f'<div class="sdg-logo-missing">'
                f'logo-{sdg}_120x120_png.png<br>파일 없음'
                f'</div>'
            )

        st.markdown(
            f'<div class="sdg-logo-grid-card">{logo_html}</div>',
            unsafe_allow_html=True,
        )

    # 1~16: 4열
    for row_start in range(1, 17, 4):
        cols = st.columns(4, gap="small")
        for col, sdg in zip(cols, range(row_start, min(row_start + 4, 17))):
            with col:
                render_intro_goal(sdg)

    # 마지막 행: SDG 17 + 설명
    last_row = st.columns([1, 3], gap="small")

    with last_row[0]:
        render_intro_goal(17)


    st.subheader("2. 대학과 SDG 연구")
    st.markdown(
        """
        <div class="sdg-research-box">
            <p>
                대학의 연구성과는 보건, 에너지, 불평등, 기후변화 등
                다양한 지속가능발전 의제와 연결됩니다.
                Elsevier/SCOPUS는 논문의 제목·초록·키워드 등을
                바탕으로 각 연구성과를 SDG별로 분류합니다.
                이때, 17개 SDGs는 서로 유기적으로 연결되어 있어, 하나의 연구성과가 동시에 여러 SDG로 분류될 수 있습니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "이 시스템은 연구자의 논문이 어떤 SDG로 분류될 수 있는지 사전에 점검할 수 있도록 지원하는 도구입니다."
    )


# ============================================================
# 2) 연구성과 SDG 매칭 시스템
# ============================================================

elif menu == "연구성과 SDG 매칭 시스템":
    logo_uri = get_logo_data_uri("logo.png")

    if logo_uri:
        st.markdown(
            f"""
            <h1 class="jbnu-main-title">
                <img src="{logo_uri}" alt="전북대학교 로고">
                <span>JBNU 연구성과 지속가능발전목표(SDGs) 매칭 시스템</span>
            </h1>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.title("JBNU 연구성과 지속가능발전목표(SDGs) 매칭 시스템")
        st.caption("※ logo.png 파일을 app.py와 같은 폴더에 두면 제목 왼쪽에 전북대학교 로고가 표시됩니다.")
    st.caption(
        "논문 제목·초록·저자키워드를 입력하여 SDG 관련 연구성과로 집계될 수 있는지 점검해보세요."
    )

    # --------------------------------------------------------
    # 1. 논문 정보 입력
    # --------------------------------------------------------

    st.subheader("1. 논문 정보 입력")

    title = st.text_area(
        "논문 제목",
        height=90,
        placeholder="예: Income inequality and poverty in developing countries",
    )

    abstract = st.text_area(
        "초록",
        height=230,
        placeholder="논문 초록을 붙여넣으세요.",
    )

    keyword_count = st.number_input(
        "저자키워드 개수",
        min_value=0,
        max_value=20,
        value=3,
        step=1,
    )

    keyword_list = []
    for i in range(int(keyword_count)):
        keyword = st.text_input(
            f"저자키워드 {i + 1}",
            key=f"author_keyword_{i}",
            placeholder=f"키워드 {i + 1} 입력",
        )
        keyword_list.append(keyword.strip())

    keywords_text = "; ".join(keyword for keyword in keyword_list if keyword)

    is_agri = st.checkbox(
        "농업 관련 학문분야(AGRI)에 해당",
        help=(
            "논문의 SCOPUS 학문분야가 "
            "AGRI(Agricultural and Biological Sciences)에 해당하면 체크하세요."
        ),
    )

    analyze = st.button(
        "분석 시작",
        type="primary",
        use_container_width=True,
    )

    if analyze:
        if not any([title.strip(), abstract.strip(), keywords_text]):
            st.warning("제목, 초록, 저자키워드 중 하나 이상을 입력해 주세요.")
            st.stop()

        paper = Paper(
            title=title.strip() or None,
            abstract=abstract.strip() or None,
            keywords=keywords_text or None,
            subject_area="AGRI" if is_agri else "OTHER",
        )

        with st.spinner("SDG 해당 여부를 확인 중입니다..."):
            results = run_all_sdgs(paper, query_dir)

        # ----------------------------------------------------
        # 2. 분석 결과
        # ----------------------------------------------------

        st.subheader("2. 분석 결과")

        summary_rows = []
        for sdg in range(1, 17):
            item = results[sdg]
            result = item["result"]

            if item["error"]:
                summary_rows.append(
                    {
                        "SDG": f"SDG {sdg}",
                        "목표": SDG_NAMES[sdg],
                        "판정": "오류",
                        "근거 수": 0,
                    }
                )
            else:
                summary_rows.append(
                    {
                        "SDG": f"SDG {sdg}",
                        "목표": SDG_NAMES[sdg],
                        "판정": f"{STATUS_ICON[result.truth]} {STATUS_LABEL[result.truth]}",
                        "근거 수": len(result.spans),
                    }
                )

        df_summary = pd.DataFrame(summary_rows)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

        true_sdgs = [
            sdg
            for sdg, item in results.items()
            if item["result"] is not None
            and item["result"].truth is Truth.TRUE
        ]

        unknown_sdgs = [
            sdg
            for sdg, item in results.items()
            if item["result"] is not None
            and item["result"].truth is Truth.UNKNOWN
        ]

        if true_sdgs:
            st.success(
                "검색조건 충족: "
                + ", ".join(f"SDG {sdg}" for sdg in true_sdgs)
            )
        else:
            st.info("현재 입력 기준으로 검색조건을 충족한 SDG가 없습니다.")

        if unknown_sdgs:
            st.warning(
                "일부 입력정보가 없어 판정이 보류된 SDG: "
                + ", ".join(f"SDG {sdg}" for sdg in unknown_sdgs)
            )

        # ----------------------------------------------------
        # 3. SDG별 연구성과 포착 근거
        # ----------------------------------------------------

        st.subheader("3. SDG별 연구성과 포착 근거")

        for sdg in range(1, 17):
            item = results[sdg]
            result = item["result"]

            if item["error"]:
                label = f"SDG {sdg}. {SDG_NAMES[sdg]} — 오류"
            else:
                label = (
                    f"SDG {sdg}. {SDG_NAMES[sdg]} — "
                    f"{STATUS_ICON[result.truth]} {STATUS_LABEL[result.truth]}"
                )

            with st.expander(
                label,
                expanded=(result is not None and result.truth is Truth.TRUE),
            ):
                if item["error"]:
                    st.error(item["error"])
                    continue

                st.write(f"**판정 결과:** {STATUS_LABEL[result.truth]}")

                notes = compact_notes(result.notes)
                if notes:
                    st.write("**판정 참고사항**")
                    for note in notes:
                        st.write(f"- {note}")

                if result.spans:
                    st.write("**판정근거**")

                    evidence = []
                    seen = set()

                    for span in result.spans:
                        key = (
                            span.field,
                            span.query,
                            span.matched_text,
                        )
                        if key in seen:
                            continue
                        seen.add(key)

                        evidence.append(
                            {
                                "위치": FIELD_LABELS.get(span.field, span.field),
                                "검색식 조건": span.query,
                                "논문 내 일치 표현": span.matched_text,
                            }
                        )

                        if len(evidence) >= 50:
                            break

                    st.dataframe(
                        pd.DataFrame(evidence),
                        use_container_width=True,
                        hide_index=True,
                    )

                    if len(result.spans) > 50:
                        st.caption(
                            f"근거가 많아 처음 50개만 표시했습니다. "
                            f"전체 근거 수: {len(result.spans)}"
                        )
                else:
                    if result.truth is Truth.FALSE:
                        st.caption(
                            "현재 입력에서 최종 TRUE로 연결되는 "
                            "검색조건이 발견되지 않았습니다."
                        )
                    elif result.truth is Truth.UNKNOWN:
                        st.caption(
                            "입력되지 않은 필드가 있어 "
                            "최종 판정을 확정할 수 없습니다."
                        )

        # ----------------------------------------------------
        # 4. SDG 포착 가이드라인
        # ----------------------------------------------------

        st.subheader("4. SDG 포착 가이드라인")
        st.caption(
            "현재 포착되지 않은 SDG 중, 입력 정보와 가장 가까운 "
            "경로를 최대 3개까지 보여줍니다. 이를 통해 어떤 검색조건이 충족되지 "
            "않았는지 확인할 수 있습니다."
        )

        guide_found = False

        for sdg in range(1, 17):
            item = results[sdg]
            result = item["result"]

            if item["error"] or result is None:
                continue

            # 이미 해당되는 SDG는 포착 가이드에서 제외
            if result.truth is Truth.TRUE:
                continue

            query_path = Path(query_dir) / f"SDG{sdg:02d}.txt"

            try:
                guide_plans = guide_query_file(
                    query_path,
                    paper,
                    top_k=5,
                )
            except Exception:
                continue

            # 현재 논문과 하나 이상의 조건이 실제로 겹치는 경우만 표시
            relevant_plans = [
                plan
                for plan in guide_plans
                if plan.matched_count > 0
            ][:3]

            if not relevant_plans:
                continue

            guide_found = True

            with st.expander(
                f"SDG {sdg}. {SDG_NAMES[sdg]} — 가까운 검색조건 보기"
            ):
                for idx, plan in enumerate(relevant_plans, start=1):
                    # 검색식의 *, ?, { }, W/n 등을 Markdown 문법으로
                    # 해석하지 않도록 inline code 형식으로 출력
                    st.markdown(f"**{idx}.** `{plan.label}`")

                    satisfied_n = sum(
                        1
                        for guide_item in plan.items
                        if guide_item.status == "충족"
                    )

                    unresolved_n = sum(
                        1
                        for guide_item in plan.items
                        if guide_item.status != "충족"
                    )

                    st.caption(
                        f"현재 충족 {satisfied_n}개 · "
                        f"확인/미충족 조건 {unresolved_n}개"
                    )

                    guide_rows = []
                    for guide_item in plan.items:
                        guide_rows.append(
                            {
                                "상태": (
                                    f"{GUIDE_STATUS_ICON.get(guide_item.status, '')} "
                                    f"{guide_item.status}"
                                ).strip(),
                                "검색조건": guide_item.query,
                                "요구 위치": guide_item.field,
                                "현재 확인": guide_item.matched_text or "-",
                                "설명": guide_item.message,
                            }
                        )

                    st.dataframe(
                        pd.DataFrame(guide_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

                    missing_items = [
                        guide_item
                        for guide_item in plan.items
                        if guide_item.status != "충족"
                    ]

                    if len(missing_items) == 1:
                        missing = missing_items[0]
                        st.info(
                            "이 검색경로에서는 "
                            f"`{missing.query}` "
                            "조건이 충족되지 않아 현재 포착되지 않습니다."
                        )

                    st.divider()

        if not guide_found:
            st.info(
                "현재 입력과 부분적으로 일치하는 "
                "미포착 SDG 검색경로가 없습니다."
            )

        st.caption(
            "※ 본 도구는 원본 Boolean 검색식 기반의 사전 진단 도구입니다. "
            "실제 SCOPUS 색인·언어처리 및 최종 SDG 분류 결과와 "
            "차이가 있을 수 있습니다."
        )


# ============================================================
# 3) 시스템 이용방법
# ============================================================

elif menu == "시스템 이용방법":
    st.title("📘 시스템 이용방법")

    st.subheader("1. 논문 정보 입력")
    st.markdown(
        """
        - [논문 제목]을 입력합니다.
        - [초록]을 입력합니다.
        - 논문에 등록된 [저자키워드 개수]를 선택한 뒤 각 [키워드]를 입력합니다.
        - 논문의 SCOPUS 학문분야가 [AGRI(Agricultural and Biological Sciences)]에 해당하면 체크합니다.
        """
    )
    st.write(
        "입력이 끝나면 [분석 시작] 버튼을 누릅니다. "
        "시스템은 SDG 검색식과 입력한 논문 정보를 대조합니다."
    )

    st.subheader("2. 분석 결과 확인")
    st.markdown(
        """
        - **해당**: 현재 입력정보를 기준으로 SDG 검색조건을 충족한 경우입니다.
        - **미해당**: 현재 입력정보를 기준으로 SDG 검색조건을 충족하지 못한 경우입니다.
        - **판정 보류**: 필요한 입력정보가 없어 판정을 확정하기 어려운 경우입니다.
        """
    )

    st.subheader("3. SDG별 연구성과 포착 근거")
    st.write(
        "해당 SDG를 펼치면 논문의 어느 위치에서 어떤 검색식 조건이 충족되었는지 확인할 수 있습니다."
    )
    st.markdown(
        """
        - **위치**: 제목, 초록, 저자키워드 등 검색조건이 확인된 위치
        - **검색식 조건**: Elsevier/SCOPUS SDG 검색식에서 요구하는 표현 또는 조건
        - **논문 내 일치 표현**: 입력한 논문에서 실제로 검색식 조건과 일치한 표현
        """
    )

    st.subheader("4. SDG 포착 가이드라인")
    st.write(
        "현재 포착되지 않은 SDG 가운데 논문과 일부 검색조건이 일치하는 경우, "
        "가장 가까운 검색경로를 최대 3개까지 보여줍니다. "
        "이를 통해 어떤 조건이 충족되었고 어떤 조건이 충족되지 않았는지 확인할 수 있습니다."
    )

    st.warning(
        "포착 가이드라인은 실제 연구내용과 관련 없는 특정 단어를 논문에 임의로 추가하도록 권고하는 기능이 아닙니다. "
        "연구내용에 부합하는 범위 내에서 SDG 연계성을 제고하기 위한 참고자료로 활용하여 주시기 바랍니다."
    )

    st.subheader("5. 이용 시 유의사항")
    st.write(
        "본 시스템은 원본 Boolean 검색식을 활용한 사전 진단 도구입니다. "
        "실제 SCOPUS의 색인정보, 추가 메타데이터, 언어처리 및 최종 분류 방식에 따라 "
        "실제 SDG 분류 결과와 차이가 발생할 수 있습니다."
    )


# ============================================================
# 4) 자료실
# ============================================================

elif menu == "자료실":
    st.title("📁 SDG 검색식 자료실")
    st.write(
        "17개 UN 지속가능발전목표별 Elsevier/SCOPUS Boolean 검색식 원문을 확인하고 "
        "각 파일을 내려받을 수 있습니다."
    )
    st.caption(
        "※ 본 자료는 연구성과 SDG 분류 원리를 이해하고 검색식을 확인하기 위한 참고자료입니다."
    )

    def render_sdg_resource_card(sdg: int):
        query_path = Path(query_dir) / f"SDG{sdg:02d}.txt"
        logo_uri = get_sdg_logo_data_uri(sdg)

        if logo_uri:
            logo_html = (
                f'<img src="{logo_uri}" '
                f'alt="SDG {sdg} {SDG_NAMES[sdg]}">'
            )
        else:
            logo_html = (
                f'<div class="sdg-logo-missing">'
                f'logo-{sdg}_120x120_png.png<br>파일 없음'
                f'</div>'
            )

        if query_path.exists():
            encoded = base64.b64encode(query_path.read_bytes()).decode("utf-8")
            download_html = (
                f'<a class="sdg-download-link" '
                f'href="data:text/plain;base64,{encoded}" '
                f'download="SDG{sdg:02d}.txt" '
                f'style="color:#004386 !important; '
                f'border:1px solid #9eb9d6; background:#ffffff;">'
                f'↓ SDG {sdg}.txt 다운로드'
                f'</a>'
            )
        else:
            download_html = (
                '<div class="sdg-download-link" '
                'style="color:#9ca3af !important; '
                'border:1px solid #d1d5db; background:#ffffff;">'
                '검색식 파일 없음'
                '</div>'
            )

        card_html = (
            f'<div class="sdg-resource-logo-card">'
            f'{logo_html}'
            f'{download_html}'
            f'</div>'
        )

        st.markdown(card_html, unsafe_allow_html=True)

    st.subheader("17개 지속가능발전목표")

    # 1~5
    row1 = st.columns(5, gap="small")
    for col, sdg in zip(row1, range(1, 6)):
        with col:
            render_sdg_resource_card(sdg)

    # 6~10
    row2 = st.columns(5, gap="small")
    for col, sdg in zip(row2, range(6, 11)):
        with col:
            render_sdg_resource_card(sdg)

    # 11~15
    row3 = st.columns(5, gap="small")
    for col, sdg in zip(row3, range(11, 16)):
        with col:
            render_sdg_resource_card(sdg)

    # 16~17 + 메시지
    row4 = st.columns([1, 1, 3], gap="small")

    with row4[0]:
        render_sdg_resource_card(16)

    with row4[1]:
        render_sdg_resource_card(17)


