# 系统配置：模型路径与类别映射
import os

WEB_FLASK_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(WEB_FLASK_DIR, 'users.json')
DATABASE_PATH = os.path.join(WEB_FLASK_DIR, 'data', 'app.db')
AVATAR_DIR = os.path.join(WEB_FLASK_DIR, 'templates', 'images', 'avatars')

# 开发模式：未配置短信时仅在服务端控制台打印验证码（不在页面展示）
DEV_MODE = True
SMS_CODE_TTL = 300
CODE_SEND_COOLDOWN = 60
SMS_CONFIG_PATH = os.path.join(WEB_FLASK_DIR, 'data', 'sms_config.json')


def _load_sms_config():
    cfg = {}
    if os.path.isfile(SMS_CONFIG_PATH):
        try:
            with open(SMS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                import json
                cfg = json.load(f)
        except Exception:
            pass
    key_id = os.environ.get('SMS_ACCESS_KEY_ID') or cfg.get('access_key_id') or ''
    key_secret = os.environ.get('SMS_ACCESS_KEY_SECRET') or cfg.get('access_key_secret') or ''
    sign_name = os.environ.get('SMS_SIGN_NAME') or cfg.get('sign_name') or ''
    template_code = os.environ.get('SMS_TEMPLATE_CODE') or cfg.get('template_code') or ''
    region_id = os.environ.get('SMS_REGION_ID') or cfg.get('region_id') or 'cn-hangzhou'
    scheme_name = os.environ.get('SMS_SCHEME_NAME') or cfg.get('scheme_name') or ''
    code_length = int(os.environ.get('SMS_CODE_LENGTH') or cfg.get('code_length') or 6)
    valid_time = int(os.environ.get('SMS_VALID_TIME') or cfg.get('valid_time') or 300)
    code_type = int(os.environ.get('SMS_CODE_TYPE') or cfg.get('code_type') or 1)
    return (
        key_id.strip(),
        key_secret.strip(),
        sign_name.strip(),
        template_code.strip(),
        region_id.strip(),
        scheme_name.strip(),
        code_length,
        valid_time,
        code_type,
    )


(
    SMS_ACCESS_KEY_ID,
    SMS_ACCESS_KEY_SECRET,
    SMS_SIGN_NAME,
    SMS_TEMPLATE_CODE,
    SMS_REGION_ID,
    SMS_SCHEME_NAME,
    SMS_CODE_LENGTH,
    SMS_VALID_TIME,
    SMS_CODE_TYPE,
) = _load_sms_config()

# 邮件 SMTP（填写 data/email_config.json 或环境变量 SMTP_*）
EMAIL_CONFIG_PATH = os.path.join(WEB_FLASK_DIR, 'data', 'email_config.json')


def _load_email_config():
    cfg = {}
    if os.path.isfile(EMAIL_CONFIG_PATH):
        try:
            with open(EMAIL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                import json
                cfg = json.load(f)
        except Exception:
            pass
    host = (os.environ.get('SMTP_HOST') or cfg.get('smtp_host') or '').strip()
    port = int(os.environ.get('SMTP_PORT') or cfg.get('smtp_port') or 465)
    user = (os.environ.get('SMTP_USER') or cfg.get('smtp_user') or '').strip()
    password = (os.environ.get('SMTP_PASS') or cfg.get('smtp_pass') or '').strip()
    if password.startswith('请填写'):
        password = ''
    from_addr = (os.environ.get('SMTP_FROM') or cfg.get('smtp_from') or user).strip()
    use_ssl = cfg.get('use_ssl')
    if use_ssl is None:
        use_ssl = port == 465
    use_tls = cfg.get('use_tls')
    if use_tls is None:
        use_tls = port == 587 and not use_ssl
    return host, port, user, password, from_addr, bool(use_ssl), bool(use_tls)


SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_USE_SSL, SMTP_USE_TLS = _load_email_config()


def reload_email_config():
    """重新读取 email_config.json（修改配置后无需重启进程）。"""
    global SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_USE_SSL, SMTP_USE_TLS
    (
        SMTP_HOST,
        SMTP_PORT,
        SMTP_USER,
        SMTP_PASS,
        SMTP_FROM,
        SMTP_USE_SSL,
        SMTP_USE_TLS,
    ) = _load_email_config()


def email_configured():
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS)

# 大模型：优先读 data/llm_config.json，其次环境变量
LLM_CONFIG_PATH = os.path.join(WEB_FLASK_DIR, 'data', 'llm_config.json')


def _load_llm_config():
    cfg = {}
    if os.path.isfile(LLM_CONFIG_PATH):
        try:
            with open(LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
                import json
                cfg = json.load(f)
        except Exception:
            pass
    url = os.environ.get('LLM_API_URL') or cfg.get('api_url') or ''
    key = os.environ.get('LLM_API_KEY') or cfg.get('api_key') or ''
    model = os.environ.get('LLM_MODEL') or cfg.get('model') or 'deepseek-chat'
    if key and '填写' in key:
        key = ''
    return url.strip(), key.strip(), model.strip()


LLM_API_URL, LLM_API_KEY, LLM_MODEL = _load_llm_config()

MEMBER_LLM_CONFIG_PATH = os.path.join(WEB_FLASK_DIR, 'data', 'member_llm_config.json')


def _load_member_llm_config():
    cfg = {}
    if os.path.isfile(MEMBER_LLM_CONFIG_PATH):
        try:
            with open(MEMBER_LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
                import json
                cfg = json.load(f)
        except Exception:
            pass
    url = (os.environ.get('MEMBER_LLM_API_URL') or cfg.get('api_url') or LLM_API_URL or '').strip()
    key = (os.environ.get('MEMBER_LLM_API_KEY') or cfg.get('api_key') or '').strip()
    model = (os.environ.get('MEMBER_LLM_MODEL') or cfg.get('model') or LLM_MODEL or 'deepseek-chat').strip()
    if key and '填写' in key:
        key = ''
    return url, key, model


MEMBER_LLM_API_URL, MEMBER_LLM_API_KEY, MEMBER_LLM_MODEL = _load_member_llm_config()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_BASE_PATH = os.path.join(BASE_DIR, 'other', 'model_train', 'detect', 'output')

MODEL_CONFIGS = {
    'ready-model': {
        'name': 'YOLO12 检测模型(已经训练好的模型)',
        'model_path': os.path.join(
            MODEL_BASE_PATH, '已经训练好的模型和测试结果', 'train', 'weights', 'best.pt'
        ),
        'train_results_path': os.path.join(
            MODEL_BASE_PATH, '已经训练好的模型和测试结果', 'train', 'results.csv'
        ),
        'val_data_path': os.path.join(
            MODEL_BASE_PATH, '已经训练好的模型和测试结果', 'val'
        ),
        'val_accuracy_path': os.path.join(
            MODEL_BASE_PATH, '已经训练好的模型和测试结果', 'val', '测试集精度.txt'
        ),
    },
    'training-model': {
        'name': 'YOLO12 检测模型(新训练的模型)',
        'model_path': os.path.join(MODEL_BASE_PATH, 'train', 'weights', 'best.pt'),
        'train_results_path': os.path.join(MODEL_BASE_PATH, 'train', 'results.csv'),
        'val_data_path': os.path.join(MODEL_BASE_PATH, 'val'),
        'val_accuracy_path': os.path.join(MODEL_BASE_PATH, 'val', '测试集精度.txt'),
    }
}

CLASS_NAME_MAPPING = {
    'airplane': '飞机',
    'ship': '船舶',
    'storage_tank': '储油罐',
    'baseball_diamond': '棒球场',
    'tennis_court': '网球场',
    'basketball_court': '篮球场',
    'ground_track_field': '田径场',
    'harbor': '港口',
    'bridge': '桥梁',
    'vehicle': '车辆',
}

AVAILABLE_MODELS = [
    {
        'key': key,
        'name': cfg['name'],
        'model_path': cfg['model_path'],
        'train_results_path': cfg.get('train_results_path'),
        'val_data_path': cfg.get('val_data_path'),
        'val_accuracy_path': cfg.get('val_accuracy_path'),
        'num_classes': len(CLASS_NAME_MAPPING),
        'supported_classes': list(CLASS_NAME_MAPPING.values()),
    }
    for key, cfg in MODEL_CONFIGS.items()
]

DEFAULT_MODEL = 'ready-model'

THEME_OPTIONS = [
    {'key': 'default', 'name': '经典红（默认）'},
    {'key': 'ocean', 'name': '海洋蓝'},
    {'key': 'forest', 'name': '森林绿'},
    {'key': 'dark', 'name': '深色模式'},
]
