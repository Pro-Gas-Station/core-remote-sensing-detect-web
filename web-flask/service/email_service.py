# 邮件发送（SMTP）
import logging
import os
import re
import smtplib
from email.header import Header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr

from config import (
    DEV_MODE,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USER,
    WEB_FLASK_DIR,
    email_configured,
    reload_email_config,
)

logger = logging.getLogger(__name__)

SMTP_CONNECT_TIMEOUT = 10
_email_config_mtime = 0.0
TEAM_NAME = '翊卫云瞳'
TEAM_NAME_EN = 'YIWEIYUNTONG'
TEAM_LOGO = os.path.join(WEB_FLASK_DIR, 'templates', 'images', 'web', 'team_logo.png')


def maybe_reload_email_config():
    """仅在配置文件变更时重新加载，避免每次发信读盘。"""
    global _email_config_mtime
    try:
        mtime = os.path.getmtime(os.path.join(WEB_FLASK_DIR, 'data', 'email_config.json'))
    except OSError:
        return
    if mtime != _email_config_mtime:
        _email_config_mtime = mtime
        reload_email_config()


def _smtp_auth_hint():
    if 'exmail.qq.com' in (SMTP_HOST or '') or (SMTP_USER or '').endswith('@aust.edu.cn'):
        return (
            ' 请确认：① mail.aust.edu.cn 已开启 POP3/SMTP '
            '② smtp_pass 为客户端专用密码（完整邮箱作 smtp_user）'
            '③ 修改配置后保存即可，若仍失败请 restart.bat 重启 Flask。'
        )
    return ' 请确认 smtp_pass 为 SMTP 授权码/客户端专用密码。'


def _parse_from_config():
    """解析 smtp_from 配置，返回 (显示名, 邮箱地址)。"""
    addr = (SMTP_USER or '').strip()
    display = TEAM_NAME
    raw = (SMTP_FROM or '').strip()
    if raw:
        m = re.match(r'^(.+?)\s*<([^>]+)>$', raw)
        if m:
            display = m.group(1).strip().strip('"\'')
            addr = m.group(2).strip()
        elif '@' in raw:
            addr = raw
        else:
            display = raw
    return display or TEAM_NAME, addr or SMTP_USER


def _build_from_header():
    display, addr = _parse_from_config()
    return formataddr((str(Header(display, 'utf-8')), addr))


def _brand_html(title, lines, highlight=None):
    """生成带 Logo 的 HTML 邮件正文。"""
    body_lines = ''.join('<p style="margin:0 0 10px;line-height:1.7;color:#333;">' + line + '</p>' for line in lines)
    code_block = ''
    if highlight:
        code_block = (
            '<p style="margin:18px 0;text-align:center;">'
            '<span style="display:inline-block;padding:12px 24px;font-size:28px;'
            'letter-spacing:6px;font-weight:700;color:#6b21a8;background:#f3e8ff;'
            'border-radius:8px;border:1px solid #d8b4fe;">' + highlight + '</span></p>'
        )
    logo_html = (
        '<td style="width:56px;vertical-align:middle;">'
        '<div style="width:48px;height:48px;border-radius:10px;background:#7c3aed;'
        'color:#fff;font-size:11px;line-height:48px;text-align:center;font-weight:700;">'
        + TEAM_NAME[:2] + '</div></td>'
    )
    if os.path.isfile(TEAM_LOGO):
        logo_html = (
            '<td style="width:56px;vertical-align:middle;">'
            '<img src="cid:team_logo" alt="' + TEAM_NAME + '" '
            'style="width:48px;height:48px;border-radius:10px;display:block;" />'
            '</td>'
        )
    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f5f5f5;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="background:#f5f5f5;padding:24px 12px;"><tr><td align="center">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="max-width:560px;background:#fff;border-radius:12px;overflow:hidden;'
        'box-shadow:0 2px 12px rgba(0,0,0,.08);">'
        '<tr><td style="background:linear-gradient(135deg,#7c3aed,#9333ea);padding:20px 24px;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>'
        + logo_html +
        '<td style="vertical-align:middle;padding-left:12px;">'
        '<div style="font-size:20px;font-weight:700;color:#fff;">' + TEAM_NAME + '</div>'
        '<div style="font-size:11px;color:#ede9fe;letter-spacing:2px;margin-top:2px;">'
        + TEAM_NAME_EN + '</div></td></tr></table></td></tr>'
        '<tr><td style="padding:24px;">'
        '<h2 style="margin:0 0 16px;font-size:18px;color:#111;">' + title + '</h2>'
        + body_lines + code_block +
        '<p style="margin:20px 0 0;font-size:12px;color:#999;line-height:1.6;">'
        '遥感影像目标检测系统 · ' + TEAM_NAME + '<br/>如非本人操作，请忽略此邮件。</p>'
        '</td></tr></table></td></tr></table></body></html>'
    )


