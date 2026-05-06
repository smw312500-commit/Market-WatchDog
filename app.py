# -*- coding: utf-8 -*-
import os
import sqlite3
from pathlib import Path
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
from functools import wraps
from crawler import get_multiple_keywords_news
from security.seed_manager import (
    init_tables, ensure_default_seed, log_access, get_active_seed,
    register_seed, get_logs, get_seed_history, get_table,
)
from security.cipher import encrypt
from security.auth import get_current_user, login as auth_login

PROJECT_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except ModuleNotFoundError:
    pass

# .env 직접 파싱 (dotenv 실패 시 fallback)
_env_file = PROJECT_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            if not os.environ.get(_k.strip()):
                os.environ[_k.strip()] = _v.strip()


def resolve_path(env_name: str, default: Path) -> Path:
    raw = os.getenv(env_name)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "mwd-secret-2026-change-in-prod")

# 관리자 계정 (환경변수 우선)
ADMIN_ID  = os.getenv("ADMIN_ID",  "admin")
ADMIN_PW  = os.getenv("ADMIN_PW",  "admin1234")

# 보안 테이블 + 기본 seed 초기화
init_tables()
ensure_default_seed()


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def api_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({'error': '관리자 로그인 필요'}), 403
        return f(*args, **kwargs)
    return wrapper

MARKET_DB = resolve_path("MARKET_DB", PROJECT_ROOT / "market_watchdog.db")
MODEL_OUTPUT  = resolve_path("MODEL_OUTPUT",  PROJECT_ROOT / "model_output.json")
AI_SUMMARY    = resolve_path("AI_SUMMARY",    PROJECT_ROOT / "ai_summary.json")
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", os.getenv("PORT", "5000")))
FLASK_DEBUG = env_flag("FLASK_DEBUG")

PROJECT_NAME = "Market WatchDog"


