# 用户账号与个人信息
import os
import json
import base64
from datetime import datetime
from config import USERS_FILE, AVATAR_DIR, THEME_OPTIONS
from service.db import get_conn, init_db, public_user, row_to_user
from service.sms_service import verify_code as verify_sms_code
from service.email_code_service import verify_code as verify_email_code, send_code as send_email_code


def _now():
    return datetime.now().isoformat()


def _migrate_json_users():
    if not os.path.exists(USERS_FILE):
        return
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        legacy = json.load(f)
    if not legacy:
        return
    with get_conn() as conn:
        for username, u in legacy.items():
            exists = conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
            if exists:
                continue
            conn.execute(
                'INSERT INTO users (username, password, real_name, phone, email, avatar, theme, bio, created_at, updated_at) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
                (
                    username,
                    u.get('password', ''),
                    u.get('realName', username),
                    u.get('phone') or None,
                    u.get('email') or None,
                    u.get('avatar') or None,
                    u.get('theme') or 'default',
                    u.get('bio') or '',
                    u.get('createTime') or _now(),
                    _now(),
                ),
            )


def init_default_users():
    init_db()
    _migrate_json_users()
    with get_conn() as conn:
        count = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
        if count > 0:
            return
        now = _now()
        conn.execute(
            'INSERT INTO users (username, password, real_name, phone, email, theme, role, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            ('admin', '123456', '管理员', None, None, 'default', 'admin', now, now),
        )
        conn.execute(
            'INSERT INTO users (username, password, real_name, phone, email, theme, role, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            ('user', '123456', '普通用户', None, None, 'default', 'user', now, now),
        )
    print('已初始化默认账号 admin/user，密码均为 123456（未绑定手机/邮箱）')


def _get_row(username):
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()


def login_user(username, password):
    if not username or not password:
        return {'code': 400, 'message': '用户名和密码不能为空'}
    row = _get_row(username)
    if not row or row['password'] != password:
        return {'code': 400, 'message': '用户名或密码错误'}
    return {
        'code': 200,
        'message': '登录成功',
        'data': {'user': public_user(row)},
    }


def is_admin(username):
    row = _get_row(username)
    if not row:
        return False
    role = row['role'] if 'role' in row.keys() and row['role'] else ''
    return role == 'admin' or row['username'] == 'admin'


def _verify_identity(row, old_password=None, old_sms_code=None, old_email_code=None, sms_purpose='reset'):
    if old_password and old_password == row['password']:
        return True
    if row['phone'] and old_sms_code and verify_sms_code(row['phone'], old_sms_code, sms_purpose):
        return True
    if row['email'] and old_email_code:
        if verify_email_code(row['email'], old_email_code, 'identity'):
            return True
        if verify_email_code(row['email'], old_email_code, 'bind'):
            return True
    return False


def register_user(username, password, role_label=None, phone=None, sms_code=None, email=None, email_code=None, register_type='phone'):
    if not username or not password:
        return {'code': 400, 'message': '用户名和密码不能为空'}
    if len(username) < 3 or len(password) < 6:
        return {'code': 400, 'message': '用户名至少3位，密码至少6位'}

    register_type = (register_type or 'phone').lower()
    phone = (phone or '').strip()
    email = (email or '').strip().lower()

    if register_type == 'email':
        if not email or not email_code:
            return {'code': 400, 'message': '请使用邮箱并完成邮箱验证'}
        if not verify_email_code(email, email_code, 'register'):
            return {'code': 400, 'message': '邮箱验证码错误或已过期'}
    else:
        if not phone or not sms_code:
            return {'code': 400, 'message': '请使用手机号并完成短信验证'}
        if not verify_sms_code(phone, sms_code, 'register'):
            return {'code': 400, 'message': '短信验证码错误或已过期'}

    with get_conn() as conn:
        if conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
            return {'code': 400, 'message': '用户名已存在'}
        if phone and conn.execute('SELECT 1 FROM users WHERE phone=?', (phone,)).fetchone():
            return {'code': 400, 'message': '该手机号已注册'}
        if email and conn.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
            return {'code': 400, 'message': '该邮箱已注册'}
        now = _now()
        display = '普通用户'
        conn.execute(
            'INSERT INTO users (username, password, real_name, phone, email, theme, role, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (username, password, display, phone or None, email or None, 'default', 'user', now, now),
        )
    return {'code': 200, 'message': '注册成功'}


