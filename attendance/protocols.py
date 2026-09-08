"""بروتوكولات أجهزة الحضور المدعومة."""

from __future__ import annotations

PROTOCOL_ADMS_ZKTECO = 'adms_zkteco'
PROTOCOL_WEBHOOK = 'webhook'
PROTOCOL_MANUAL = 'manual'

PROTOCOL_CHOICES: dict[str, str] = {
    PROTOCOL_ADMS_ZKTECO: 'ZKTeco ADMS/PUSH',
    PROTOCOL_WEBHOOK: 'API عام (HTTP)',
    PROTOCOL_MANUAL: 'إدخال يدوي',
}

PROTOCOL_HELP: dict[str, str] = {
    PROTOCOL_ADMS_ZKTECO: (
        'معظم أجهزة ZKTeco التي تدعم Cloud PUSH: uFace، SpeedFace، iFace، K40، MB…'
    ),
    PROTOCOL_WEBHOOK: (
        'أي جهاز أو تطبيق يرسل HTTP POST برمز الجهاز — Hikvision bridge، تطبيق جوال، سكربت…'
    ),
    PROTOCOL_MANUAL: 'تسجيل حضور/انصراف من LiftCore بدون جهاز بصمة.',
}


def protocol_label(protocol: str | None) -> str:
    key = (protocol or PROTOCOL_ADMS_ZKTECO).strip()
    return PROTOCOL_CHOICES.get(key, key)


def normalize_protocol(raw: str | None, default: str = PROTOCOL_ADMS_ZKTECO) -> str:
    key = (raw or default).strip()
    if key in PROTOCOL_CHOICES:
        return key
    return default