# =========================================================
# 시장 데이터 DB 유틸
# =========================================================
def query_db(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(str(MARKET_DB))
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('is_admin'):
        return redirect(url_for('admin'))
    error = None
    if request.method == 'POST':
        uid = (request.form.get('user_id') or '').strip()
        pw  = (request.form.get('password') or '').strip()
        if uid == ADMIN_ID and pw == ADMIN_PW:
            session['is_admin'] = True
            session['user_id']  = uid
            return redirect(url_for('admin'))
        error = '아이디 또는 비밀번호가 틀렸습니다.'
    return render_template('login.html', project_name=PROJECT_NAME, error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', project_name=PROJECT_NAME)

@app.route('/demo')
def demo():
    return render_template('demo.html', project_name=PROJECT_NAME)


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
# API - 인증
# =========================================================
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    body     = request.get_json(silent=True) or {}
    user_id  = (body.get('user_id') or '').strip()
    password = (body.get('password') or '').strip()
    token    = auth_login(user_id, password)
    if not token:
        return jsonify({'error': '아이디 또는 비밀번호가 틀렸습니다.'}), 401
    return jsonify({'token': token, 'user_id': user_id})


# =========================================================
# API - ML 모델 결과 (공개 — 분석 페이지용)
# =========================================================
@app.route('/api/model/latest')
def api_model_latest():
    import json
    if not MODEL_OUTPUT.exists():
        return jsonify({'error': 'model_output.json not found'}), 404
    with open(MODEL_OUTPUT, encoding='utf-8') as f:
        return jsonify(json.load(f))


# =========================================================
# API - ML 모델 결과 (보안 레이어 — 데모/외부 API용)
# =========================================================
@app.route('/api/secure/model/latest')
def api_secure_model_latest():
    import json
    from datetime import date

    if not MODEL_OUTPUT.exists():
        return jsonify({'error': 'model_output.json not found'}), 404

    with open(MODEL_OUTPUT, encoding='utf-8') as f:
        plain = json.load(f)

    user  = get_current_user()
    seed  = get_active_seed()
    sv    = int(seed['seed_version']) if seed else None
    ip    = request.remote_addr or ''
    ua    = request.headers.get('User-Agent', '')
    path  = request.path

    if user:
        log_access(path, 'NORMAL_ACCESS', 'ORIGINAL_RETURNED',
                   user_id=str(user.get('sub', '')), seed_version=sv,
                   ip_address=ip, user_agent=ua)
        return jsonify({'mode': 'original', 'data': plain})

    table = get_table(date.today())
    if table:
        decoy = encrypt(plain, table)
        log_access(path, 'UNAUTHORIZED', 'DECOY_RETURNED',
                   seed_version=sv, ip_address=ip, user_agent=ua)
        return jsonify({'mode': 'decoy', 'seed_version': sv, 'data': decoy})

    log_access(path, 'UNAUTHORIZED', 'BLOCKED', ip_address=ip, user_agent=ua)
    return jsonify({'error': 'unauthorized'}), 401


# =========================================================
# API - 관리자 (보안)
# =========================================================
@app.route('/api/admin/security-seed', methods=['GET'])
@api_admin_required
def api_seed_current():
    seed = get_active_seed()
    if not seed:
        return jsonify({'error': 'seed 없음'}), 404
    return jsonify({
        'seed_version': seed['seed_version'],
        'seed_phrase':  seed['seed_phrase'],
        'active_from':  seed['active_from'],
        'created_by':   seed['created_by'],
        'is_active':    seed['is_active'],
    })


@app.route('/api/admin/security-seed', methods=['POST'])
@api_admin_required
def api_seed_register():
    body        = request.get_json(silent=True) or {}
    seed_text   = (body.get('seed_phrase') or '').strip()
    created_by  = (body.get('created_by') or 'admin').strip()
    if not seed_text:
        return jsonify({'error': 'seed_phrase 필요'}), 400
    new_seed = register_seed(seed_text, created_by)
    return jsonify({
        'ok': True,
        'seed_version': new_seed['seed_version'] if new_seed else None,
        'message': 'New security seed activated',
    })


@app.route('/api/admin/security-seed/history')
@api_admin_required
def api_seed_history():
    return jsonify(get_seed_history())


@app.route('/api/admin/access-logs')
@api_admin_required
def api_access_logs():
    limit = int(request.args.get('limit', 100))
    return jsonify(get_logs(limit))


@app.route('/api/admin/access-logs/stats')
@api_admin_required
def api_log_stats():
    from security.seed_manager import _conn
    with _conn() as c:
        total   = c.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0]
        decoys  = c.execute("SELECT COUNT(*) FROM access_logs WHERE result_type='DECOY_RETURNED'").fetchone()[0]
        normals = c.execute("SELECT COUNT(*) FROM access_logs WHERE result_type='ORIGINAL_RETURNED'").fetchone()[0]
        by_seed = c.execute("""
            SELECT seed_version, result_type, COUNT(*) as cnt
            FROM access_logs WHERE seed_version IS NOT NULL
            GROUP BY seed_version, result_type
            ORDER BY seed_version DESC
        """).fetchall()
    return jsonify({
        'total': total, 'decoy_returned': decoys, 'original_returned': normals,
        'by_seed_version': [dict(r) for r in by_seed],
    })


# =========================================================
# API - mail_archive 파일 목록 / 내용 / seed 등록
# =========================================================
MAIL_DIR = PROJECT_ROOT / 'mail_archive'

@app.route('/api/admin/mail-files')
@api_admin_required
def api_mail_files():
    files = sorted(f.name for f in MAIL_DIR.glob('*.txt'))
    active = get_active_seed()
    active_text = active['seed_phrase'] if active else ''
    result = []
    for name in files:
        text = (MAIL_DIR / name).read_text(encoding='utf-8')
        result.append({
            'name': name,
            'preview': text[:120].replace('\n', ' '),
            'is_active': text.strip() == active_text.strip(),
        })
    return jsonify(result)


@app.route('/api/admin/mail-files/activate', methods=['POST'])
@api_admin_required
def api_mail_activate():
    body = request.get_json(silent=True) or {}
    name = (body.get('filename') or '').strip()
    path = MAIL_DIR / name
    if not path.exists() or not name.endswith('.txt'):
        return jsonify({'error': '파일 없음'}), 404
    text = path.read_text(encoding='utf-8')
    new_seed = register_seed(text, session.get('user_id', 'admin'))
    return jsonify({
        'ok': True,
        'seed_version': new_seed['seed_version'] if new_seed else None,
        'filename': name,
    })


# =========================================================
# API - AI 시장 해석 (캐시 읽기)
# =========================================================
@app.route('/api/ai/interpret')
def api_ai_interpret():
    import json
    if not AI_SUMMARY.exists():
        return jsonify({'error': '아직 AI 요약이 없습니다.'}), 404
    with open(AI_SUMMARY, encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/ai/summarize', methods=['POST'])
def api_ai_summarize():
    import json
    from datetime import datetime
    try:
        from openai import OpenAI
    except ImportError:
        return jsonify({'error': 'openai 패키지 미설치'}), 503

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'error': 'OPENAI_API_KEY 미설정'}), 503

    if not MODEL_OUTPUT.exists():
        return jsonify({'error': 'model_output.json 없음'}), 404

    with open(MODEL_OUTPUT, encoding='utf-8') as f:
        data = json.load(f)

    def interpret_row(r):
        s = r['anomaly_score']
        z = r['sw_z']
        stress = "매우 안정적" if s < 0.2 else "안정적" if s < 0.4 else "다소 불안" if s < 0.6 else "불안"
        trend  = ("자금이 빠르게 빠지는 중" if z < -2 else
                  "자금이 줄어드는 중"     if z < -1.5 else
                  "자금이 빠르게 몰리는 중" if z > 2 else
                  "자금이 늘어나는 중"     if z > 1.5 else
                  "발행량 평균 수준")
        return f"{r['final_level']} 상태 / {stress} / {trend}"

    def latest(arr): return arr[-1] if arr else {}
    cp   = latest(data['cp'])
    abcp = latest(data['abcp'])
    ab   = latest(data['abstb'])

    situation = (
        f"기준 시점: {data['last_updated']}\n\n"
        f"기업어음:     {interpret_row(cp)}\n"
        f"자산담보어음: {interpret_row(abcp)}\n"
        f"AB단기사채:   {interpret_row(ab)}\n"
    )

    prompt = (
        f"{situation}\n"
        "위 세 가지 단기금융상품 현황을 금융을 전혀 모르는 사람에게 설명해줘.\n"
        "카톡으로 친한 친구한테 설명하듯 자연스럽게, 4~5문장으로.\n"
        "각 상품 상태를 구체적으로 언급하고, "
        "마지막 문장은 지금 전체적으로 어떻게 보면 되는지 결론으로 마무리해줘."
    )

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        summary = response.choices[0].message.content or ''
        result  = {
            'summary':      summary,
            'last_updated': data['last_updated'],
            'generated_at': datetime.now().isoformat(timespec='seconds'),
        }
        with open(AI_SUMMARY, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =========================================================
# API - AI 채팅
# =========================================================
@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    import json
    try:
        from openai import OpenAI
    except ImportError:
        return jsonify({'error': 'openai 패키지 미설치'}), 503

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'error': 'OPENAI_API_KEY 미설정'}), 503

    body = request.get_json(silent=True) or {}
    user_msg = (body.get('message') or '').strip()
    history  = body.get('history') or []

    if not user_msg:
        return jsonify({'error': '메시지가 없습니다.'}), 400

    context = ''
    if MODEL_OUTPUT.exists():
        with open(MODEL_OUTPUT, encoding='utf-8') as f:
            data = json.load(f)
        def last_n(arr, n=6):
            return arr[-n:] if len(arr) >= n else arr
        def fmt(arr):
            return '\n'.join(
                f"  {r['YYYYMM']}: 레벨={r['final_level']}, "
                f"스트레스={r['anomaly_score']:.3f}, 추세이탈={r['sw_z']:+.2f}({r['sw_signal']})"
                for r in arr
            )
        context = (
            f"[현재 시장 데이터 — {data['last_updated']} 기준]\n"
            f"CP: {fmt(last_n(data['cp']))}\n"
            f"ABCP: {fmt(last_n(data['abcp']))}\n"
            f"AB단기사채: {fmt(last_n(data['abstb']))}\n"
        )

    system_prompt = (
        "너는 한국 단기채권 시장 모니터링 시스템의 AI 도우미야.\n"
        "사용자는 금융 지식이 거의 없는 초보자야.\n"
        "항상 쉬운 말로, 친근하게 대화해. 전문 용어는 꼭 써야 할 때만 쓰고 바로 쉽게 풀어줘.\n"
        "답변은 3~5문장 이내로 짧고 명확하게.\n\n"
        + context
    )

    messages = [{'role': 'system', 'content': system_prompt}]
    for h in history[-10:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': user_msg})

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=500,
            messages=messages,
        )
        reply = response.choices[0].message.content or ''
        return jsonify({'reply': reply})
    except Exception as e:
        print(f"[AI Chat Error] {type(e).__name__}: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print(f"[{PROJECT_NAME}] 서버 가동 중...")
    app.run(host=FLASK_HOST, debug=FLASK_DEBUG, port=FLASK_PORT)
