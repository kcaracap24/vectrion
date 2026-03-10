"""
vectrion/cloud_vault.py — Optional cloud vault for encrypted off-machine file storage.

Supports any S3-compatible provider: AWS S3, Cloudflare R2, MinIO, DigitalOcean Spaces.

Files are AES-256 encrypted client-side (Fernet via HKDF-SHA256) before upload.
The encryption key material lives in {workdir}/vault_key.bin (chmod 600).

Three modes:
  local_only  — default, no cloud interaction
  mirror      — local file kept + encrypted copy in cloud
  cloud_only  — encrypted cloud copy only; local raw file deleted after upload
                (restored on-demand before Stage 1, re-deleted after)

Cloud objects are stored under the path:
  engagements/{engagement_id}/{filename}.enc

Limitation: entire file is loaded into memory for Fernet encryption.
Files larger than ~500 MB may cause memory pressure on constrained systems.

Install cloud dependencies:
  pip install vectrion[cloud]
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path


# ─── Encryption helpers ────────────────────────────────────────────────────────

def ensure_vault_key(workdir: str) -> bytes:
    """Load or generate the 32-byte raw vault key, stored in vault_key.bin (chmod 600)."""
    key_path = Path(workdir) / "vault_key.bin"
    if key_path.exists():
        data = key_path.read_bytes()
        if len(data) == 32:
            return data
    # Generate new key
    raw = os.urandom(32)
    key_path.write_bytes(raw)
    try:
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError:
        pass  # Windows / restricted env
    return raw


def get_fernet(workdir: str):
    """Return a Fernet instance whose key is derived via HKDF-SHA256 from vault_key.bin."""
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        import base64
    except ImportError:
        raise ImportError(
            "cryptography package not installed. "
            "Install with: pip install vectrion[cloud]"
        )

    raw = ensure_vault_key(workdir)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"vectrion-vault-v1",
    )
    derived = hkdf.derive(raw)
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_file(src: Path, workdir: str) -> bytes:
    """Read *src* and return a Fernet ciphertext token."""
    fernet = get_fernet(workdir)
    plaintext = Path(src).read_bytes()
    return fernet.encrypt(plaintext)


def decrypt_bytes(ciphertext: bytes, workdir: str) -> bytes:
    """Decrypt a Fernet ciphertext token and return plaintext bytes."""
    fernet = get_fernet(workdir)
    return fernet.decrypt(ciphertext)


# ─── S3 helpers ────────────────────────────────────────────────────────────────

def _make_s3_client(cfg: dict):
    """Build a boto3 S3 client from cloud_cfg. Empty endpoint_url → AWS S3."""
    try:
        import boto3
    except ImportError:
        raise ImportError(
            "boto3 package not installed. "
            "Install with: pip install vectrion[cloud]"
        )

    kwargs: dict = {
        "aws_access_key_id":     cfg.get("access_key", ""),
        "aws_secret_access_key": cfg.get("secret_key", ""),
        "region_name":           cfg.get("region", "us-east-1") or "us-east-1",
    }
    endpoint = cfg.get("endpoint_url", "").strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint

    return boto3.client("s3", **kwargs)


def upload_encrypted(
    src: Path,
    engagement_id: str,
    safe_filename: str,
    workdir: str,
    cloud_cfg: dict,
) -> str:
    """
    Encrypt *src* and upload to S3. Returns the cloud object key string.

    Object path: engagements/{engagement_id}/{safe_filename}.enc
    """
    s3 = _make_s3_client(cloud_cfg)
    bucket = cloud_cfg.get("bucket", "")
    if not bucket:
        raise ValueError("Cloud vault: bucket name is not configured")

    cloud_key = f"engagements/{engagement_id}/{safe_filename}.enc"
    ciphertext = encrypt_file(src, workdir)

    s3.put_object(
        Bucket=bucket,
        Key=cloud_key,
        Body=ciphertext,
        ContentType="application/octet-stream",
    )
    return cloud_key


def download_and_decrypt(
    cloud_key: str,
    workdir: str,
    cloud_cfg: dict,
    dest: Path,
) -> None:
    """Download encrypted object from S3 and write decrypted bytes to *dest*."""
    s3 = _make_s3_client(cloud_cfg)
    bucket = cloud_cfg.get("bucket", "")
    if not bucket:
        raise ValueError("Cloud vault: bucket name is not configured")

    resp = s3.get_object(Bucket=bucket, Key=cloud_key)
    ciphertext = resp["Body"].read()
    plaintext = decrypt_bytes(ciphertext, workdir)
    Path(dest).write_bytes(plaintext)


def delete_cloud_object(cloud_key: str, cloud_cfg: dict) -> None:
    """
    Delete the cloud object. Non-fatal: all errors are swallowed and logged to
    stderr so that local cleanup can proceed even if the cloud is unreachable.
    """
    try:
        s3 = _make_s3_client(cloud_cfg)
        bucket = cloud_cfg.get("bucket", "")
        if not bucket:
            return
        s3.delete_object(Bucket=bucket, Key=cloud_key)
    except Exception as exc:
        import sys
        print(f"[cloud_vault] WARNING: could not delete {cloud_key}: {exc}", file=sys.stderr)


def test_connection(cloud_cfg: dict) -> dict:
    """
    Verify connectivity by listing at most 1 object in the configured bucket.
    Returns {"ok": bool, "message": str}.
    """
    try:
        s3 = _make_s3_client(cloud_cfg)
        bucket = cloud_cfg.get("bucket", "")
        if not bucket:
            return {"ok": False, "message": "Bucket name is required"}
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        return {"ok": True, "message": f"Connected to bucket '{bucket}' successfully"}
    except ImportError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


# ─── Config helpers ────────────────────────────────────────────────────────────

_CLOUD_DEFAULTS: dict = {
    "enabled":      False,
    "mode":         "local_only",
    "endpoint_url": "",
    "bucket":       "",
    "access_key":   "",
    "secret_key":   "",
    "region":       "us-east-1",
}


def load_cloud_config(workdir: str) -> dict:
    """Read the 'cloud_vault' section from config.json (returns defaults if absent)."""
    config_path = Path(workdir) / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            stored = data.get("cloud_vault", {})
            return {**_CLOUD_DEFAULTS, **stored}
        except Exception:
            pass
    return dict(_CLOUD_DEFAULTS)


def save_cloud_config(workdir: str, cloud_cfg: dict) -> None:
    """Merge *cloud_cfg* into the 'cloud_vault' key of config.json."""
    config_path = Path(workdir) / "config.json"
    try:
        existing = json.loads(config_path.read_text()) if config_path.exists() else {}
    except Exception:
        existing = {}
    existing["cloud_vault"] = {**_CLOUD_DEFAULTS, **cloud_cfg}
    config_path.write_text(json.dumps(existing, indent=2))


def is_cloud_enabled(workdir: str) -> bool:
    """Return True if cloud vault is enabled and mode is not local_only."""
    cfg = load_cloud_config(workdir)
    return bool(cfg.get("enabled")) and cfg.get("mode", "local_only") != "local_only"
