"""공개 레포에 DB를 올리기 위한 암호화/복호화. 키 문자열은 임의 길이를 허용한다."""
import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet


def _fernet(passphrase: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest())
    return Fernet(key)


def encrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    dst.write_bytes(_fernet(passphrase).encrypt(src.read_bytes()))


def decrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    dst.write_bytes(_fernet(passphrase).decrypt(src.read_bytes()))
