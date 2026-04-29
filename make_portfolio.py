# -*- coding: utf-8 -*-
"""
Market WatchDog 포트폴리오 소개문 생성기
실행: python make_portfolio.py
출력: Market_WatchDog_Portfolio.docx
"""

from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

doc = Document()

# ── 페이지 여백 설정 ─────────────────────────────────────
section = doc.sections[0]
section.page_width  = Cm(21)
section.page_height = Cm(29.7)
section.top_margin    = Cm(2.2)
section.bottom_margin = Cm(2.2)
section.left_margin   = Cm(2.5)
section.right_margin  = Cm(2.5)

# ── 색상 상수 ────────────────────────────────────────────
COLOR_ACCENT  = RGBColor(0x00, 0xC8, 0x5A)   # 그린 포인트
COLOR_DARK    = RGBColor(0x1A, 0x1A, 0x2E)   # 짙은 네이비
COLOR_GRAY    = RGBColor(0x6B, 0x72, 0x80)   # 서브텍스트
COLOR_DANGER  = RGBColor(0xEF, 0x44, 0x44)   # 위험 빨강
COLOR_BLUE    = RGBColor(0x1D, 0x4E, 0xD8)   # CP 파랑
COLOR_TEAL    = RGBColor(0x0D, 0x94, 0x88)   # ABCP 틸
COLOR_AMBER   = RGBColor(0xB4, 0x53, 0x09)   # AB 앰버


# ── 헬퍼 함수 ────────────────────────────────────────────
def add_heading(text, level=1, color=None):
    p = doc.add_paragraph()
    p.clear()
    run = p.add_run(text)
    run.bold = True
    if level == 1:
        run.font.size = Pt(20)
        run.font.color.rgb = color or COLOR_DARK
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after  = Pt(6)
        # 하단 보더
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '4')
        bottom.set(qn('w:color'), '00C85A')
        pBdr.append(bottom)
        pPr.append(pBdr)
    elif level == 2:
        run.font.size = Pt(14)
        run.font.color.rgb = color or COLOR_DARK
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after  = Pt(4)
    elif level == 3:
        run.font.size = Pt(12)
        run.font.color.rgb = color or COLOR_GRAY
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after  = Pt(2)
    return p


def add_body(text, indent=False, color=None, bold=False, size=10.5):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    if bold:
        run.bold = True
    if indent:
        p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.space_after = Pt(3)
    return p


def add_bullet(text, level=0, color=None):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.size = Pt(10.5)
    if color:
        run.font.color.rgb = color
    p.paragraph_format.left_indent = Cm(0.4 + level * 0.5)
    p.paragraph_format.space_after = Pt(2)
    return p


def add_image_placeholder(label, width_cm=15, height_cm=8):
    """이미지 자리 표시자 — 회색 배경 테이블 1행"""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Cm(width_cm)
    # 배경색 설정
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'E5E7EB')
    tcPr.append(shd)
    # 높이
    tr = tbl.rows[0]._tr
    trPr = tr.get_or_add_trPr()
    trHeight = OxmlElement('w:trHeight')
    trHeight.set(qn('w:val'), str(int(height_cm * 567)))  # 1cm ≒ 567 twips
    trHeight.set(qn('w:hRule'), 'exact')
    trPr.append(trHeight)
    # 텍스트
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"📷  {label}")
    run.font.size = Pt(11)
    run.font.color.rgb = COLOR_GRAY
    run.bold = True
    # 수직 가운데 정렬
    tc_pr = cell._element.find(qn('w:tcPr'))
    if tc_pr is None:
        tc_pr = OxmlElement('w:tcPr')
        cell._element.insert(0, tc_pr)
    vAlign = OxmlElement('w:vAlign')
    vAlign.set(qn('w:val'), 'center')
    tc_pr.append(vAlign)
    doc.add_paragraph()  # 여백
    return tbl


def add_separator():
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(4)


