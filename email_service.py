"""Sending certificates by email (SMTP).

The organiser types the sender address and an *app password* in the app. Nothing
is written to disk. One connection is opened for the whole batch.

Result of sending one message is one of:
  "sent"        the mail server accepted the message
  "failed"      the server refused it - safe to try again
  "unconfirmed" the connection broke while sending - the message MAY have gone
                out, so check the Sent folder before trying again
"""
from __future__ import annotations

import smtplib
import socket
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

PROVIDERS = {
    "Gmail / Google Workspace": {"host": "smtp.gmail.com", "port": 465, "security": "ssl"},
    "Outlook / Microsoft 365": {"host": "smtp.office365.com", "port": 587, "security": "starttls"},
    "Yahoo Mail": {"host": "smtp.mail.yahoo.com", "port": 465, "security": "ssl"},
    "Other (enter server details)": {"host": "", "port": 465, "security": "ssl"},
}

APP_PASSWORD_HELP = {
    "Gmail / Google Workspace": "Create one at myaccount.google.com/apppasswords (needs 2-Step Verification). "
                                "Your normal Gmail password will NOT work.",
    "Outlook / Microsoft 365": "Many Outlook/college accounts block this. Use an app password if your account allows it.",
    "Yahoo Mail": "Create an app password under Account security -> Generate app password.",
    "Other (enter server details)": "Use the SMTP details and password given by your email provider.",
}


def guess_provider(email: str) -> str:
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if domain in ("gmail.com", "googlemail.com"):
        return "Gmail / Google Workspace"
    if domain in ("outlook.com", "hotmail.com", "live.com", "office365.com", "msn.com") or domain.endswith(".onmicrosoft.com"):
        return "Outlook / Microsoft 365"
    if domain.startswith("yahoo.") or domain in ("ymail.com", "rocketmail.com"):
        return "Yahoo Mail"
    return "Gmail / Google Workspace" if domain else "Gmail / Google Workspace"


def clean_header(value: str) -> str:
    """Headers must be one line (also blocks header-injection tricks)."""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def build_message(sender: str, sender_name: str, recipient: str, subject: str, body: str,
                  pdf_bytes: bytes, filename: str, reply_to: str = "") -> EmailMessage:
    from email.headerregistry import Address

    message = EmailMessage()
    sender_name = clean_header(sender_name)
    user, _, domain = sender.partition("@")
    message["From"] = Address(display_name=sender_name, username=user, domain=domain)
    r_user, _, r_domain = recipient.partition("@")
    message["To"] = Address(username=r_user, domain=r_domain)
    message["Subject"] = clean_header(subject)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=domain or None)
    if reply_to:
        message["Reply-To"] = clean_header(reply_to)
    message.set_content(body)
    message.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
    return message


@dataclass
class SendResult:
    status: str            # sent | failed | unconfirmed
    detail: str = ""
    fatal: bool = False    # True -> stop the whole batch (bad login, daily limit...)


class Mailer:
    """Keeps one SMTP connection open for a whole batch (use as a context manager)."""

    def __init__(self, host: str, port: int, security: str, sender: str, password: str,
                 timeout: int = 30):
        self.host, self.port, self.security = host, int(port), security
        self.sender, self.password, self.timeout = sender, password, timeout
        self.server: smtplib.SMTP | None = None

    # -- connection -------------------------------------------------------
    def connect(self) -> None:
        context = ssl.create_default_context()
        if self.security == "ssl":
            server = smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=self.timeout)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            server.ehlo()
            if self.security == "starttls":
                server.starttls(context=context)
                server.ehlo()
        if self.password:
            server.login(self.sender, self.password)
        self.server = server

    def close(self) -> None:
        if self.server is not None:
            try:
                self.server.quit()
            except Exception:  # noqa: BLE001
                pass
            self.server = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # -- sending ----------------------------------------------------------
    def send(self, message: EmailMessage) -> SendResult:
        try:
            if self.server is None:
                self.connect()
            refused = self.server.send_message(message)
            if refused:
                return SendResult("failed", "Recipient refused by the server")
            return SendResult("sent", "Accepted by the mail server")
        except smtplib.SMTPRecipientsRefused as error:
            return SendResult("failed", "Address refused: " + _first_error(error))
        except smtplib.SMTPAuthenticationError:
            return SendResult("failed", "Login rejected - check the app password", fatal=True)
        except smtplib.SMTPSenderRefused as error:
            return SendResult("failed", f"Sender refused ({error.smtp_code})", fatal=True)
        except smtplib.SMTPDataError as error:
            text = _decode(error.smtp_error)
            fatal = error.smtp_code in (550, 552, 554) and any(
                w in text.lower() for w in ("limit", "quota", "exceeded"))
            return SendResult("failed", f"Server rejected the message ({error.smtp_code}): {text[:140]}", fatal=fatal)
        except (smtplib.SMTPServerDisconnected, TimeoutError, socket.timeout, ConnectionError, ssl.SSLError, OSError) as error:
            self.close()  # reconnect automatically for the next message
            return SendResult("unconfirmed", f"Connection lost while sending ({type(error).__name__}) - "
                                             "check the Sent folder before retrying")
        except smtplib.SMTPException as error:
            return SendResult("failed", f"Mail error: {error}")


def _decode(value) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def _first_error(error: smtplib.SMTPRecipientsRefused) -> str:
    for _, (code, text) in error.recipients.items():
        return f"{code} {_decode(text)[:120]}"
    return "refused"


def check_login(host: str, port: int, security: str, sender: str, password: str) -> tuple[bool, str]:
    """Log in without sending anything. Returns (ok, friendly message)."""
    try:
        with Mailer(host, port, security, sender, password, timeout=20):
            pass
        return True, "Login successful. Nothing was sent."
    except smtplib.SMTPAuthenticationError:
        return False, ("The server rejected the login. For Gmail you must use a 16-character App Password "
                       "(not your normal password) and 2-Step Verification must be on.")
    except (socket.gaierror, TimeoutError, socket.timeout, ConnectionError, ssl.SSLError, OSError) as error:
        return False, f"Could not connect to {host}:{port} ({type(error).__name__}). Check your internet and the server details."
    except smtplib.SMTPException as error:
        return False, f"Mail server error: {error}"


def pause(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)
