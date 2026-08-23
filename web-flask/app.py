# 遥感影像目标检测系统 - Flask 后端入口
import os
import json
from flask import Flask, request, jsonify, send_from_directory, Response, redirect
from flask_cors import CORS

from service.user_service import (
    login_user, register_user, init_default_users,
    get_profile, update_profile, save_avatar,
    bind_phone, bind_email, change_password, reset_password_by_phone, reset_password_by_email,
    save_user_setting, get_user_settings, list_all_users, is_admin,
    admin_delete_user, admin_unbind_phone, admin_unbind_email,
    admin_set_password, admin_set_role,
    _get_row,
)
from service.model_data_service import get_model_data, _read_experiments
from service.sms_service import send_code
from service.email_code_service import send_code as send_email_code
from service.email_service import send_email
from service.pdf_service import build_detection_pdf, PDF_ENGINE_VERSION
from service.news_service import get_news_list
from service.llm_service import chat, llm_status, llm_config_for_user, save_llm_config
from service.db import get_conn, init_db
from config import email_configured, reload_email_config, SMTP_HOST, SMTP_USER
from service.sms_provider import sms_configured

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(TEMPLATE_DIR, 'static')
IMAGE_DIR = os.path.join(TEMPLATE_DIR, 'images')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
CORS(app, resources={r'/api/*': {'origins': '*'}}, supports_credentials=False)


def _read_html(filename):
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _username_from_request():
    data = request.get_json(silent=True) or {}
    name = request.headers.get('X-User-Name') or data.get('username') or request.args.get('username')
    return (name or '').strip() or None


def _resolve_email_send(data):
    """target=bound 仅发绑定邮箱；target=new 仅发表单新邮箱；否则为登录页注册/找回。"""
    purpose = (data.get('purpose') or 'register').strip()
    target = (data.get('target') or '').strip().lower()
    scene = (data.get('scene') or '').strip().lower()
    email_in = (data.get('email') or '').strip().lower()
    username = _username_from_request()

    if not target:
        if scene == 'identity' or purpose in ('identity', 'reset'):
            target = 'bound'
        elif scene == 'new':
            target = 'new'
        elif purpose == 'bind' and email_in:
            target = 'new'

    if target == 'bound':
        if not username:
            return None, purpose, {'code': 401, 'message': '请先登录'}
        row = _get_row(username)
        if not row:
            return None, purpose, {'code': 404, 'message': '用户不存在'}
        if not row['email']:
            return None, purpose, {'code': 400, 'message': '当前账号未绑定邮箱'}
        return row['email'].strip().lower(), purpose, None

    if target == 'new':
        if not email_in or '@' not in email_in:
            return None, purpose, {'code': 400, 'message': '请输入有效的新邮箱'}
        if username:
            row = _get_row(username)
            if row and row['email'] and email_in == row['email'].strip().lower():
                return None, purpose, {'code': 400, 'message': '新邮箱不能与当前绑定邮箱相同'}
        return email_in, purpose, None

    # 已登录且未传新邮箱：原邮箱/改密等场景，发到绑定邮箱
    if username:
        row = _get_row(username)
        if not row:
            return None, purpose, {'code': 404, 'message': '用户不存在'}
        if not row['email']:
            return None, purpose, {'code': 400, 'message': '当前账号未绑定邮箱'}
        return row['email'].strip().lower(), purpose, None

    if not email_in or '@' not in email_in:
        return None, purpose, {'code': 400, 'message': '请输入有效邮箱'}
    return email_in, purpose, None


def _resolve_sms_send(data):
    """已登录且 scene!=new 时，验证码发到账号绑定手机。"""
    from service.sms_service import _normalize_phone
    purpose = (data.get('purpose') or 'register').strip()
    scene = (data.get('scene') or '').strip()
    phone = _normalize_phone(data.get('phone'))
    username = _username_from_request()
    if username:
        row = _get_row(username)
        if not row:
            return None, purpose, {'code': 404, 'message': '用户不存在'}
        if scene == 'new':
            if not phone or len(phone) < 11:
                return None, purpose, {'code': 400, 'message': '请输入有效的新手机号'}
        else:
            if not row['phone']:
                return None, purpose, {'code': 400, 'message': '当前账号未绑定手机'}
            phone = _normalize_phone(row['phone'])
    elif not phone or len(phone) < 11:
        return None, purpose, {'code': 400, 'message': '请输入有效手机号'}
    if not phone or len(phone) < 11:
        return None, purpose, {'code': 400, 'message': '请输入有效手机号'}
    return phone, purpose, None


@app.route('/')
@app.route('/login.html')
def page_login():
    return _read_html('login.html'), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/detect.html')