def add_two_col_info(pairs):
    """key: value 형태 2열 테이블"""
    tbl = doc.add_table(rows=len(pairs), cols=2)
    tbl.style = 'Table Grid'
    for i, (k, v) in enumerate(pairs):
        kc = tbl.cell(i, 0)
        vc = tbl.cell(i, 1)
        kp = kc.paragraphs[0]
        vp = vc.paragraphs[0]
        kr = kp.add_run(k)
        kr.bold = True
        kr.font.size = Pt(10)
        kr.font.color.rgb = COLOR_DARK
        vr = vp.add_run(v)
        vr.font.size = Pt(10)
        # 헤더행 배경
        tc = kc._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F3F4F6')
        tcPr.append(shd)
    doc.add_paragraph()


# ════════════════════════════════════════════════════════════
#  1. 표지
# ════════════════════════════════════════════════════════════
p_title = doc.add_paragraph()
p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_title.paragraph_format.space_before = Pt(60)
p_title.paragraph_format.space_after  = Pt(6)
r = p_title.add_run("Market WatchDog")
r.bold = True
r.font.size = Pt(34)
r.font.color.rgb = COLOR_DARK

p_sub = doc.add_paragraph()
p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_sub.paragraph_format.space_after = Pt(4)
r2 = p_sub.add_run("한국 단기금융시장 스트레스 모니터링 대시보드")
r2.font.size = Pt(14)
r2.font.color.rgb = COLOR_GRAY

p_tag = doc.add_paragraph()
p_tag.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_tag.paragraph_format.space_after = Pt(40)
r3 = p_tag.add_run("CP  ·  ABCP  ·  AB단기사채  |  MSI v56.2  |  Flask + SQLite")
r3.font.size = Pt(11)
r3.font.color.rgb = COLOR_ACCENT
r3.bold = True

# 표지 대표 이미지 자리
add_image_placeholder("대시보드 대표 스크린샷 (전체 화면 캡처 권장)", width_cm=15.5, height_cm=9)

p_date = doc.add_paragraph()
p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
p_date.paragraph_format.space_before = Pt(30)
r4 = p_date.add_run("2026.04  |  Portfolio Document")
r4.font.size = Pt(10)
r4.font.color.rgb = COLOR_GRAY

doc.add_page_break()


# ════════════════════════════════════════════════════════════
#  2. 프로젝트 개요
# ════════════════════════════════════════════════════════════
add_heading("1. 프로젝트 개요", 1)

add_body(
    "Market WatchDog은 국내 단기금융시장(CP·ABCP·AB단기사채)의 발행·잔액·신용등급·만기구조 데이터를 "
    "월별로 수집·가공하고, 복합 시장 스트레스 지수(MSI)를 산출해 실시간으로 시각화하는 "
    "Flask 기반 웹 대시보드입니다.",
    size=11
)

add_body(
    "단기금융시장은 유동성 위기의 최전선입니다. 레고랜드 사태(2022.10), 새마을금고 사태(2023.07), "
    "태영건설(2023.12) 등 주요 신용 이벤트가 CP·ABCP 시장에서 먼저 신호를 보낸다는 점에 착안해, "
    "정량적·자동화된 스트레스 탐지 도구를 직접 설계·구현했습니다.",
    size=11
)

add_separator()
add_heading("기본 정보", 2)
add_two_col_info([
    ("프로젝트명",   "Market WatchDog"),
    ("개발 기간",    "2024년 하반기 ~ 2026년 현재 (지속 업데이트)"),
    ("개발 목적",    "단기금융시장 스트레스의 정량적 조기 탐지 및 시각화"),
    ("데이터 범위",  "2016년 ~ 2026년 3월 (월별, CP·ABCP·AB단기사채)"),
    ("기술 스택",    "Python 3.12 / Flask / SQLite / Pandas / NumPy / Chart.js"),
    ("데이터 원천",  "한국예탁결제원(Seibro) 발행·잔액 데이터, 연합인포맥스 뉴스"),
    ("실행 환경",    "로컬 서버 (http://127.0.0.1:5000), Python venv"),
])


# ════════════════════════════════════════════════════════════
#  3. 문제 정의 및 개발 배경
# ════════════════════════════════════════════════════════════
add_heading("2. 문제 정의 및 개발 배경", 1)

add_heading("왜 단기금융시장인가?", 2)
add_bullet("CP(기업어음), ABCP(자산유동화기업어음), AB단기사채는 기업 운전자금 조달의 핵심 채널")
add_bullet("만기가 짧아(주로 1년 이내) 시장 경색 시 롤오버 실패 → 즉각적 유동성 위기로 전이")
add_bullet("레고랜드·새마을금고·태영건설 등 주요 사건에서 CP/ABCP 시장이 선행 신호를 발신")

