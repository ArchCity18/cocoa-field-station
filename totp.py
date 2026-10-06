"""TOTP enrollment and encrypted secret helpers for the Streamlit login flow."""
import base64
import hashlib
import hmac
import io
import secrets
import time
from urllib.parse import quote

import qrcode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def provisioning_uri(secret, email):
    label = quote(f"Cocoa Field Station:{email}", safe="")
    return (f"otpauth://totp/{label}?secret={secret}&issuer=Cocoa%20Field%20Station"
            "&algorithm=SHA1&digits=6&period=30")


def qr_image(uri):
    output = io.BytesIO()
    qrcode.make(uri).save(output, format="PNG")
    output.seek(0)
    return output


def code_for_counter(secret, counter):
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF) % 1_000_000
    return f"{number:06d}"


def verify_code(secret, code, now=None):
    code = str(code).strip()
    if len(code) != 6 or not code.isdecimal():
        return False
    counter = int((time.time() if now is None else now) // 30)
    return any(hmac.compare_digest(code_for_counter(secret, counter + drift), code)
               for drift in (-1, 0, 1))


def _encryption_key(cookie_secret):
    return hashlib.sha256(b"cocoa-field-station/totp/v1:" + cookie_secret.encode("utf-8")).digest()


def encrypt_secret(secret, cookie_secret):
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_encryption_key(cookie_secret)).encrypt(nonce, secret.encode("ascii"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(encrypted, cookie_secret):
    data = base64.b64decode(encrypted, validate=True)
    nonce, ciphertext = data[:12], data[12:]
    return AESGCM(_encryption_key(cookie_secret)).decrypt(nonce, ciphertext, None).decode("ascii")
