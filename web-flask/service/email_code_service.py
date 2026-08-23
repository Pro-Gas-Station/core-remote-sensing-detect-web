# 邮箱验证码
import random
import threading
from datetime import datetime, timedelta

from config import DEV_MODE, SMS_CODE_TTL, CODE_SEND_COOLDOWN, email_configured
from service.db import get_conn
from service.email_service import send_verification_email


def _now():
    return datetime.now()


def _gen_code():
    return str(random.randint(100000, 999999))


def _cooldown_remain(email, purpose):
    with get_conn() as conn:
        row = conn.execute(
            'SELECT created_at FROM email_codes WHERE email=? AND purpose=? '
            'ORDER BY created_at DESC LIMIT 1',
            (email, purpose),
        ).fetchone()
    if not row:
        return 0
    try:
        created = datetime.fromisoformat(row['created_at'])
    except ValueError:
        return 0
    elapsed = (_now() - created).total_seconds()
    if elapsed < CODE_SEND_COOLDOWN:
        return int(CODE_SEND_COOLDOWN - elapsed) + 1
    return 0


def _dispatch_verification_email(email, code, ttl_min):
    """后台发送邮件，避免阻塞 HTTP 请求。"""
    def worker():
        result = send_verification_email(email, code, ttl_min)
        if result.get('code') != 200:
            print('[EMAIL FAIL]', email, result.get('message'))
            return
        print('[EMAIL OK] 验证码已发送至', email)
        if result.get('dev_mode') or (DEV_MODE and not email_configured()):
            print('[EMAIL 开发模式] 验证码', code)

    threading.Thread(target=worker, daemon=True, name='email-code-send').start()


def send_code(email, purpose):
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        return {'code': 400, 'message': '请输入有效邮箱'}
    purpose = purpose or 'register'

    remain = _cooldown_remain(email, purpose)
    if remain > 0:
        return {'code': 429, 'message': '发送过于频繁，请 ' + str(remain) + ' 秒后再试'}

    code = _gen_code()
    expires = _now() + timedelta(seconds=SMS_CODE_TTL)
    ts = _now().isoformat()
    with get_conn() as conn:
        conn.execute(
            'DELETE FROM email_codes WHERE email=? AND purpose=?',
            (email, purpose),
        )
        conn.execute(
            'INSERT INTO email_codes (email, code, purpose, expires_at, created_at) VALUES (?,?,?,?,?)',
            (email, code, purpose, expires.isoformat(), ts),
        )

    ttl_min = max(1, SMS_CODE_TTL // 60)

    if DEV_MODE and not email_configured():
        print('[EMAIL 开发模式] 验证码', code, '邮箱', email, '用途', purpose)
    else:
        _dispatch_verification_email(email, code, ttl_min)

    return {
        'code': 200,
        'message': '验证码已发送至 ' + email + '（' + str(ttl_min) + ' 分钟内有效，请查收含垃圾箱）',
    }

def verify_code(email, code, purpose):
    email = (email or '').strip().lower()
    code = (code or '').strip()
    if not email or not code:
        return False
    with get_conn() as conn:
        row = conn.execute(
            'SELECT code, expires_at FROM email_codes WHERE email=? AND purpose=? '
            'ORDER BY created_at DESC LIMIT 1',
            (email, purpose),
        ).fetchone()
    if not row or row['code'] != code:
        return False
    try:
        exp = datetime.fromisoformat(row['expires_at'])
    except ValueError:
        return False
    return _now() <= exp
