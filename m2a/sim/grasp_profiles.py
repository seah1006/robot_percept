"""Shared Dex3 synergy settings."""
import json
from pathlib import Path
import numpy as np

PROFILES = json.loads(Path(__file__).with_name('grasp_profiles.json').read_text(encoding='utf-8'))


def grasp_profile(part_id):
    return PROFILES['parts'].get(part_id, PROFILES['default'])


def hand_command(profile, progress, sign):
    # Nominal Dex3 targets in HAND order: thumb, index, middle.
    cmd = progress * np.array(profile['close'], dtype=float)
    if profile['close_from_open']:
        delay = profile['thumb_delay']
        thumb = np.clip((progress-delay)/(1-delay), 0, 1)
        cmd[:3] = (1-thumb)*np.array(profile['open'][:3]) + thumb*np.array(profile['close'][:3])
    return sign * cmd

