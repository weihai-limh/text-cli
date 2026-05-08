"""
邮件 handler mixin。
"""

import email.mime.multipart
import email.mime.text
import email.mime.base
import email.encoders
import smtplib
from core import ok, error


class MailHandlers:
    """邮件;发送"""

    def _handle_email_send(self, params: list) -> dict:
        if len(params) < 3:
            return error('missing_param',
                        '缺少参数: 收件人, 主题, 正文 (可选: 附件路径)')
        to_addr = params[0]
        subject = params[1]
        body = params[2]
        attachment_path = params[3] if len(params) > 3 else None

        creds = self.config.get('credentials', {})
        mail_cfg = creds.get('邮件;发送', {})

        smtp_host = mail_cfg.get('smtp_host', 'smtp.mxhichina.com')
        smtp_port = mail_cfg.get('smtp_port', 465)
        smtp_user = mail_cfg.get('smtp_user', '')
        smtp_password = mail_cfg.get('value', '')
        from_email = mail_cfg.get('from_email', smtp_user)

        if not smtp_password:
            return error('missing_credential',
                        'SMTP 密码未配置。请设置环境变量 SMTP_PASSWORD')

        # 构建 MIME 邮件
        msg = email.mime.multipart.MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(email.mime.text.MIMEText(body, 'plain', 'utf-8'))

        # 附件
        if attachment_path:
            p = self.check_path(attachment_path)
            if p is None:
                return error('path_denied',
                            f'附件路径不在白名单内: {attachment_path}')
            if not p.is_file():
                return error('file_not_found',
                            f'附件文件不存在: {attachment_path}')
            try:
                with open(p, 'rb') as f:
                    part = email.mime.base.MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                email.encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{p.name}"'
                )
                msg.attach(part)
            except Exception as e:
                return error('attachment_error', f'附件读取失败: {e}')

        # SMTP 发送
        try:
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.starttls()

            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [to_addr], msg.as_string())
            server.quit()

            return ok(f'邮件已发送至 {to_addr}',
                     subject=subject, from_addr=from_email)
        except smtplib.SMTPAuthenticationError:
            return error('smtp_auth_failed',
                        f'SMTP 认证失败: {smtp_user}@{smtp_host}')
        except smtplib.SMTPConnectError:
            return error('smtp_connect_failed',
                        f'无法连接到 SMTP 服务器: {smtp_host}:{smtp_port}')
        except smtplib.SMTPException as e:
            return error('smtp_error', f'SMTP 错误: {e}')
        except Exception as e:
            return error('internal_error', f'邮件发送异常: {e}')
