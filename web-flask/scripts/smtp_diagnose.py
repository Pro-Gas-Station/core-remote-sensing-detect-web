# -*- coding: utf-8 -*-
"""SMTP 诊断：在 web-flask 目录运行 python scripts/smtp_diagnose.py"""
import json
import os
import smtplib
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CFG_PATH = os.path.join(ROOT, 'data', 'email_config.json')


def load_cfg():
    with open(CFG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def try_auth(host, port, user, pwd, use_ssl, use_tls):
    label = f'{host}:{port} ssl={use_ssl} tls={use_tls}'
    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=25)
        else:
            smtp = smtplib.SMTP(host, port, timeout=25)
        smtp.set_debuglevel(0)
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(user, pwd)
        smtp.quit()
        return label, True, 'login ok'
    except smtplib.SMTPAuthenticationError as e:
        return label, False, f'auth fail: {e.smtp_code} {e.smtp_error!r}'
    except Exception as e:
        return label, False, str(e)


def main():
    cfg = load_cfg()
    user = cfg.get('smtp_user', '').strip()
    pwd = cfg.get('smtp_pass', '').strip()
    print('user:', user)
    print('pass_len:', len(pwd))
    hosts = [
        ('smtp.exmail.qq.com', 465, True, False),
        ('smtp.exmail.qq.com', 587, False, True),
        ('hwsmtp.exmail.qq.com', 465, True, False),
        ('smtp.qq.com', 465, True, False),
    ]
  # also try username variants
    users = [user]
    if user and '@' in user:
        users.append(user.split('@')[0])

    results = []
    for host, port, ssl, tls in hosts:
        for u in users:
            label, ok, msg = try_auth(host, port, u, pwd, ssl, tls)
            results.append((f'{label} user={u}', ok, msg))

    out = os.path.join(ROOT, 'data', 'smtp_diagnose_result.txt')
    with open(out, 'w', encoding='utf-8') as f:
        for line, ok, msg in results:
            f.write(f'{"OK" if ok else "FAIL"} | {line} | {msg}\n')
    print('written', out)
    for line, ok, msg in results:
        if ok:
            print('OK', line)


if __name__ == '__main__':
    main()
