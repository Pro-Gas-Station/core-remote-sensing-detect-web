# 大模型问答
import json
import requests
from config import LLM_API_URL, LLM_API_KEY, LLM_MODEL, MEMBER_LLM_API_URL, MEMBER_LLM_API_KEY, MEMBER_LLM_MODEL

SYSTEM_PROMPT = (
    '你是「遥感影像目标检测系统」的智能助手。'
    '系统基于 YOLO 模型，支持识别飞机、船舶、储油罐、棒球场、网球场、篮球场、田径场、港口、桥梁、车辆等 10 类俯视目标。'
    '请用简洁、专业的中文回答用户关于遥感检测、影像上传、模型使用、报告导出等问题。'
    '若问题与遥感无关，可礼貌说明并引导用户提问检测相关话题。'
)


def _chat_url(base):
    base = (base or '').strip().rstrip('/')
    if not base:
        base = 'https://api.deepseek.com'
    if base.endswith('/chat/completions'):
        return base
    if base.endswith('/v1'):
        return base + '/chat/completions'
    if 'deepseek.com' in base:
        return base + '/v1/chat/completions'
    return base + '/v1/chat/completions'


def _chat_url_candidates(base):
    """按常见兼容路径依次尝试，避免 404。"""
    base = (base or '').strip().rstrip('/')
    if not base:
        base = 'https://api.deepseek.com'
    urls = []
    primary = _chat_url(base)
    urls.append(primary)
    if 'deepseek.com' in base:
        alt = base + '/chat/completions'
        if alt not in urls:
            urls.append(alt)
        v1 = base + '/v1/chat/completions'
        if v1 not in urls:
            urls.append(v1)
    else:
        alt = base + '/chat/completions'
        if alt not in urls:
            urls.append(alt)
    deduped = []
    for u in urls:
        if u not in deduped:
            deduped.append(u)
    return deduped


def _post_chat(api_url, api_key, model, messages, max_tokens=1024, timeout=90):
    last_err = '未知错误'
    for url in _chat_url_candidates(api_url):
        payload = {
            'model': model or 'deepseek-chat',
            'messages': messages,
            'max_tokens': max_tokens,
        }
        try:
            resp = requests.post(
                url,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + api_key,
                },
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as e:
            last_err = '无法连接 API 服务：' + str(e)
            continue
        if resp.status_code == 200:
            return resp, url
        try:
            err = resp.json()
            msg = err.get('error', {})
            if isinstance(msg, dict):
                msg = msg.get('message', str(msg))
        except Exception:
            msg = resp.text[:200]
        last_err = 'HTTP ' + str(resp.status_code) + ': ' + str(msg)
        if resp.status_code == 404:
            continue
        break
    raise RuntimeError(last_err)


def test_llm_connection(api_url, api_key, model):
    """保存前/后测试 API 是否可用。"""
    try:
        resp, used_url = _post_chat(
            api_url,
            api_key,
            model,
            [{'role': 'user', 'content': 'hi'}],
            max_tokens=16,
            timeout=30,
        )
    except RuntimeError as e:
        return False, str(e)
    return True, '连接成功（' + used_url + '），云端大模型已启用'


def _sanitize_key(key):
    key = (key or '').strip()
    if not key or '填写' in key:
        return ''
    return key


def _is_member(username):
    if not username:
        return False
    from service.user_service import _get_row
    row = _get_row(username)
    if not row:
        return False
    role = row['role'] if 'role' in row.keys() and row['role'] else 'user'
    return role == 'member'


def get_llm_credentials(username=None):
    if username and _is_member(username):
        url = (MEMBER_LLM_API_URL or LLM_API_URL or '').strip()
        key = _sanitize_key(MEMBER_LLM_API_KEY)
        model = (MEMBER_LLM_MODEL or LLM_MODEL or 'deepseek-chat').strip()
        return url, key, model

    url = LLM_API_URL or ''
    key = _sanitize_key(LLM_API_KEY)
    model = LLM_MODEL or 'deepseek-chat'

    if username:
        from service.user_service import get_user_llm_settings
        user_cfg = get_user_llm_settings(username)
        if user_cfg.get('api_url'):
            url = user_cfg['api_url']
        if user_cfg.get('api_key'):
            key = _sanitize_key(user_cfg['api_key'])
        if user_cfg.get('model'):
            model = user_cfg['model']

    return url.strip(), key, model.strip()


def save_llm_config(username, api_url=None, api_key=None, model=None):
    if _is_member(username):
        return {
            'code': 400,
            'message': '会员用户已自动接入云端大模型，无需单独配置 API Key',
            'data': llm_status(username),
        }
    from service.user_service import save_user_llm_settings
    result = save_user_llm_settings(username, api_url, api_key, model)
    if result.get('code') != 200:
        return result
    url, key, mdl = get_llm_credentials(username)
    if not url or not key:
        return {'code': 400, 'message': '请填写 API 地址与 Key'}
    ok, tip = test_llm_connection(url, key, mdl)
    result['data'] = llm_status(username)
    result['test_ok'] = ok
    if ok:
        result['message'] = tip
    else:
        result['message'] = '配置已保存。连接测试未通过：' + tip
    return result