add_heading("기존 분석의 한계", 2)
add_bullet("시장 데이터가 여러 기관에 분산되어 있어 통합 모니터링 도구 부재")
add_bullet("전문가 주관에 의존하는 정성적 판단 → 실시간·정량화된 경보 체계 필요")
add_bullet("발행액·잔액·신용도·만기 4개 축을 동시에 추적하는 복합 지수 부재")

add_heading("해결 방향", 2)
add_bullet("원천 데이터 자동 전처리 파이프라인 구축 (월 1회 실행으로 전체 갱신)")
add_bullet("잔액 편차(residual) + 신용도 + 만기구조 3축 합산 MSI 설계")
add_bullet("과거 위기 사건을 기준점(anchor)으로 지수를 정규화해 해석 가능성 확보")
add_bullet("Flask 웹 대시보드로 비전문가도 직관적으로 현황을 파악할 수 있도록 시각화")

doc.add_page_break()


# ════════════════════════════════════════════════════════════
#  4. 시스템 아키텍처
# ════════════════════════════════════════════════════════════
add_heading("3. 시스템 아키텍처", 1)

add_image_placeholder("데이터 파이프라인 구조도 (흐름도 또는 다이어그램)", width_cm=15.5, height_cm=7)

add_heading("데이터 파이프라인 (월 1회 실행)", 2)

add_body("① 원천 데이터 수집", bold=True)
add_bullet("발행 데이터: Seibro 크롤러 → CP/ABCP/AB단기사채 월별 CSV (legacy data/)")
add_bullet("잔액 데이터: Seibro 잔액 크롤러 → 신용도별 4버킷 월별 CSV (legacy data2/)")

add_body("② 전처리 자동화 (monthly_preprocess_automation.py)", bold=True)
add_bullet("발행 원천에서 신용등급 정규화(A1/A2/A3/B/C/D), 만기 버킷(ultra~xlong) 분류")
add_bullet("잔액 원천(억원 단위) → 원 환산, 4개 신용버킷(top/high-mid/low/distress) 집계")
add_bullet("이전 월 누적본에 신규 월 데이터를 이어붙여 장기 시계열 CSV 생성")
add_bullet("출력: master set/전처리/{YY년MM월}/ 하위 CP·ABCP·ABSTB 표준 CSV 일체")

add_body("③ DB 적재 (init_db.py)", bold=True)
add_bullet("전처리 CSV → SQLite(market_watchdog.db) 일괄 적재")
add_bullet("테이블: cp_balance, cp_issue, cp_tenor, cp_grade_iss, cp_grade_bal (ABCP·AB 동일 구조)")

add_body("④ MSI 산출 (MSI_v562_sqlite.py)", bold=True)
add_bullet("잔액 residual risk score + 신용도 risk score + 만기 단기 pressure 3축 계산")
add_bullet("레고랜드(202210)를 anchor 1.00으로 후정규화 → 비교 가능한 절대값")
add_bullet("출력: master set/msi/{YY년MM월}/*.sqlite (테이블: msi_v562_monthly)")

add_body("⑤ Flask 서버 (app.py)", bold=True)
add_bullet("market_watchdog.db + 최신 MSI sqlite를 자동 탐색·연결")
add_bullet("REST API 제공 → 브라우저에서 Chart.js로 실시간 시각화")

add_separator()
add_heading("전체 실행 명령 (run_pipeline.py)", 2)
p_code = doc.add_paragraph()
r_code = p_code.add_run("python run_pipeline.py 26년4월")
r_code.font.name = "Courier New"
r_code.font.size = Pt(10)
r_code.font.color.rgb = COLOR_ACCENT
p_code.paragraph_format.left_indent = Cm(0.8)

doc.add_page_break()


# ════════════════════════════════════════════════════════════
#  5. 주요 기능 — HOME
# ════════════════════════════════════════════════════════════
add_heading("4. 주요 기능", 1)

add_heading("4-1. HOME — 시장 뉴스 모니터링", 2)

