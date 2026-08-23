# 短信验证码：阿里云号码认证服务（SendSmsVerifyCode + CheckSmsVerifyCode）
import threading
import uuid
from datetime import datetime, timedelta

from config import DEV_MODE, SMS_CODE_TTL, SMS_VALID_TIME, CODE_SEND_COOLDOWN
from service.db import get_conn
from service.sms_provider import check_sms_verify_code, send_sms_verify_code, sms_configured


def _normalize_phone(phone):
    phone = (phone or '').strip().replace(' ', '').replace('-', '')
    if phone.startswith('+86'):
        phone = phone[3:]
    if phone.startswith('86') and len(phone) > 11:
        phone = phone[2:]
    return phone


def _normalize_code(code):
    return (code or '').strip().replace(' ', '')


def _now():
    return datetime.now()


def _cooldown_remain(phone, purpose):
    with get_conn() as conn:
        row = conn.execute(
            'SELECT created_at FROM sms_codes WHERE phone=? AND purpose=? '
            'ORDER BY created_at DESC LIMIT 1',
            (phone, purpose),
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


def _dispatch_provider_send(phone, purpose, out_id):
    def worker():
        result = send_sms_verify_code(phone, purpose, out_id)
        if not result.get('ok'):
            print('[SMS FAIL]', phone, purpose, result.get('message'))
        else:
            print('[SMS OK] 验证码已发送至', phone, '用途', purpose)

    threading.Thread(target=worker, daemon=True, name='sms-code-send').start()


def send_code(phone, purpose):
    phone = _normalize_phone(phone)
    if not phone or len(phone) < 11:
        return {'code': 400, 'message': '请输入有效手机号'}
    purpose = purpose or 'register'

    remain = _cooldown_remain(phone, purpose)
    if remain > 0:
        return {'code': 429, 'message': '发送过于频繁，请 ' + str(remain) + ' 秒后再试'}

    if not sms_configured():
        if DEV_MODE:
            print('[SMS 未配置] 请在阿里云号码认证服务开通后填写 data/sms_config.json')
        return {
            'code': 503,
            'message': (
                '短信认证未配置。请登录阿里云「号码认证服务」开通短信认证，'
                '在控制台复制赠送签名与模板编号，填入 web-flask/data/sms_config.json 后重启。'
                '控制台：https://dypns.console.aliyun.com'
            ),
        }

    out_id = str(uuid.uuid4())
    ttl_sec = min(SMS_CODE_TTL, SMS_VALID_TIME)
    expires = _now() + timedelta(seconds=ttl_sec)
    ts = _now().isoformat()
    with get_conn() as conn:
        conn.execute(
            'DELETE FROM sms_codes WHERE phone=? AND purpose=?',
            (phone, purpose),
        )
        conn.execute(
            'INSERT INTO sms_codes (phone, code, purpose, expires_at, created_at, out_id) '
            'VALUES (?,?,?,?,?,?)',
            (phone, '', purpose, expires.isoformat(), ts, out_id),
        )

    _dispatch_provider_send(phone, purpose, out_id)

    return {'code': 200, 'message': '验证码已发送至您的手机，请注意查收（5 分钟内有效）'}


def verify_code(phone, code, purpose):
    phone = _normalize_phone(phone)
    code = _normalize_code(code)
    if not phone or not code:
        return False

    with get_conn() as conn:
        row = conn.execute(
            'SELECT expires_at, out_id FROM sms_codes WHERE phone=? AND purpose=? '
            'ORDER BY created_at DESC LIMIT 1',
            (phone, purpose),
        ).fetchone()

    if row:
        try:
            exp = datetime.fromisoformat(row['expires_at'])
            if _now() > exp:
                return False
        except ValueError:
            pass

    if sms_configured():
        out_id = row['out_id'] if row else None
        result = check_sms_verify_code(phone, code, out_id)
        return result.get('ok', False)

    if not row or not row['code']:
        return False
    return row['code'] == code
