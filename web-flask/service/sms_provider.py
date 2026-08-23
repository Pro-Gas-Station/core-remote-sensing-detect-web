# 短信网关：阿里云号码认证服务（Dypnsapi 短信认证）
import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from config import (
    SMS_ACCESS_KEY_ID,
    SMS_ACCESS_KEY_SECRET,
    SMS_CODE_LENGTH,
    SMS_CODE_TYPE,
    SMS_REGION_ID,
    SMS_SCHEME_NAME,
    SMS_SIGN_NAME,
    SMS_TEMPLATE_CODE,
    SMS_VALID_TIME,
)

DYPNS_ENDPOINT = 'https://dypnsapi.aliyuncs.com/'
API_VERSION = '2017-05-25'


def sms_configured():
    return bool(SMS_ACCESS_KEY_ID and SMS_ACCESS_KEY_SECRET and SMS_SIGN_NAME and SMS_TEMPLATE_CODE)


def _percent_encode(value):
    return quote(str(value), safe='~')


def _sign(params, secret):
    items = sorted(params.items())
    query = '&'.join(_percent_encode(k) + '=' + _percent_encode(v) for k, v in items)
    string_to_sign = 'GET&%2F&' + _percent_encode(query)
    digest = hmac.new((secret + '&').encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(digest).decode('utf-8')


def _call_dypns(action, extra_params):
    if not sms_configured():
        return {'ok': False, 'message': '短信认证服务未配置，请填写 data/sms_config.json'}

    params = {
        'AccessKeyId': SMS_ACCESS_KEY_ID,
        'Action': action,
        'Format': 'JSON',
        'RegionId': SMS_REGION_ID or 'cn-hangzhou',
        'SignatureMethod': 'HMAC-SHA1',
        'SignatureNonce': str(uuid.uuid4()),
        'SignatureVersion': '1.0',
        'Timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'Version': API_VERSION,
    }
    params.update(extra_params)
    params['Signature'] = _sign(params, SMS_ACCESS_KEY_SECRET)

    try:
        resp = requests.get(DYPNS_ENDPOINT, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        return {'ok': False, 'message': '短信认证 API 请求失败：' + str(e), 'raw': None}

    if action == 'CheckSmsVerifyCode':
        if data.get('Code') == 'OK':
            return {'ok': True, 'data': data, 'message': data.get('Message') or 'OK'}

    if data.get('Code') == 'OK' and data.get('Success'):
        return {'ok': True, 'data': data, 'message': data.get('Message') or 'OK'}

    code = data.get('Code') or ''
    msg = data.get('Message') or code or resp.text[:200]
    if code == 'biz.FREQUENCY':
        msg = '发送过于频繁，请稍后再试（同一手机号 60 秒内只能发一次）'
    elif code == 'isv.SMS_TEMPLATE_ILLEGAL':
        msg = '模板编号无效，请核对 TemplateCode 是否为控制台赠送模板 100001'
    elif code == 'isv.SMS_SIGNATURE_ILLEGAL':
        msg = '签名无效，请核对 SignName 是否为「速通互联验证码」'
    return {'ok': False, 'message': str(msg), 'raw': data}


def send_sms_verify_code(phone, purpose=None, out_id=None):
    """SendSmsVerifyCode：由阿里云生成验证码并下发短信。"""
    out_id = out_id or str(uuid.uuid4())
    valid_min = max(1, int(SMS_VALID_TIME / 60))
    extra = {
        'PhoneNumber': phone,
        'SignName': SMS_SIGN_NAME,
        'TemplateCode': SMS_TEMPLATE_CODE,
        'TemplateParam': json.dumps({'code': '##code##', 'min': str(valid_min)}, ensure_ascii=False),
        'CountryCode': '86',
        'CodeType': str(SMS_CODE_TYPE),
        'CodeLength': str(SMS_CODE_LENGTH),
        'ValidTime': str(SMS_VALID_TIME),
        'OutId': out_id,
        'ReturnVerifyCode': 'false',
    }
    if SMS_SCHEME_NAME:
        extra['SchemeName'] = SMS_SCHEME_NAME

    result = _call_dypns('SendSmsVerifyCode', extra)
    if not result.get('ok'):
        return result
    model = (result.get('data') or {}).get('Model') or {}
    result['out_id'] = model.get('OutId') or out_id
    return result


def check_sms_verify_code(phone, verify_code, out_id=None):
    """CheckSmsVerifyCode：调用阿里云核验验证码。"""
    extra = {
        'PhoneNumber': phone,
        'VerifyCode': verify_code,
        'CountryCode': '86',
        'CaseAuthPolicy': '1',
    }
    if out_id:
        extra['OutId'] = out_id
    if SMS_SCHEME_NAME:
        extra['SchemeName'] = SMS_SCHEME_NAME

    result = _call_dypns('CheckSmsVerifyCode', extra)
    if not result.get('ok'):
        return {'ok': False, 'message': result.get('message', '核验请求失败')}

    model = (result.get('data') or {}).get('Model') or {}
    verify_result = model.get('VerifyResult') or model.get('verifyResult')
    if verify_result == 'PASS':
        return {'ok': True, 'message': '验证通过'}

    return {'ok': False, 'message': '验证码错误或已过期，请使用最新一条短信中的验证码'}


def dispatch_sms(phone, code, purpose=None):
    """兼容旧调用：短信认证服务由阿里云生成验证码，忽略传入的 code。"""
    return send_sms_verify_code(phone, purpose)