add_body(
    "연합인포맥스 뉴스를 키워드별로 실시간 크롤링해 3개 카테고리로 분류·표시합니다."
)

add_two_col_info([
    ("슬롯 1 — 직접금융·발행",     "CP, ABCP, 기업어음, 단기사채, 직접금융, 채권발행"),
    ("슬롯 2 — 단기자금·유동성·금리", "단기자금, 유동성, 콜금리, CP금리, MMF, RP"),
    ("슬롯 3 — 신용위험·시스템리스크", "신용위험, 부도, PF, PF리스크, 시스템리스크, 신용등급"),
])

add_image_placeholder("HOME 뉴스 모니터링 화면 스크린샷", width_cm=15.5, height_cm=8)


# ════════════════════════════════════════════════════════════
#  6. 주요 기능 — INDICATORS
# ════════════════════════════════════════════════════════════
add_heading("4-2. INDICATORS — 시계열 지표 대시보드", 2)

add_body(
    "CP·ABCP·AB단기사채 3개 시장의 잔액·발행액·만기구조·신용등급 비중을 "
    "2016년부터 월별 누적 차트로 제공합니다."
)

add_bullet("기간 선택: 전체 / 최근 24·12·6·3개월 / 커스텀 범위(YYYYMM 입력)")
add_bullet("잔액 추이: 시장별 절대 잔액 + 비중 변화 (CP 파랑, ABCP 틸, AB 앰버)")
add_bullet("발행액 추이: 월별 신규 발행금액 시계열")
add_bullet("만기구조: ultra(≤7일) ~ xlong(≥366일) 6개 버킷 스택 차트")
add_bullet("신용등급 비중: top(A1) · high(A2) · mid(A3) · low(B) · distress(C/D) 발행 비중")
add_bullet("잔액 신용도: 4버킷 비중 (top / high-mid / low / distress)")

add_image_placeholder("INDICATORS 지표 대시보드 전체 스크린샷", width_cm=15.5, height_cm=9)

doc.add_page_break()

add_image_placeholder("만기구조 스택 차트 상세 스크린샷", width_cm=7.5, height_cm=6.5)
add_image_placeholder("신용등급 비중 차트 상세 스크린샷", width_cm=7.5, height_cm=6.5)
# (위 두 이미지는 나란히 배치 의도 — 실제 Word에서 2열 표로 교체하거나 텍스트 배치 조정 가능)


# ════════════════════════════════════════════════════════════
#  7. 주요 기능 — ANALYSIS (MSI)
# ════════════════════════════════════════════════════════════
add_heading("4-3. ANALYSIS — 시장 스트레스 지수 (MSI v56.2)", 2)

add_body(
    "잔액 이탈 · 신용도 · 만기구조 3개 축을 합산한 복합 스트레스 지수를 산출하며, "
    "레고랜드 사태(2022.10)를 기준점 1.00으로 정규화합니다."
)

add_image_placeholder("ANALYSIS MSI 대시보드 전체 스크린샷", width_cm=15.5, height_cm=9)

add_heading("MSI 구성 로직", 3)
add_two_col_info([
    ("balance_core",   "CP·ABCP·AB 잔액 비중의 rolling linear residual risk (가중 45%)"),
    ("credit_core",    "CP·AB 발행 신용도 비중의 rolling median residual risk (가중 30%)"),
    ("tenor_core",     "ABCP·AB 단기만기 압력의 rolling residual risk (가중 25%)"),
    ("MSI_precursor",  "0.85 × avg(3축) + 0.15 × max(3축)  — 선행 신호"),
    ("MSI_trend",      "0.80 × avg(3축) + 0.20 × max(3축)  — 추세 신호"),
    ("MSI_total",      "0.70 × precursor + 0.30 × trend + hidden_risk_boost"),
    ("정규화",         "anchor = 레고랜드(202210), target = 1.00"),
])

add_heading("상태 단계 (Status)", 3)
add_two_col_info([
    ("정상",   "MSI < 0.50"),
    ("주의",   "0.50 ≤ MSI < 0.75"),
    ("경고",   "0.75 ≤ MSI < 1.00"),
    ("위험",   "1.00 ≤ MSI < 1.20"),
    ("초위험", "MSI ≥ 1.20"),
])

