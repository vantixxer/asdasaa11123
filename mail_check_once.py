"""Разовая проверка почты: пересылает новые непрочитанные письма в Telegram
и помечает их прочитанными. Рассчитан на запуск по расписанию (GitHub Actions).
Никаких внешних библиотек не нужно.
"""
import email
import imaplib
import os
import urllib.parse
import urllib.request
from email.header import decode_header, make_header

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]
IMAP_HOST = os.environ.get("IMAP_HOST") or "imap.gmail.com"
MAX_PER_RUN = 10  # защита от лавины писем при первом запуске


def decode(value) -> str:
    return str(make_header(decode_header(value or "")))


def decode_part(part) -> str:
    charset = part.get_content_charset() or "utf-8"
    payload = part.get_payload(decode=True) or b""
    return payload.decode(charset, errors="replace")


def get_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition", ""))
            if part.get_content_type() == "text/plain" and "attachment" not in disposition:
                return decode_part(part)
        return "(нет текстовой части)"
    return decode_part(msg)


def send_to_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text[:3500]}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30).read()


def main() -> None:
    sent = 0
    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        imap.select("INBOX")
        _, data = imap.uid("search", None, "UNSEEN")
        for uid in data[0].split()[-MAX_PER_RUN:]:
            _, msg_data = imap.uid("fetch", uid, "(BODY.PEEK[])")
            msg = email.message_from_bytes(msg_data[0][1])
            text = (
                f"📧 {decode(msg['Subject'])}\n"
                f"От: {decode(msg['From'])}\n\n"
                f"{get_text(msg).strip()}"
            )
            send_to_telegram(text)
            imap.uid("store", uid, "+FLAGS", "\\Seen")  # только после успешной отправки
            sent += 1
    print(f"Отправлено писем: {sent}")  # содержимое писем в лог не пишем


if __name__ == "__main__":
    main()