def get_profile(username):
    row = _get_row(username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    return {
        'code': 200,
        'data': {
            'user': public_user(row),
            'themes': THEME_OPTIONS,
            'stats': get_user_stats(username),
        },
    }


def update_profile(username, data):
    row = _get_row(username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    fields = {
        'real_name': data.get('realName', row['real_name']),
        'bio': data.get('bio', row['bio']),
        'theme': data.get('theme', row['theme']),
        'gender': data.get('gender', row['gender'] if 'gender' in row.keys() else ''),
        'work_unit': data.get('workUnit', row['work_unit'] if 'work_unit' in row.keys() else ''),
        'department': data.get('department', row['department'] if 'department' in row.keys() else ''),
        'address': data.get('address', row['address'] if 'address' in row.keys() else ''),
        'postal_code': data.get('postalCode', row['postal_code'] if 'postal_code' in row.keys() else ''),
        'region': data.get('region', row['region'] if 'region' in row.keys() else ''),
    }
    with get_conn() as conn:
        conn.execute(
            'UPDATE users SET real_name=?, bio=?, theme=?, gender=?, work_unit=?, department=?, '
            'address=?, postal_code=?, region=?, updated_at=? WHERE username=?',
            (
                fields['real_name'], fields['bio'], fields['theme'], fields['gender'],
                fields['work_unit'], fields['department'], fields['address'],
                fields['postal_code'], fields['region'], _now(), username,
            ),
        )
    return get_profile(username)


def get_user_stats(username):
    with get_conn() as conn:
        reports = conn.execute(
            'SELECT COUNT(*) AS c FROM detection_reports WHERE username=?', (username,)
        ).fetchone()['c']
        last = conn.execute(
            'SELECT created_at, total, model_name FROM detection_reports WHERE username=? '
            'ORDER BY id DESC LIMIT 1', (username,)
        ).fetchone()
    return {
        'reportCount': reports,
        'lastDetectAt': last['created_at'] if last else '',
        'lastDetectTotal': last['total'] if last else 0,
        'lastModel': last['model_name'] if last else '',
    }


def save_avatar(username, image_data):
    if not image_data:
        return {'code': 400, 'message': '请上传头像'}
    os.makedirs(AVATAR_DIR, exist_ok=True)
    raw = image_data
    if ',' in raw:
        raw = raw.split(',', 1)[1]
    try:
        binary = base64.b64decode(raw)
    except Exception:
        return {'code': 400, 'message': '头像数据无效'}
    path = os.path.join(AVATAR_DIR, username + '.jpg')
    with open(path, 'wb') as f:
        f.write(binary)
    rel = '/images/avatars/' + username + '.jpg'
    with get_conn() as conn:
        conn.execute(
            'UPDATE users SET avatar=?, updated_at=? WHERE username=?',
            (rel + '?t=' + str(int(datetime.now().timestamp())), _now(), username),
        )
    row = _get_row(username)
    return {'code': 200, 'message': '头像已更新', 'data': {'user': public_user(row)}}


def bind_phone(username, phone, sms_code, old_password=None, old_sms_code=None):
    if not phone or not sms_code:
        return {'code': 400, 'message': '手机号和验证码不能为空'}
    row = _get_row(username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    if row['phone']:
        if not _verify_identity(row, old_password, old_sms_code, None, 'reset'):
            return {'code': 400, 'message': '更换手机号需原手机号验证码或登录密码'}
    if not verify_sms_code(phone, sms_code, 'bind'):
        return {'code': 400, 'message': '验证码错误或已过期'}
    with get_conn() as conn:
        dup = conn.execute('SELECT username FROM users WHERE phone=? AND username!=?', (phone, username)).fetchone()
        if dup:
            return {'code': 400, 'message': '该手机号已被其他账号绑定'}
        conn.execute('UPDATE users SET phone=?, updated_at=? WHERE username=?', (phone, _now(), username))
    return {'code': 200, 'message': '手机号绑定成功', 'data': {'user': public_user(_get_row(username))}}


def bind_email(username, email, email_code, old_password=None, old_email_code=None):
    if not email or '@' not in email:
        return {'code': 400, 'message': '请输入有效邮箱'}
    if not email_code:
        return {'code': 400, 'message': '请填写邮箱验证码'}
    row = _get_row(username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    if row['email']:
        if not _verify_identity(row, old_password, None, old_email_code):
            return {'code': 400, 'message': '更换邮箱需原邮箱验证码或登录密码'}
    if not verify_email_code(email, email_code, 'bind'):
        return {'code': 400, 'message': '邮箱验证码错误或已过期'}
    email = email.strip().lower()
    with get_conn() as conn:
        dup = conn.execute('SELECT username FROM users WHERE email=? AND username!=?', (email, username)).fetchone()
        if dup:
            return {'code': 400, 'message': '该邮箱已被其他账号绑定'}
        conn.execute('UPDATE users SET email=?, updated_at=? WHERE username=?', (email, _now(), username))
    return {'code': 200, 'message': '邮箱已绑定', 'data': {'user': public_user(_get_row(username))}}


def change_password(username, new_password, sms_code=None, old_password=None, email_code=None):
    row = _get_row(username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    if not new_password or len(new_password) < 6:
        return {'code': 400, 'message': '新密码至少6位'}
    if new_password == row['password']:
        return {'code': 400, 'message': '新密码不能与原密码相同'}
    verified = False
    if row['phone'] and sms_code and verify_sms_code(row['phone'], sms_code, 'reset'):
        verified = True
    elif row['email'] and email_code and verify_email_code(row['email'], email_code, 'reset'):
        verified = True
    elif old_password and old_password == row['password']:
        verified = True
    elif not row['phone'] and not row['email']:
        if old_password and old_password == row['password']:
            verified = True
    if not verified:
        if row['phone']:
            return {'code': 400, 'message': '请使用绑定手机短信验证码、绑定邮箱验证码或原密码'}
        if row['email']:
            return {'code': 400, 'message': '请使用绑定邮箱验证码或原密码'}
        return {'code': 400, 'message': '请提供原密码'}
    with get_conn() as conn:
        conn.execute('UPDATE users SET password=?, updated_at=? WHERE username=?', (new_password, _now(), username))
    return {'code': 200, 'message': '密码修改成功'}


def reset_password_by_phone(phone, sms_code, new_password):
    if not phone or not sms_code or not new_password:
        return {'code': 400, 'message': '请填写完整信息'}
    if len(new_password) < 6:
        return {'code': 400, 'message': '新密码至少6位'}
    if not verify_sms_code(phone, sms_code, 'reset'):
        return {'code': 400, 'message': '验证码错误或已过期'}
    with get_conn() as conn:
        row = conn.execute('SELECT username, password FROM users WHERE phone=?', (phone,)).fetchone()
        if not row:
            return {'code': 400, 'message': '该手机号未绑定任何账号'}
        if new_password == row['password']:
            return {'code': 400, 'message': '新密码不能与原密码相同'}
        conn.execute('UPDATE users SET password=?, updated_at=? WHERE username=?', (new_password, _now(), row['username']))
    return {'code': 200, 'message': '密码已重置，请登录'}


def reset_password_by_email(email, email_code, new_password):
    email = (email or '').strip().lower()
    if not email or not email_code or not new_password:
        return {'code': 400, 'message': '请填写完整信息'}
    if len(new_password) < 6:
        return {'code': 400, 'message': '新密码至少6位'}
    if not verify_email_code(email, email_code, 'reset'):
        return {'code': 400, 'message': '邮箱验证码错误或已过期'}
    with get_conn() as conn:
        row = conn.execute('SELECT username, password FROM users WHERE email=?', (email,)).fetchone()
        if not row:
            return {'code': 400, 'message': '该邮箱未绑定任何账号'}
        if new_password == row['password']:
            return {'code': 400, 'message': '新密码不能与原密码相同'}
        conn.execute('UPDATE users SET password=?, updated_at=? WHERE username=?', (new_password, _now(), row['username']))
    return {'code': 200, 'message': '密码已重置，请登录'}


def _role_label(role):
    if role == 'admin':
        return '管理员'
    if role == 'member':
        return '会员用户'
    return '普通用户'


def admin_delete_user(admin_username, target_username):
    if not is_admin(admin_username):
        return {'code': 403, 'message': '仅管理员可操作'}
    target_username = (target_username or '').strip()
    if not target_username:
        return {'code': 400, 'message': '请指定用户名'}
    if target_username == 'admin':
        return {'code': 400, 'message': '不能注销管理员账号'}
    if target_username == admin_username:
        return {'code': 400, 'message': '不能注销当前登录的管理员账号'}
    row = _get_row(target_username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    with get_conn() as conn:
        conn.execute('DELETE FROM user_settings WHERE username=?', (target_username,))
        conn.execute('DELETE FROM detection_reports WHERE username=?', (target_username,))
        conn.execute('DELETE FROM users WHERE username=?', (target_username,))
    avatar_path = os.path.join(AVATAR_DIR, target_username + '.jpg')
    if os.path.isfile(avatar_path):
        try:
            os.remove(avatar_path)
        except OSError:
            pass
    return {'code': 200, 'message': '用户已注销'}


def admin_unbind_phone(admin_username, target_username):
    if not is_admin(admin_username):
        return {'code': 403, 'message': '仅管理员可操作'}
    target_username = (target_username or '').strip()
    row = _get_row(target_username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    if not row['phone']:
        return {'code': 400, 'message': '该用户未绑定手机'}
    if not row['email']:
        return {'code': 400, 'message': '手机与邮箱至少保留一项，请直接注销该用户'}
    with get_conn() as conn:
        conn.execute('UPDATE users SET phone=NULL, updated_at=? WHERE username=?', (_now(), target_username))
    return {'code': 200, 'message': '已解绑手机号', 'data': {'user': public_user(_get_row(target_username))}}


def admin_unbind_email(admin_username, target_username):
    if not is_admin(admin_username):
        return {'code': 403, 'message': '仅管理员可操作'}
    target_username = (target_username or '').strip()
    row = _get_row(target_username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    if not row['email']:
        return {'code': 400, 'message': '该用户未绑定邮箱'}
    if not row['phone']:
        return {'code': 400, 'message': '手机与邮箱至少保留一项，请直接注销该用户'}
    with get_conn() as conn:
        conn.execute('UPDATE users SET email=NULL, updated_at=? WHERE username=?', (_now(), target_username))
    return {'code': 200, 'message': '已解绑邮箱', 'data': {'user': public_user(_get_row(target_username))}}


def admin_set_password(admin_username, target_username, new_password):
    if not is_admin(admin_username):
        return {'code': 403, 'message': '仅管理员可操作'}
    target_username = (target_username or '').strip()
    new_password = (new_password or '').strip()
    if not target_username or not new_password:
        return {'code': 400, 'message': '请填写用户名和新密码'}
    if len(new_password) < 6:
        return {'code': 400, 'message': '新密码至少6位'}
    row = _get_row(target_username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    with get_conn() as conn:
        conn.execute('UPDATE users SET password=?, updated_at=? WHERE username=?', (new_password, _now(), target_username))
    return {'code': 200, 'message': '密码已更新'}


def admin_set_role(admin_username, target_username, role):
    if not is_admin(admin_username):
        return {'code': 403, 'message': '仅管理员可操作'}
    target_username = (target_username or '').strip()
    role = (role or '').strip().lower()
    if role not in ('user', 'member'):
        return {'code': 400, 'message': '仅可设置为普通用户或会员用户'}
    if target_username == 'admin':
        return {'code': 400, 'message': '不能修改管理员角色'}
    row = _get_row(target_username)
    if not row:
        return {'code': 404, 'message': '用户不存在'}
    with get_conn() as conn:
        conn.execute('UPDATE users SET role=?, updated_at=? WHERE username=?', (role, _now(), target_username))
    return {'code': 200, 'message': '角色已更新为' + _role_label(role), 'data': {'user': public_user(_get_row(target_username))}}


def list_all_users(admin_username):
    if not is_admin(admin_username):
        return {'code': 403, 'message': '仅管理员可查看'}
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT username, password, real_name, phone, email, role, theme, gender, work_unit, '
            'department, region, address, bio, created_at, updated_at FROM users ORDER BY username'
        ).fetchall()
    items = []
    for r in rows:
        role = r['role'] if 'role' in r.keys() and r['role'] else 'user'
        items.append({
            'username': r['username'],
            'password': r['password'],
            'realName': r['real_name'] or '',
            'phone': r['phone'] or '',
            'email': r['email'] or '',
            'role': role,
            'roleLabel': _role_label(role),
            'theme': r['theme'] or 'default',
            'gender': r['gender'] or '',
            'workUnit': r['work_unit'] or '',
            'department': r['department'] or '',
            'region': r['region'] or '',
            'address': r['address'] or '',
            'bio': r['bio'] or '',
            'createdAt': r['created_at'] or '',
            'updatedAt': r['updated_at'] or '',
            'phoneBound': bool(r['phone']),
            'emailBound': bool(r['email']),
        })
    return {'code': 200, 'data': {'items': items, 'total': len(items)}}


def save_user_setting(username, key, value):
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO user_settings (username, key, value) VALUES (?,?,?)',
            (username, key, value if isinstance(value, str) else json.dumps(value)),
        )
    return {'code': 200, 'message': '已保存'}


def get_user_settings(username):
    with get_conn() as conn:
        rows = conn.execute('SELECT key, value FROM user_settings WHERE username=?', (username,)).fetchall()
    data = {r['key']: r['value'] for r in rows}
    return {'code': 200, 'data': data}


def get_user_llm_settings(username):
    data = get_user_settings(username).get('data') or {}
    return {
        'api_url': data.get('llm_api_url', ''),
        'api_key': data.get('llm_api_key', ''),
        'model': data.get('llm_model', ''),
    }


def save_user_llm_settings(username, api_url=None, api_key=None, model=None):
    if not username:
        return {'code': 401, 'message': '请先登录'}
    current = get_user_llm_settings(username)
    url = (api_url or current.get('api_url') or '').strip()
    model_name = (model or current.get('model') or 'deepseek-chat').strip()
    key = (api_key or '').strip()
    if not key:
        key = current.get('api_key') or ''
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO user_settings (username, key, value) VALUES (?,?,?)',
            (username, 'llm_api_url', url),
        )
        conn.execute(
            'INSERT OR REPLACE INTO user_settings (username, key, value) VALUES (?,?,?)',
            (username, 'llm_api_key', key),
        )
        conn.execute(
            'INSERT OR REPLACE INTO user_settings (username, key, value) VALUES (?,?,?)',
            (username, 'llm_model', model_name),
        )
    return {'code': 200, 'message': '大模型配置已保存，可直接提问'}