add_heading("주요 사건 윈도우 분석", 3)
add_body(
    "코로나(2020.03), 레고랜드(2022.10), 새마을금고(2023.07), 태영건설(2023.12) 등 "
    "주요 이벤트 기준 T-8 ~ T+4 구간의 MSI 패턴을 비교 차트로 제공합니다."
)
add_bullet("암수 사건(신호는 떴으나 실현되지 않은 잠재 위험)도 별도 분류·표시")
add_bullet("각 이벤트의 peak MSI, 상태, 3축 분해값 수치 카드로 확인 가능")

add_image_placeholder("사건별 MSI 윈도우 비교 차트 스크린샷", width_cm=15.5, height_cm=8)

doc.add_page_break()


# ════════════════════════════════════════════════════════════
#  8. 기술적 특징
# ════════════════════════════════════════════════════════════
add_heading("5. 기술적 특징 및 구현 포인트", 1)

add_heading("데이터 엔지니어링", 2)
add_bullet("다양한 인코딩(UTF-8-sig / CP949 / EUC-KR) 자동 감지 CSV 로더")
add_bullet("신용등급 정규화: 전각문자·특수기호 포함 원천 → A1/A2+/A2/… 표준 코드")
add_bullet("만기 버킷: ultra(≤7d) / short(8-30d) / mid(31-91d) / main(92-183d) / long(184-365d) / xlong(≥366d)")
add_bullet("월별 incremental append: 이전 누적본 + 신규 1개월 → 중복 제거 후 저장")
add_bullet("잔액 단위 자동 환산: 억원 원천 → 원 단위 (×100,000,000)")

add_heading("MSI 알고리즘 설계", 2)
add_bullet("Rolling linear baseline(24개월 window) vs. Rolling median baseline 혼용")
add_bullet("MAD(중앙절대편차) 기반 정규화 → 극단값에 강인한 z-score 추출")
add_bullet("higher_is_risk / lower_is_risk 플래그로 방향성 명시적 처리")
add_bullet("hidden_risk_boost: precursor ≥ 0.50 이면서 trend ≥ 0.58일 때 +0.04 가산")
add_bullet("anchor 정규화: 레고랜드 raw MSI → scale_factor 산출 → 전 기간 소급 적용")

add_heading("Flask API 설계", 2)
add_bullet("14개 REST 엔드포인트: /api/{cp|abcp|ab}/{balance|issue|tenor|grade/iss|grade/bal}")
add_bullet("?from=YYYYMM&to=YYYYMM 파라미터로 기간 필터링 지원")
add_bullet("/api/msi/latest: 전체 시계열 + 사건 윈도우 + recent24 단일 응답")
add_bullet("MSI DB는 최신 월 폴더를 자동 탐색(find_latest_msi_db) — 경로 변경 불필요")
add_bullet(".env 환경변수로 DB 경로·포트 오버라이드 가능")

add_heading("프론트엔드", 2)
add_bullet("순수 Chart.js 4.x — 별도 프레임워크 없이 11개 이상 차트 렌더링")
add_bullet("기간 선택 버튼 → fetch API → 차트 실시간 갱신 (페이지 리로드 없음)")
add_bullet("MSI 게이지: CSS gradient arc 커스텀 렌더링")
add_bullet("반응형 레이아웃: CSS Grid auto-fill minmax 사용")


# ════════════════════════════════════════════════════════════
#  9. 프로젝트 성과 및 의의
# ════════════════════════════════════════════════════════════
add_heading("6. 프로젝트 성과 및 의의", 1)

add_bullet(
    "정량화된 조기경보: 레고랜드 사태 T-3 이전부터 MSI 경고 구간 진입 확인",
    color=COLOR_DARK
)
add_bullet(
    "재현 가능한 파이프라인: 월 1회 run_pipeline.py 실행으로 전체 데이터 갱신 자동화",
    color=COLOR_DARK
)
add_bullet(
    "10년 시계열 구축: 2016년 ~ 2026년 3월 (약 120개월) CP·ABCP·AB 통합 시계열",
    color=COLOR_DARK
)
add_bullet(
    "사건 유형 분류: 발행자 과잉공급 vs. 매수자 이탈 vs. 암수(잠재 위험) 3가지 패턴 정의",
    color=COLOR_DARK
)
add_bullet(
    "확장 가능 구조: .env 환경변수, SQLite 분리 저장으로 서버 배포 및 경로 변경 용이",
    color=COLOR_DARK
)