def _attach_branded_body(msg, subject_title, plain_body, html_body):
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(plain_body, 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    related = MIMEMultipart('related')
    related.attach(alt)
    if os.path.isfile(TEAM_LOGO) and 'cid:team_logo' in html_body:
        with open(TEAM_LOGO, 'rb') as f:
            img = MIMEImage(f.read(), _subtype='png')
        img.add_header('Content-ID', '<team_logo>')
        img.add_header('Content-Disposition', 'inline', filename='team_logo.png')
        related.attach(img)
    msg.attach(related)


def _smtp_connect_and_send(to_addr, msg_string):
    """使用配置的 SMTP；仅在失败时尝试备用端口。"""
    maybe_reload_email_config()
    if SMTP_USE_SSL:
        primary = (SMTP_HOST, SMTP_PORT, True, False)
    else:
        primary = (SMTP_HOST, SMTP_PORT, False, SMTP_USE_TLS)

    attempts = [primary]
    if primary[1] == 465:
        attempts.append((SMTP_HOST, 587, False, True))
    elif primary[1] == 587:
        attempts.append((SMTP_HOST, 465, True, False))

    last_err = None
    for host, port, use_ssl, use_tls in attempts:
        try:
            if use_ssl:
                smtp = smtplib.SMTP_SSL(host, port, timeout=SMTP_CONNECT_TIMEOUT)
            else:
                smtp = smtplib.SMTP(host, port, timeout=SMTP_CONNECT_TIMEOUT)
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, [to_addr], msg_string)
            smtp.quit()
            logger.info('email sent via %s:%s to %s', host, port, to_addr)
            print('[EMAIL OK]', host, port, '->', to_addr)
            return True, None
        except smtplib.SMTPAuthenticationError as e:
            last_err = e
            print('[EMAIL AUTH FAIL]', host, port, e.smtp_code, e.smtp_error)
            break
        except Exception as e:
            last_err = e
            print('[EMAIL RETRY]', host, port, str(e))
    return False, last_err


def send_email(to_addr, subject, body, attachment=None, attachment_name='report.pdf', html_body=None):
    maybe_reload_email_config()
    if not to_addr:
        return {'code': 400, 'message': '收件邮箱为空'}

    if not email_configured():
        if DEV_MODE:
            print('[EMAIL 开发模式]', to_addr, subject, body[:200])
            return {
                'code': 200,
                'message': '邮件已模拟发送（未配置 SMTP，验证码见服务端控制台）',
                'dev_mode': True,
            }
        return {
            'code': 503,
            'message': '邮箱服务未配置。请编辑 data/email_config.json 填写 smtp_pass。',
        }

    try:
        msg = MIMEMultipart()
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = _build_from_header()
        msg['To'] = to_addr
        if html_body:
            _attach_branded_body(msg, subject.replace('【翊卫云瞳】', '').strip(), body, html_body)
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        if attachment:
            part = MIMEApplication(attachment)
            part.add_header('Content-Disposition', 'attachment', filename=attachment_name)
            msg.attach(part)

        ok, err = _smtp_connect_and_send(to_addr, msg.as_string())
        if ok:
            return {'code': 200, 'message': '邮件已发送'}
        if isinstance(err, smtplib.SMTPAuthenticationError):
            return {'code': 500, 'message': 'SMTP 登录失败：' + _smtp_auth_hint()}
        return {'code': 500, 'message': '邮件发送失败：' + str(err)}
    except smtplib.SMTPAuthenticationError:
        return {'code': 500, 'message': 'SMTP 登录失败：' + _smtp_auth_hint()}
    except smtplib.SMTPException as e:
        return {'code': 500, 'message': '邮件发送失败（SMTP）：' + str(e)}
    except Exception as e:
        return {'code': 500, 'message': '邮件发送失败：' + str(e)}


def send_verification_email(to_addr, code, ttl_min=5):
    """发送验证码邮件（轻量 HTML，无 Logo 附件，加快构建与发送）。"""
    maybe_reload_email_config()
    if not to_addr:
        return {'code': 400, 'message': '收件邮箱为空'}

    if not email_configured():
        if DEV_MODE:
            print('[EMAIL 开发模式]', to_addr, '验证码', code)
            return {
                'code': 200,
                'message': '邮件已模拟发送（未配置 SMTP，验证码见服务端控制台）',
                'dev_mode': True,
            }
        return {
            'code': 503,
            'message': '邮箱服务未配置。请编辑 data/email_config.json 填写 smtp_pass。',
        }

    subject = '【翊卫云瞳】邮箱验证码'
    plain = (
        '您正在使用遥感影像目标检测系统，验证码为：' + code + '。\n'
        + str(ttl_min) + ' 分钟内有效，请勿泄露给他人。\n\n如非本人操作，请忽略此邮件。'
    )
    html = _brand_html(
        '邮箱验证码',
        ['您正在使用遥感影像目标检测系统，请使用以下验证码完成验证：'],
        highlight=code,
    )
    html = html.replace(
        '如非本人操作，请忽略此邮件。',
        str(ttl_min) + ' 分钟内有效，请勿泄露给他人。<br/>如非本人操作，请忽略此邮件。',
    )

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = _build_from_header()
        msg['To'] = to_addr
        msg.attach(MIMEText(plain, 'plain', 'utf-8'))
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        ok, err = _smtp_connect_and_send(to_addr, msg.as_string())
        if ok:
            return {'code': 200, 'message': '邮件已发送'}
        if isinstance(err, smtplib.SMTPAuthenticationError):
            return {'code': 500, 'message': 'SMTP 登录失败：' + _smtp_auth_hint()}
        return {'code': 500, 'message': '邮件发送失败：' + str(err)}
    except smtplib.SMTPAuthenticationError:
        return {'code': 500, 'message': 'SMTP 登录失败：' + _smtp_auth_hint()}
    except smtplib.SMTPException as e:
        return {'code': 500, 'message': '邮件发送失败（SMTP）：' + str(e)}
    except Exception as e:
        return {'code': 500, 'message': '邮件发送失败：' + str(e)}
