"""메일 발송 (Resend HTTP API).

- RESEND_API_KEY 가 있으면 실제로 보낸다.
- 키가 없으면: 개발·테스트 환경에서는 보내지 않고 OUTBOX 에 쌓아 화면·테스트에서 확인할 수 있게 하고,
  운영 환경에서는 MailError 를 낸다. 보내지 않은 메일을 보냈다고 표시하지 않기 위함.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import config

log = logging.getLogger("pgm.mail")

RESEND_URL = "https://api.resend.com/emails"


class MailError(Exception):
    pass


@dataclass
class Mail:
    to: str
    subject: str
    text: str
    html: str


OUTBOX: list[Mail] = []  # 개발·테스트용 (실제 발송하지 않은 메일)


def mail_enabled() -> bool:
    return bool(config.RESEND_API_KEY)


def send(mail: Mail) -> bool:
    """실제로 발송했으면 True, 개발용 보관함에만 넣었으면 False."""
    if not config.RESEND_API_KEY:
        if config.IS_PRODUCTION:
            raise MailError("메일 발송 설정(RESEND_API_KEY)이 없어 메일을 보내지 못했습니다.")
        OUTBOX.append(mail)
        log.warning("[개발용] 메일을 실제로 보내지 않았습니다 → %s: %s\n%s", mail.to, mail.subject, mail.text)
        return False
    body = json.dumps(
        {"from": config.MAIL_FROM, "to": [mail.to], "subject": mail.subject, "text": mail.text, "html": mail.html}
    ).encode("utf-8")
    req = urllib.request.Request(
        RESEND_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {config.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "public-goods-manage",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:  # noqa: S310 (고정 주소)
            if res.status >= 300:
                raise MailError(f"메일 서버 응답 {res.status}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        log.error("Resend 발송 실패 %s: %s", e.code, detail)
        if e.code == 403 and "domain" in detail.lower():
            raise MailError("보내는 메일 주소의 도메인이 Resend 에서 인증되지 않았습니다.") from e
        raise MailError(f"메일을 보내지 못했습니다 ({e.code}).") from e
    except urllib.error.URLError as e:
        raise MailError("메일 서버에 연결하지 못했습니다.") from e
    return True


def _layout(title: str, lines: list[str], button_text: str, url: str, footer: str) -> tuple[str, str]:
    paras = "".join(f'<p style="margin:0 0 12px;line-height:1.6">{line}</p>' for line in lines)
    html = f"""<!doctype html><html lang="ko"><body style="margin:0;background:#f6f8fb;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#0d1b33">
<div style="max-width:480px;margin:24px auto;background:#fff;border:1px solid #e1e8f2;border-radius:12px;padding:28px">
<p style="margin:0 0 4px;font-weight:700;color:#0f766e">public goods manage</p>
<h1 style="margin:0 0 16px;font-size:20px">{title}</h1>
{paras}
<p style="margin:20px 0"><a href="{url}" style="display:inline-block;background:#0f766e;color:#fff;text-decoration:none;font-weight:700;padding:12px 20px;border-radius:8px">{button_text}</a></p>
<p style="margin:0 0 12px;font-size:12px;color:#4a6188;word-break:break-all">버튼이 눌리지 않으면 이 주소를 복사해 열어 주세요:<br>{url}</p>
<p style="margin:16px 0 0;font-size:12px;color:#4a6188">{footer}</p>
</div></body></html>"""
    text = "\n".join([title, "", *lines, "", f"{button_text}: {url}", "", footer])
    return text, html


def verification_mail(to: str, name: str, url: str) -> Mail:
    text, html = _layout(
        "이메일 주소를 인증해 주세요",
        [f"{name}님, 가입해 주셔서 고맙습니다.", f"아래 버튼을 누르면 인증이 끝나고 로그인할 수 있습니다. 링크는 {config.VERIFY_TOKEN_HOURS}시간 동안 쓸 수 있어요."],
        "이메일 인증하기",
        url,
        "직접 가입하지 않았다면 이 메일을 무시하세요. 계정은 인증 전까지 사용할 수 없습니다.",
    )
    return Mail(to, "[public goods manage] 이메일 인증", text, html)


def reset_mail(to: str, name: str, url: str) -> Mail:
    text, html = _layout(
        "비밀번호 재설정",
        [f"{name}님, 비밀번호 재설정을 요청하셨습니다.", f"아래 버튼을 눌러 새 비밀번호를 정해 주세요. 링크는 {config.RESET_TOKEN_MINUTES}분 동안 한 번만 쓸 수 있어요."],
        "새 비밀번호 정하기",
        url,
        "직접 요청하지 않았다면 이 메일을 무시하세요. 비밀번호는 바뀌지 않습니다.",
    )
    return Mail(to, "[public goods manage] 비밀번호 재설정", text, html)