add_separator()
add_heading("한계 및 향후 개선 방향", 2)
add_bullet("원천 데이터 수작업 입력 → Seibro API 연동 시 완전 자동화 가능")
add_bullet("로그인/권한 관리(models.py) 미완성 → 다중 사용자 지원 예정")
add_bullet("롤오버 분석(rollover_auto.py) 대시보드 미통합 — 별도 페이지 추가 계획")
add_bullet("CP 만기구조 마스터 데이터 연계 시 tenor_core 정확도 향상 가능")


# ════════════════════════════════════════════════════════════
#  10. 파일 구조
# ════════════════════════════════════════════════════════════
add_heading("7. 주요 파일 구조", 1)

add_two_col_info([
    ("app.py",                           "Flask 서버 · REST API · MSI DB 탐색"),
    ("MSI_v562_sqlite.py",               "시장 스트레스 지수 산출 엔진 (핵심 알고리즘)"),
    ("monthly_preprocess_automation.py", "월별 원천 → 표준 CSV 전처리 자동화"),
    ("init_db.py",                       "전처리 CSV → market_watchdog.db 일괄 적재"),
    ("run_pipeline.py",                  "전체 파이프라인 원커맨드 실행기"),
    ("rollover_auto.py",                 "롤오버 위험 분석 CSV 생성"),
    ("crawler.py",                       "연합인포맥스 뉴스 크롤러"),
    ("Seibro balance crawler.py",        "Seibro 잔액 데이터 Selenium 크롤러"),
    ("Siebro crawler.py",                "Seibro 발행 데이터 Selenium 크롤러"),
    ("templates/index.html",             "HOME — 뉴스 모니터링 페이지"),
    ("templates/indicators.html",        "INDICATORS — 시계열 차트 대시보드"),
    ("templates/analysis.html",          "ANALYSIS — MSI 스트레스 지수 대시보드"),
    ("market_watchdog.db",               "메인 SQLite (CP·ABCP·AB 시계열)"),
    ("master set/msi/",                  "월별 MSI sqlite 저장 폴더"),
])

doc.add_page_break()


# ════════════════════════════════════════════════════════════
#  11. 사진 배치 가이드 (별도 안내 페이지)
# ════════════════════════════════════════════════════════════
add_heading("부록. 스크린샷 배치 가이드", 1)

add_body(
    "아래 회색 박스 위치에 실제 캡처 이미지를 삽입하세요. "
    "Word에서 이미지 선택 후 '텍스트 배치 → 앞으로' 또는 '인라인'으로 설정하면 "
    "박스를 대체할 수 있습니다.",
    size=10, color=COLOR_GRAY
)

add_body("권장 캡처 목록:", bold=True)
add_two_col_info([
    ("①", "대시보드 전체 화면 (표지용) — 브라우저 전체 화면 캡처 권장"),
    ("②", "HOME 뉴스 모니터링 — 3개 슬롯이 모두 채워진 상태"),
    ("③", "INDICATORS 전체 — 잔액·발행·만기·신용 차트 동시 노출"),
    ("④", "INDICATORS 만기구조 차트 상세"),
    ("⑤", "INDICATORS 신용등급 비중 차트 상세"),
    ("⑥", "ANALYSIS MSI 대시보드 전체 — 게이지 + 시계열 + 사건 윈도우"),
    ("⑦", "ANALYSIS 사건별 MSI 윈도우 비교 차트 (레고랜드·코로나 등)"),
    ("⑧", "데이터 파이프라인 구조도 (별도 제작 — draw.io 등 활용 권장)"),
])

add_body(
    "Tip: Chrome 확장 'GoFullPage' 또는 F12 → Ctrl+Shift+P → 'Capture full size screenshot' "
    "를 이용하면 스크롤 없이 전체 페이지를 캡처할 수 있습니다.",
    size=10, color=COLOR_GRAY
)


# ── 저장 ────────────────────────────────────────────────────
out_path = "Market_WatchDog_Portfolio.docx"
doc.save(out_path)
print(f"[완료] {out_path} 저장됨")