def page_detect():
    return _read_html('detect.html'), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/profile.html')
@app.route('/profile')
def page_profile():
    return _read_html('profile.html'), 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
    }


@app.route('/detect')
def page_detect_short():
    return _read_html('detect.html'), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/login')
def page_login_short():
    return _read_html('login.html'), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/favicon.ico')
def favicon_ico():
    ico = os.path.join(STATIC_DIR, 'favicon.ico')
    if os.path.isfile(ico):
        return send_from_directory(STATIC_DIR, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    png = os.path.join(STATIC_DIR, 'favicon.png')
    if os.path.isfile(png):
        return send_from_directory(STATIC_DIR, 'favicon.png', mimetype='image/png')
    return '', 204


@app.route('/favicon.svg')
def favicon_svg():
    svg = os.path.join(STATIC_DIR, 'favicon.svg')
    if os.path.isfile(svg):
        return send_from_directory(STATIC_DIR, 'favicon.svg', mimetype='image/svg+xml')
    return '', 204


@app.route('/model-data.html')
@app.route('/model-data')
def page_model_data():
    return _read_html('model-data.html'), 200, {'Content-Type': 'text/html; charset=utf-8'}


APP_VERSION = '2025-06-25-admin-member-pdf-v1'


@app.route('/admin-users.html')
@app.route('/admin-users')
def page_admin_users():
    return redirect('/model-data.html?type=admin', code=302)


@app.route('/images/<path:filename>')
def static_images(filename):
    return send_from_directory(IMAGE_DIR, filename)


@app.route('/api/user/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    return jsonify(login_user(data.get('username'), data.get('password')))


@app.route('/api/user/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or {}
    return jsonify(register_user(
        data.get('username'),
        data.get('password'),
        data.get('roleLabel'),
        data.get('phone'),
        data.get('smsCode'),
        data.get('email'),
        data.get('emailCode'),
        data.get('registerType'),
    ))


@app.route('/api/email/send', methods=['POST'])
def api_email_send():
    """登录页注册/找回密码发验证码（需传邮箱）。"""
    data = request.get_json(silent=True) or {}
    email, purpose, err = _resolve_email_send(data)
    if err:
        return jsonify(err)
    if not email:
        return jsonify({'code': 400, 'message': '请输入有效邮箱'})
    result = send_email_code(email, purpose)
    if result.get('code') == 200:
        result['data'] = {'email': email, 'purpose': purpose}
    return jsonify(result)


@app.route('/api/email/send-bound', methods=['POST'])
def api_email_send_bound():
    """已登录：验证码仅发到账号绑定邮箱（原邮箱验证/改密）。"""
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    purpose = (data.get('purpose') or 'identity').strip()
    row = _get_row(username)
    if not row:
        return jsonify({'code': 404, 'message': '用户不存在'})
    if not row['email']:
        return jsonify({'code': 400, 'message': '当前账号未绑定邮箱'})
    email = row['email'].strip().lower()
    print('[EMAIL BOUND]', username, '->', email, 'purpose=' + purpose)
    result = send_email_code(email, purpose)
    if result.get('code') == 200:
        result['data'] = {'email': email, 'purpose': purpose}
    return jsonify(result)


@app.route('/api/email/send-new', methods=['POST'])
def api_email_send_new():
    """已登录：验证码发到用户填写的新邮箱（绑定/更换）。"""
    username = _username_from_request()
    data = request.get_json(silent=True) or {}
    purpose = (data.get('purpose') or 'bind').strip()
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'code': 400, 'message': '请输入有效的新邮箱'})
    if username:
        row = _get_row(username)
        if row and row['email'] and email == row['email'].strip().lower():
            return jsonify({'code': 400, 'message': '新邮箱不能与当前绑定邮箱相同'})
    print('[EMAIL NEW]', username or '-', '->', email, 'purpose=' + purpose)
    result = send_email_code(email, purpose)
    if result.get('code') == 200:
        result['data'] = {'email': email, 'purpose': purpose}
    return jsonify(result)


@app.route('/api/email/status', methods=['GET'])
def api_email_status():
    reload_email_config()
    return jsonify({
        'code': 200,
        'data': {
            'configured': email_configured(),
            'smtp_host': SMTP_HOST or '',
            'smtp_user': SMTP_USER or '',
            'hint': (
                '已配置 SMTP，可直接发送'
                if email_configured()
                else '请编辑 data/email_config.json 填写 smtp_pass'
            ),
        },
    })


@app.route('/api/email/test', methods=['POST'])
def api_email_test():
    """发送测试邮件到发件邮箱自身，用于验证 SMTP。"""
    reload_email_config()
    if not email_configured():
        return jsonify({'code': 503, 'message': 'SMTP 未配置，请填写 data/email_config.json'})
    target = SMTP_USER
    body = '这是一封 SMTP 测试邮件。若您能收到，说明邮箱验证码功能已可用。'
    result = send_email(target, '【翊卫云瞳】SMTP 测试', body)
    return jsonify(result)


@app.route('/api/sms/send', methods=['POST'])
def api_sms_send():
    data = request.get_json(silent=True) or {}
    phone, purpose, err = _resolve_sms_send(data)
    if err:
        return jsonify(err)
    return jsonify(send_code(phone, purpose))


@app.route('/api/user/profile', methods=['GET'])
def api_profile_get():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(get_profile(username))


@app.route('/api/user/profile', methods=['PUT'])
def api_profile_put():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(update_profile(username, data))


@app.route('/api/user/avatar', methods=['POST'])
def api_avatar():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(save_avatar(username, data.get('image')))


@app.route('/api/user/bind-phone', methods=['POST'])
def api_bind_phone():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(bind_phone(
        username,
        data.get('phone'),
        data.get('smsCode'),
        data.get('oldPassword'),
        data.get('oldSmsCode'),
    ))


@app.route('/api/user/bind-email', methods=['POST'])
def api_bind_email():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(bind_email(
        username,
        data.get('email'),
        data.get('emailCode'),
        data.get('oldPassword'),
        data.get('oldEmailCode'),
    ))


@app.route('/api/user/password/change', methods=['POST'])
def api_password_change():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(change_password(
        username,
        data.get('newPassword'),
        data.get('smsCode'),
        data.get('oldPassword'),
        data.get('emailCode'),
    ))


@app.route('/api/user/password/reset', methods=['POST'])
def api_password_reset():
    data = request.get_json(silent=True) or {}
    return jsonify(reset_password_by_phone(
        data.get('phone'), data.get('smsCode'), data.get('newPassword'),
    ))


@app.route('/api/user/password/reset-email', methods=['POST'])
def api_password_reset_email():
    data = request.get_json(silent=True) or {}
    return jsonify(reset_password_by_email(
        data.get('email'), data.get('emailCode'), data.get('newPassword'),
    ))


@app.route('/api/admin/users', methods=['GET'])
def api_admin_users():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(list_all_users(username))


@app.route('/api/admin/users/<target_username>', methods=['DELETE'])
def api_admin_delete_user(target_username):
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(admin_delete_user(username, target_username))


@app.route('/api/admin/users/<target_username>/unbind-phone', methods=['POST'])
def api_admin_unbind_phone(target_username):
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(admin_unbind_phone(username, target_username))


@app.route('/api/admin/users/<target_username>/unbind-email', methods=['POST'])
def api_admin_unbind_email(target_username):
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(admin_unbind_email(username, target_username))


@app.route('/api/admin/users/<target_username>/password', methods=['POST'])
def api_admin_set_password(target_username):
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(admin_set_password(username, target_username, data.get('newPassword')))


@app.route('/api/admin/users/<target_username>/role', methods=['POST'])
def api_admin_set_role(target_username):
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(admin_set_role(username, target_username, data.get('role')))


@app.route('/api/user/settings', methods=['GET'])
def api_settings_get():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(get_user_settings(username))


@app.route('/api/user/settings', methods=['POST'])
def api_settings_post():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    return jsonify(save_user_setting(username, data.get('key'), data.get('value')))


@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'code': 200,
        'data': {
            'service': 'remote-sensing-detect',
            'app_version': APP_VERSION,
            'pdf_engine': PDF_ENGINE_VERSION,
            'email_configured': email_configured(),
            'email_api': 'send-bound',
            'sms_configured': sms_configured(),
            'port': 5011,
            'pages': ['model-data.html', 'admin-users.html', 'detect.html', 'profile.html'],
        },
    })