def _mask_key(key):
    if not key:
        return ''
    if len(key) <= 8:
        return '****'
    return key[:4] + '****' + key[-4:]


def _build_messages(question, history=None):
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    if history:
        for item in history[-12:]:
            role = item.get('role')
            text = (item.get('text') or item.get('content') or '').strip()
            if not text:
                continue
            if role == 'user':
                messages.append({'role': 'user', 'content': text})
            elif role in ('bot', 'assistant'):
                messages.append({'role': 'assistant', 'content': text})
    messages.append({'role': 'user', 'content': question})
    return messages


def _call_llm(question, history, api_url, api_key, model):
    messages = _build_messages(question, history)
    resp, _used = _post_chat(api_url, api_key, model, messages, max_tokens=1024, timeout=90)
    data = resp.json()
    return data['choices'][0]['message']['content'].strip()


def _local_answer(question):
    q = question.strip().replace('’', "'").replace('‘', "'")
    lower = q.lower()

    if any(w in q for w in ['你好', '您好', 'hello', 'hi', '在吗', '你是谁']):
        return '您好！我是遥感检测智能助手。您可以问我：支持哪些物体类别、如何上传影像、如何导出 PDF 报告等。'

    if any(w in q for w in ['物体', '类别', '识别', '支持', '哪些']) or '10' in q:
        return (
            '本系统支持 10 类俯视场景物体：飞机、船舶、储油罐、棒球场、网球场、篮球场、'
            '田径场、港口、桥梁、车辆。在检测工作台上传遥感影像即可在线识别。'
        )

    if 'pdf' in lower or '报告' in q or '导出' in q:
        return '完成检测后，点击「导出 PDF 报告」即可下载；发送邮件需先在个人中心绑定邮箱。'

    if '密码' in q or '注册' in q or '手机' in q:
        return '新用户需手机号短信注册；忘记密码可通过短信找回。管理员默认未绑手机，请先在个人中心绑定。'

    if '模型' in q or 'yolo' in lower or '原理' in q:
        return '系统采用 YOLO 深度学习检测模型，可在检测台顶部切换「已训练模型」或「新训练模型」。'

    if '上传' in q or '影像' in q or '图片' in q or '检测' in q:
        return '在检测工作台下方上传区选择本地 JPG/PNG 影像，或点击页面上方样例卡片快速加载，再点击「开始检测」。'

    if q.isdigit() or len(q) <= 3:
        return '收到。如需了解系统功能，可问我：系统能识别哪些物体？如何导出 PDF？'

    return (
        '关于「' + q + '」：本系统专注遥感影像目标检测。'
        '您可上传 JPG/PNG 影像进行识别，或在个人中心使用地图浏览、智能问答与报告功能。'
        '在「智能问答」页可填写 API Key 接入云端大模型。'
    )


def chat(question, username=None, history=None):
    if not question or not str(question).strip():
        return {'code': 400, 'message': '问题不能为空'}
    q = str(question).strip()
    api_url, api_key, model = get_llm_credentials(username)

    if api_url and api_key:
        try:
            answer = _call_llm(q, history, api_url, api_key, model)
            return {'code': 200, 'data': {'answer': answer, 'source': 'llm'}}
        except Exception as e:
            err = str(e)
            return {
                'code': 200,
                'data': {
                    'answer': '云端大模型调用失败：' + err + '\n\n请检查 API Key 是否有效、账户余额是否充足，或在上方重新保存配置。',
                    'source': 'error',
                },
            }
    if not username:
        return {
            'code': 200,
            'data': {
                'answer': '请先登录后再使用智能问答；保存 API Key 后需保持登录状态。',
                'source': 'local',
            },
        }
    return {'code': 200, 'data': {'answer': _local_answer(q), 'source': 'local'}}


def llm_status(username=None):
    api_url, api_key, model = get_llm_credentials(username)
    member = _is_member(username)
    configured = bool(api_url and api_key)
    return {
        'configured': configured,
        'api_url': api_url or '',
        'model': model,
        'api_key_masked': _mask_key(api_key),
        'is_member': member,
        'member_auto_llm': member and configured,
    }


def llm_config_for_user(username):
    api_url, api_key, model = get_llm_credentials(username)
    member = _is_member(username)
    return {
        'code': 200,
        'data': {
            'api_url': api_url or 'https://api.deepseek.com',
            'model': model or 'deepseek-chat',
            'api_key_masked': _mask_key(api_key),
            'configured': bool(api_url and api_key),
            'is_member': member,
            'member_auto_llm': member and bool(api_url and api_key),
        },
    }
