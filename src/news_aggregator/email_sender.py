"""邮件发送模块"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailSender:
    """Gmail 邮件发送器"""

    def __init__(
        self,
        sender_email: str,
        app_password: str,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 465,
    ):
        """
        Args:
            sender_email: 发件人邮箱
            app_password: Gmail 应用专用密码
            smtp_server: SMTP 服务器
            smtp_port: SMTP 端口
        """
        self.sender_email = sender_email
        self.app_password = app_password.replace(" ", "")  # 移除空格
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port

    def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
    ) -> bool:
        """发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件正文
            is_html: 是否为 HTML 格式

        Returns:
            是否发送成功
        """
        try:
            # 创建邮件
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = to_email

            # 添加正文
            content_type = "html" if is_html else "plain"
            part = MIMEText(body, content_type, "utf-8")
            message.attach(part)

            # 发送
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                self.smtp_server, self.smtp_port, context=context
            ) as server:
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, to_email, message.as_string())

            logger.info(f"邮件已发送至 {to_email}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False


def send_email(
    sender: str,
    password: str,
    recipient: str,
    subject: str,
    body: str,
    is_html: bool = False,
) -> bool:
    """便捷发送函数"""
    sender_obj = EmailSender(sender, password)
    return sender_obj.send(recipient, subject, body, is_html)
