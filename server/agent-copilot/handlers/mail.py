"""
Mail handler mixin.
"""

import email.mime.multipart
import email.mime.text
import email.mime.base
import email.encoders
import smtplib
from core import ok, error


class MailHandlers:
    """email;send (aliases: mail;send, 邮件;发送)"""

    def _handle_email_send(self, params: list) -> dict:
        if len(params) < 3:
            return error('missing_param',
                        'Missing parameter: to, subject, body (optional: attachment_path)')
        to_addr = params[0]
        subject = params[1]
        body = params[2]
        attachment_path = None
        if len(params) > 3:
            # Last param might be an actual attachment path, or body text split by comma
            # Only treat as attachment path if it starts with / or ./
            extra = params[3].strip()
            if extra and (extra.startswith('/') or extra.startswith('./')):
                attachment_path = extra
            elif extra:
                # Not a path → merge back into body
                body += ', ' + extra

        creds = self.config.get('credentials', {})
        mail_cfg = creds.get('email;send', {})

        smtp_host = mail_cfg.get('smtp_host', 'smtp.mxhichina.com')
        smtp_port = mail_cfg.get('smtp_port', 465)
        smtp_user = mail_cfg.get('smtp_user', '')
        from_email = mail_cfg.get('from_email', smtp_user)

        # Three-tier priority: injected creds → key_registry → config
        smtp_password = None

        # 1. Injected creds (from service proxy)
        if self._injected_creds:
            smtp_password = self._injected_creds.get('smtp-tide')

        # 2. key_registry
        if not smtp_password:
            try:
                kr = getattr(self, 'key_registry', None)
                if kr:
                    smtp_password = kr.get('smtp-tide')
            except Exception:
                pass

        # 3. Config fallback
        if not smtp_password:
            smtp_password = mail_cfg.get('value', '')

        if not smtp_password:
            return error('missing_credential',
                        'SMTP password not configured. Register via 指令:key;register,smtp-tide,<cipher>,smtp_password'
                        ' or set SMTP_PASSWORD env var')

        # Build MIME message
        msg = email.mime.multipart.MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(email.mime.text.MIMEText(body, 'plain', 'utf-8'))

        # Attachment
        if attachment_path:
            p = self.check_path(attachment_path)
            if p is None:
                return error('path_denied',
                            f'Attachment path not in whitelist: {attachment_path}')
            if not p.is_file():
                return error('file_not_found',
                            f'Attachment file not found: {attachment_path}')
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
                return error('attachment_error', f'Attachment read failed: {e}')

        # SMTP send
        try:
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.starttls()

            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, [to_addr], msg.as_string())
            server.quit()

            return ok(f'Mail sent to {to_addr}',
                     subject=subject, from_addr=from_email)
        except smtplib.SMTPAuthenticationError:
            return error('smtp_auth_failed',
                        f'SMTP auth failed: {smtp_user}@{smtp_host}')
        except smtplib.SMTPConnectError:
            return error('smtp_connect_failed',
                        f'Cannot connect to SMTP server: {smtp_host}:{smtp_port}')
        except smtplib.SMTPException as e:
            return error('smtp_error', f'SMTP error: {e}')
        except Exception as e:
            return error('internal_error', f'Mail send error: {e}')
