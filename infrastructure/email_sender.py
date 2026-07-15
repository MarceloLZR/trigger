"""
infrastructure.email_sender
--------------------------------
Envía correos electrónicos utilizando la aplicación de escritorio de Outlook (Windows).
"""
from __future__ import annotations
import os

from core.interfaces import IEmailSender


class EmailSender(IEmailSender):
    def send_email(self, to_addresses: str, subject: str, html_body: str, attachment_paths: list[str] = None) -> bool:
        try:
            import win32com.client
        except ImportError:
            raise ImportError("La librería pywin32 no está instalada. Ejecuta: pip install pywin32")

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0: olMailItem

        mail.To = to_addresses
        mail.Subject = subject
        mail.HTMLBody = html_body

        if attachment_paths:
            for attachment_path in attachment_paths:
                if os.path.exists(attachment_path):
                    mail.Attachments.Add(attachment_path)

        mail.Send()
        return True
