# -*- coding: utf-8 -*-
import os
import re
import sqlite3
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from crawler import get_multiple_keywords_news
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

basedir   = os.path.abspath(os.path.dirname(__file__))
MARKET_DB = os.path.join(basedir, 'market_watchdog.db')
MSI_ROOT  = Path(os.getenv("MSI_ROOT", r"E:\PROJECT\Market-WatchDog\master set\msi"))

PROJECT_NAME = "Market WatchDog"


# =========================================================
# 시장 데이터 DB 유틸
# =========================================================
def query_db(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(MARKET_DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def build_range_clause(from_ym, to_ym):
    conditions, params = [], []
    if from_ym:
        conditions.append("yyyymm >= ?")
        params.append(int(from_ym))
    if to_ym:
        conditions.append("yyyymm <= ?")
        params.append(int(to_ym))
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


# =========================================================
# MSI DB 유틸 (최신 월 자동 탐색)
# =========================================================
def find_latest_msi_db() -> str:
    pattern = re.compile(r"(\d{2})년\s*(\d{1,2})월")
    candidates = []
    for d in MSI_ROOT.iterdir():
        if not d.is_dir():
            continue
        m = pattern.fullmatch(d.name.strip())
        if m:
            yyyymm = int(f"20{m.group(1)}{int(m.group(2)):02d}")
            dbs = list(d.glob("*.sqlite"))
            if dbs:
                candidates.append((yyyymm, dbs[0]))
    if not candidates:
        raise FileNotFoundError(f"MSI sqlite 없음: {MSI_ROOT}")
    return str(max(candidates, key=lambda x: x[0])[1])


def query_msi(sql, params=()):
    db_path = find_latest_msi_db()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# =========================================================
# 페이지 라우트
# =========================================================
@app.route('/')
def index():
    return render_template('index.html', project_name=PROJECT_NAME)

@app.route('/indicators')
def indicators():
    return render_template('indicators.html', project_name=PROJECT_NAME)

@app.route('/analysis')
def analysis():
    return render_template('analysis.html', project_name=PROJECT_NAME)


# =========================================================
# API - 뉴스
# =========================================================
SLOT_KEYWORDS = {
    "slot1": ["CP", "ABCP", "기업어음", "단기사채", "직접금융", "채권발행"],
    "slot2": ["단기자금", "유동성", "콜금리", "CP금리", "MMF", "RP"],
    "slot3": ["신용위험", "부도", "PF", "PF리스크", "시스템리스크", "신용등급"],
}

@app.route('/api/infomax_news')
def api_infomax_news():
    result = {}
    for slot, keywords in SLOT_KEYWORDS.items():
        result[slot] = get_multiple_keywords_news(keywords)
    return jsonify({"status": "success", **result})


# =========================================================
# API - CP
# =========================================================
@app.route('/api/cp/balance')
def api_cp_balance():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, balance_amt FROM cp_balance {w} ORDER BY yyyymm", p))

@app.route('/api/cp/issue')
def api_cp_issue():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, issue_amt FROM cp_issue {w} ORDER BY yyyymm", p))

@app.route('/api/cp/tenor')
def api_cp_tenor():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, ultra, short, mid, main, long, xlong FROM cp_tenor {w} ORDER BY yyyymm", p))

@app.route('/api/cp/grade/iss')
def api_cp_grade_iss():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, top, high, mid, low, dist, a1, a2, a2p, a2m, a3, a3p, a3m, b, bp, bm, c, other FROM cp_grade_iss {w} ORDER BY yyyymm", p))

@app.route('/api/cp/grade/bal')
def api_cp_grade_bal():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, top, highmid, low, dist FROM cp_grade_bal {w} ORDER BY yyyymm", p))


# =========================================================
# API - ABCP
# =========================================================
@app.route('/api/abcp/balance')
def api_abcp_balance():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, balance_amt FROM abcp_balance {w} ORDER BY yyyymm", p))

@app.route('/api/abcp/issue')
def api_abcp_issue():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, issue_amt FROM abcp_issue {w} ORDER BY yyyymm", p))

@app.route('/api/abcp/tenor')
def api_abcp_tenor():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, ultra, short, mid, main, long, xlong FROM abcp_tenor {w} ORDER BY yyyymm", p))

@app.route('/api/abcp/grade/iss')
def api_abcp_grade_iss():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, top, high, mid, low, dist, a1, a2, a2p, a2m, a3, a3p, a3m, bp, c, d FROM abcp_grade_iss {w} ORDER BY yyyymm", p))

@app.route('/api/abcp/grade/bal')
def api_abcp_grade_bal():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, top, highmid, low, dist FROM abcp_grade_bal {w} ORDER BY yyyymm", p))


# =========================================================
# API - AB단기사채
# =========================================================
@app.route('/api/ab/balance')
def api_ab_balance():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, balance_amt FROM ab_balance {w} ORDER BY yyyymm", p))

@app.route('/api/ab/issue')
def api_ab_issue():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, issue_amt FROM ab_issue {w} ORDER BY yyyymm", p))

@app.route('/api/ab/tenor')
def api_ab_tenor():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, ultra, short, mid, main, long, xlong FROM ab_tenor {w} ORDER BY yyyymm", p))

@app.route('/api/ab/grade/iss')
def api_ab_grade_iss():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, top, high, mid, low, dist, a1, a2, a2p, a2m, a3, a3p, a3m, b, bp, bm, c, d FROM ab_grade_iss {w} ORDER BY yyyymm", p))

@app.route('/api/ab/grade/bal')
def api_ab_grade_bal():
    w, p = build_range_clause(request.args.get('from'), request.args.get('to'))
    return jsonify(query_db(f"SELECT yyyymm, top, highmid, low, dist FROM ab_grade_bal {w} ORDER BY yyyymm", p))


# =========================================================
# API - 공통
# =========================================================
@app.route('/api/latest')
def api_latest():
    return jsonify(query_db("SELECT MAX(yyyymm) as latest FROM cp_balance")[0])


# =========================================================
# API - MSI
# =========================================================
@app.route('/api/msi/latest')
def api_msi_latest():
    def safe(v):
        try: return float(v)
        except: return 0.0

    rows = query_msi("SELECT * FROM msi_v562_monthly ORDER BY YYYYMM")

    latest_row = rows[-1]
    latest = {
        'yyyymm':     int(latest_row['YYYYMM']),
        'msi':        round(safe(latest_row['MSI_total_v562']),    3),
        'precursor':  round(safe(latest_row['MSI_precursor_v562']),3),
        'trend':      round(safe(latest_row['MSI_trend_v562']),    3),
        'status':     latest_row['MSI_v562_상태']           or '-',
        'pre_status': latest_row['MSI_precursor_v562_상태'] or '-',
        'tr_status':  latest_row['MSI_trend_v562_상태']     or '-',
        'balance':    round(safe(latest_row['balance_core']),3),
        'credit':     round(safe(latest_row['credit_core']), 3),
        'tenor':      round(safe(latest_row['tenor_core']),  3),
    }

    chart_all = [{'YYYYMM':             r['YYYYMM'],
                  'MSI_total_v562':     safe(r['MSI_total_v562']),
                  'MSI_precursor_v562': safe(r['MSI_precursor_v562']),
                  'MSI_v562_상태':      r['MSI_v562_상태'],
                  'balance_core':       safe(r['balance_core']),
                  'credit_core':        safe(r['credit_core']),
                  'tenor_core':         safe(r['tenor_core'])} for r in rows]

    events_meta = {
        '코로나':         {'yyyymm':202003,'type':'발행자 과잉공급','color':'#94a3b8'},
        '레고랜드':       {'yyyymm':202210,'type':'매수자 이탈',   'color':'#ef4444'},
        '새마을금고':     {'yyyymm':202307,'type':'매수자 이탈',   'color':'#f97316'},
        '태영건설':       {'yyyymm':202312,'type':'매수자 이탈',   'color':'#f59e0b'},
        '암수사건1':      {'yyyymm':201810,'type':'암수 — 경고 후 소멸','color':'#6366f1'},
        '암수사건2':      {'yyyymm':202010,'type':'암수 — 코로나 2차','color':'#8b5cf6'},
    }
    events = {}
    for name, meta in events_meta.items():
        idx_list = [i for i, r in enumerate(rows) if r['YYYYMM'] == meta['yyyymm']]
        if not idx_list:
            continue
        i = idx_list[0]
        peak_row = rows[i]
        window = []
        for j in range(max(0, i-8), min(len(rows)-1, i+4)+1):
            window.append({
                'YYYYMM':          rows[j]['YYYYMM'],
                'T':               j - i,
                'MSI_total_v562':  safe(rows[j]['MSI_total_v562']),
                'MSI_v562_상태':   rows[j]['MSI_v562_상태'],
                'balance_core':    safe(rows[j]['balance_core']),
                'credit_core':     safe(rows[j]['credit_core']),
                'tenor_core':      safe(rows[j]['tenor_core']),
            })
        events[name] = {
            **meta,
            'peak':      round(safe(peak_row['MSI_total_v562']),    3),
            'status':    peak_row['MSI_v562_상태'] or '-',
            'precursor': round(safe(peak_row['MSI_precursor_v562']),3),
            'window':    window,
        }

    recent24 = [{'YYYYMM':             r['YYYYMM'],
                 'MSI_total_v562':     safe(r['MSI_total_v562']),
                 'MSI_precursor_v562': safe(r['MSI_precursor_v562']),
                 'MSI_trend_v562':     safe(r['MSI_trend_v562']),
                 'MSI_v562_상태':      r['MSI_v562_상태'],
                 'balance_core':       safe(r['balance_core']),
                 'credit_core':        safe(r['credit_core']),
                 'tenor_core':         safe(r['tenor_core'])}
                for r in reversed(rows[-24:])]

    return jsonify({'latest': latest, 'chart_all': chart_all,
                    'events': events,  'recent24': recent24})


if __name__ == '__main__':
    print(f"[{PROJECT_NAME}] 서버 가동 중...")
    app.run(debug=True, port=5000)