@app.route('/api/report/pdf', methods=['POST'])
def api_report_pdf():
    try:
        username = _username_from_request() or 'guest'
        data = request.get_json(silent=True) or {}
        detections = data.get('detections') or []
        pdf_bytes = build_detection_pdf(
            username,
            data.get('modelName', ''),
            detections,
            data.get('total', len(detections)),
            data.get('message'),
        )
        try:
            with get_conn() as conn:
                conn.execute(
                    'INSERT INTO detection_reports (username, model_name, total, summary, detections_json, created_at) '
                    'VALUES (?,?,?,?,?,?)',
                    (
                        username,
                        data.get('modelName', ''),
                        data.get('total', len(detections)),
                        data.get('message', ''),
                        json.dumps(detections, ensure_ascii=False),
                        __import__('datetime').datetime.now().isoformat(),
                    ),
                )
        except Exception:
            pass
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'attachment; filename=detection_report.pdf',
                'Cache-Control': 'no-store, no-cache, must-revalidate',
                'X-PDF-Engine': PDF_ENGINE_VERSION,
            },
        )
    except Exception as e:
        return jsonify({'code': 500, 'message': 'PDF 生成失败：' + str(e)}), 500


@app.route('/api/report/email', methods=['POST'])
def api_report_email():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    from service.user_service import _get_row
    row = _get_row(username)
    if not row or not row['email']:
        return jsonify({'code': 400, 'message': '请先在个人中心绑定邮箱后再发送报告'})
    data = request.get_json(silent=True) or {}
    detections = data.get('detections') or []
    pdf_bytes = build_detection_pdf(
        username,
        data.get('modelName', ''),
        detections,
        data.get('total', len(detections)),
        data.get('message'),
    )
    body = '您好，附件为遥感影像目标检测报告。\n检测目标数：' + str(data.get('total', len(detections)))
    result = send_email(row['email'], '遥感检测分析报告', body, pdf_bytes)
    return jsonify(result)


