# SMTP 连通性测试（在项目根 web-flask 下运行）
import json
import os
import smtplib
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import email_configured, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_USE_SSL, SMTP_USE_TLS


def try_login(host, port, use_ssl, use_tls):
    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            smtp = smtplib.SMTP(host, port, timeout=20)
            if use_tls:
                smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.quit()
        return True, '登录成功'
    except smtplib.SMTPAuthenticationError as e:
        return False, '认证失败(535)：请使用 mail.aust.edu.cn 的客户端专用密码，不是网页登录密码'
    except Exception as e:
        return False, str(e)


def main():
    print('email_configured:', email_configured())
    print('user:', SMTP_USER)
    print('host:', SMTP_HOST, 'port:', SMTP_PORT)
    if not email_configured():
        print('未配置 smtp_pass，请编辑 data/email_config.json')
        return 1

    tests = [
        (SMTP_HOST, SMTP_PORT, SMTP_USE_SSL, SMTP_USE_TLS),
        ('smtp.exmail.qq.com', 465, True, False),
        ('smtp.exmail.qq.com', 587, False, True),
    ]
    seen = set()
    for host, port, ssl, tls in tests:
        key = (host, port, ssl, tls)
        if key in seen:
            continue
        seen.add(key)
        ok, msg = try_login(host, port, ssl, tls)
        print(f'[{host}:{port} ssl={ssl} tls={tls}]', 'OK' if ok else msg)

    from service.email_service import send_email
    r = send_email(SMTP_USER, '【测试】翊卫云瞳', '这是一封 SMTP 测试邮件。')
    print('send_email:', r)
    return 0 if r.get('code') == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
