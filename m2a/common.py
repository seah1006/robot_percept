"""m2a 공용 로더 (메인 소유). 다른 모듈은 여기서 경로·설정을 읽는다."""
from __future__ import annotations
import json
from pathlib import Path

M2A = Path(__file__).resolve().parent
ROOT = M2A.parent


def load_layout(path: Path | None = None) -> dict:
    with open(path or M2A / 'config/layout.json', encoding='utf-8') as f:
        return json.load(f)


def load_parts(product: str = 'm2a_shelf_v1') -> dict:
    return json.loads((M2A / 'knowledge' / product / 'parts.json').read_text(encoding='utf-8'))


def load_steps(product: str = 'm2a_shelf_v1') -> dict:
    return json.loads((M2A / 'knowledge' / product / 'steps.json').read_text(encoding='utf-8'))