@app.route('/api/news', methods=['GET'])
def api_news():
    return jsonify(get_news_list())


@app.route('/api/llm/status', methods=['GET'])
def api_llm_status():
    username = _username_from_request() or request.args.get('username')
    return jsonify({'code': 200, 'data': llm_status(username)})


@app.route('/api/llm/config', methods=['GET'])
def api_llm_config_get():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    return jsonify(llm_config_for_user(username))


@app.route('/api/llm/config', methods=['POST'])
def api_llm_config_post():
    username = _username_from_request()
    if not username:
        return jsonify({'code': 401, 'message': '请先登录'})
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(save_llm_config(
            username,
            data.get('apiUrl') or data.get('api_url'),
            data.get('apiKey') or data.get('api_key'),
            data.get('model'),
        ))
    except Exception as e:
        return jsonify({'code': 500, 'message': '保存大模型配置失败：' + str(e)}), 500


@app.route('/api/llm/chat', methods=['POST'])
def api_llm_chat():
    username = _username_from_request()
    data = request.get_json(silent=True) or {}
    return jsonify(chat(data.get('question'), username, data.get('history')))


@app.route('/api/models', methods=['GET'])
def api_models():
    from service.detection_service import get_models
    return jsonify(get_models())


@app.route('/api/detect', methods=['POST'])
def api_detect():
    from service.detection_service import detect_objects
    data = request.get_json(silent=True) or {}
    image_data = data.get('image')
    if not image_data:
        return jsonify({'code': 400, 'message': '请上传影像数据'})
    model_name = data.get('model', 'ready-model')
    return jsonify(detect_objects(model_name, image_data))


@app.route('/api/experiments', methods=['GET'])
def api_experiments():
    from config import MODEL_CONFIGS
    model_key = request.args.get('model') or 'ready-model'
    if model_key not in MODEL_CONFIGS:
        return jsonify({'code': 404, 'message': '模型不存在'})
    return jsonify(_read_experiments(MODEL_CONFIGS[model_key]))


@app.route('/api/model-data', methods=['GET'])
def api_model_data():
    from config import MODEL_CONFIGS
    data_type = request.args.get('type')
    model_key = request.args.get('model') or 'ready-model'
    if not data_type:
        return jsonify({'code': 400, 'message': '缺少 type 参数'})
    if data_type == 'experiments':
        if model_key not in MODEL_CONFIGS:
            return jsonify({'code': 404, 'message': '模型不存在'})
        return jsonify(_read_experiments(MODEL_CONFIGS[model_key]))
    return jsonify(get_model_data(data_type, model_key))


if __name__ == '__main__':
    import socket
    init_db()
    init_default_users()
    port = 5011
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(('0.0.0.0', port))
        probe.close()
    except OSError:
        print('[错误] 端口', port, '已被占用。请关闭所有 python 窗口后，双击 web-flask/start.bat 再启动。')
        raise SystemExit(1)
    print('[startup] PDF engine:', PDF_ENGINE_VERSION)
    print('[startup] Email SMTP:', '已配置' if email_configured() else '未配置（开发模式仅控制台打印验证码）')
    print('[startup] App version:', APP_VERSION)
    print('[startup] Email API: /api/email/send-bound, /api/email/send-new')
    print('[startup] Open http://127.0.0.1:5011/login.html')
    app.run(host='0.0.0.0', port=port)
