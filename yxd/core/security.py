# -*- coding: utf-8 -*-
"""密码哈希与登录会话签名。仅使用 Python 标准库。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

PBKDF2_ROUNDS = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, PBKDF2_ROUNDS)
    return "pbkdf2$%d$%s$%s" % (
        PBKDF2_ROUNDS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = (stored or "").split("$", 3)
        if algo != "pbkdf2":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        got = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def sign_session(payload: Dict[str, Any], secret: str, days: int = 7) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + days * 86400
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    data = b64url(raw)
    sig = hmac.new(secret.encode("utf-8"), data.encode("ascii"), hashlib.sha256).hexdigest()
    return data + "." + sig


def verify_session(token: str, secret: str) -> Optional[Dict[str, Any]]:
    try:
        data, sig = (token or "").rsplit(".", 1)
        expected = hmac.new(secret.encode("utf-8"), data.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        payload = json.loads(raw.decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def new_id(prefix: str = "", n: int = 10) -> str:
    alphabet = "23456789abcdefghjkmnpqrstuvwxyz"
    return (prefix or "") + "".join(secrets.choice(alphabet) for _ in range(n))


def new_number(prefix: str) -> str:
    """例如 BJ261107-8K3F。"""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    stamp = time.strftime("%y%m%d")
    suffix = "".join(secrets.choice(alphabet) for _ in range(4))
    return "%s%s-%s" % (prefix, stamp, suffix)


def mask_phone(phone: str) -> str:
    p = str(phone or "")
    if len(p) >= 7:
        return p[:3] + "****" + p[-4:]
    return p


def safe_filename(name: str) -> str:
    keep = []
    for ch in (name or ""):
        if ch.isalnum() or ch in "-_.":
            keep.append(ch)
    return "".join(keep)[-80:] or "file"
