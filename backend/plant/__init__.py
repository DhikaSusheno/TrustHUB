"""TrustHUB plant knowledge layer (CALIBER 2026 Case 1).

Paket ini mengubah dataset CALIBER "Manufacturing Knowledge Hub" menjadi
knowledge hub berbasis equipment-tag:

    dataset/      lokasi + validasi dataset
    extract       PDF/PNG/xlsx -> sections + metadata asli (doc no, rev, approval)
    registry      document registry + equipment graph di SQLite
    retrieval     hybrid retrieval (SQLite FTS5 lokal, tanpa API key)
    trust         trust score, badge, guardrail safety-critical
    conflicts     deteksi nilai yang bertentangan antar dokumen
    failure_memory  hubungkan breakdown ke OPL + tindakan sebelumnya
    ask           jawaban ter-grounding dengan sitasi, atau penolakan jujur

Prinsip: jangan pernah mengarang metadata. Semua field trust (approval,
revision, cross-source agreement) berasal dari dokumen aslinya.
"""

__all__ = [
    "dataset",
    "extract",
    "registry",
    "retrieval",
    "trust",
    "conflicts",
    "failure_memory",
    "ask",
]