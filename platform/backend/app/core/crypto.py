"""敏感字段加密 — 数据源密码等敏感配置的 Fernet 加解密.

生产环境应从 KMS (Vault/AWS KMS) 获取密钥，开发环境从环境变量读取。
"""

import os

from cryptography.fernet import Fernet

# 加密密钥 — 开发环境从 DATAOS_ENCRYPTION_KEY 环境变量读取
# 生成新密钥: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY = os.getenv("DATAOS_ENCRYPTION_KEY", "")
_fernet: Fernet | None = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None

# 需要加密的敏感字段名
SENSITIVE_KEYS = {
    "password", "secret", "token", "access_key",
    "private_key", "api_key", "connection_string",
}


def encrypt_config(config: dict) -> dict:
    """加密 datasource.config 中的敏感字段 (入库前调用).

    开发环境未配置加密密钥时，返回原值 (明文)。
    """
    if not _fernet:
        return config
    encrypted = {**config}
    for key in SENSITIVE_KEYS:
        if key in encrypted and encrypted[key]:
            encrypted[key] = _fernet.encrypt(
                str(encrypted[key]).encode()
            ).decode()
    return encrypted


def decrypt_config(config: dict) -> dict:
    """解密 datasource.config 中的敏感字段 (出库后调用).

    调用前应先检查权限并记录审计日志。
    """
    if not _fernet:
        return config
    decrypted = {**config}
    for key in SENSITIVE_KEYS:
        if key in decrypted and decrypted[key]:
            try:
                decrypted[key] = _fernet.decrypt(
                    decrypted[key].encode()
                ).decode()
            except Exception:
                # 可能是未加密的旧数据，跳过
                pass
    return decrypted


def is_crypto_available() -> bool:
    """检查加密模块是否就绪."""
    return _fernet is not None
