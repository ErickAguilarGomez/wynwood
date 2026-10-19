import base64
from email.message import Message

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailError(Exception):
    pass


class ResendEmailBackend(BaseEmailBackend):
    api_url = "https://api.resend.com/emails"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = settings.RESEND_API_KEY
        if not self.api_key:
            raise ImproperlyConfigured("RESEND_API_KEY is required when using the Resend email backend")

    def send_messages(self, email_messages):
        sent_count = 0
        for message in email_messages:
            if self._send(message):
                sent_count += 1
        return sent_count

    def _send(self, message):
        if not message.recipients():
            return False

        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": message.to,
            "subject": message.subject,
        }
        if message.cc:
            payload["cc"] = message.cc
        if message.bcc:
            payload["bcc"] = message.bcc
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        if message.body:
            payload["text"] = message.body

        for alternative, mimetype in message.alternatives:
            if mimetype == "text/html":
                payload["html"] = alternative

        if message.extra_headers:
            payload["headers"] = message.extra_headers

        if message.attachments:
            payload["attachments"] = [self._encode_attachment(attachment) for attachment in message.attachments]

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            if self.fail_silently:
                return False
            status = getattr(getattr(error, "response", None), "status_code", None)
            detail = f"Resend API request failed with HTTP {status}" if status else "Resend API request failed"
            raise ResendEmailError(detail) from error
        return True

    @staticmethod
    def _encode_attachment(attachment):
        if isinstance(attachment, Message):
            content = attachment.get_payload(decode=True) or b""
            filename = attachment.get_filename() or "attachment"
        else:
            filename, content, _ = attachment
            if isinstance(content, str):
                content = content.encode()
        return {
            "filename": filename,
            "content": base64.b64encode(content).decode("ascii"),
        }
