# -*- coding: utf-8 -*-
"""
cipher.py
Date-Based Dynamic Decoy Security Layer — 핵심 암호 엔진

동작 원리:
  1. seed 문서에서 알파벳 첫 등장 순서로 치환 알파벳 생성
  2. 접근 날짜(월/일) 자릿수 합산 → 회전 칸수
  3. 치환 알파벳을 회전 → 최종 치환표
  4. JSON 키 + 값 전부 치환 (양방향)
"""

import re
from datetime import date as date_type


ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ── 치환표 생성 ───────────────────────────────────────────────
def extract_permuted_alphabet(seed_text: str) -> str:
    """seed 문서에서 알파벳 첫 등장 순서로 26자 치환 알파벳 생성."""
    seen = []
    for ch in seed_text.upper():
        if ch.isalpha() and ch not in seen:
            seen.append(ch)
        if len(seen) == 26:
            break

    # 등장하지 않은 알파벳 뒤에 붙임
    for ch in ALPHA:
        if ch not in seen:
            seen.append(ch)

    return "".join(seen)


def get_rotation(d: date_type) -> int:
    """월/일 자릿수 전부 합산 → 회전 칸수."""
    digits = str(d.month) + str(d.day)
    return sum(int(c) for c in digits)


def build_table(seed_text: str, d: date_type) -> dict:
    """
    최종 치환표 반환.
    {
      'forward':  {'A': 'X', 'B': 'Y', ...},   # 정방향 (원본→치환)
      'backward': {'X': 'A', 'Y': 'B', ...},   # 역방향 (치환→원본)
      'digit_f':  {'0': 'X', '1': 'Y', ...},   # 숫자 정방향
      'digit_b':  {'X': '0', 'Y': '1', ...},   # 숫자 역방향
    }
    """
    perm = extract_permuted_alphabet(seed_text)
    rot  = get_rotation(d) % 26

    # 치환 알파벳을 rot칸 회전
    rotated = perm[rot:] + perm[:rot]

    forward  = {ALPHA[i]: rotated[i] for i in range(26)}
    backward = {v: k for k, v in forward.items()}

    # 숫자 0~9 → 치환 알파벳 앞 10자
    digit_f = {str(i): rotated[i] for i in range(10)}
    digit_b = {v: str(i) for i, v in digit_f.items()}

    return {
        'forward': forward, 'backward': backward,
        'digit_f': digit_f, 'digit_b': digit_b,
        'rotation': rot, 'permuted': perm, 'rotated': rotated,
    }


# ── 단일 값 변환 ──────────────────────────────────────────────
def _transform_str(s: str, alpha_map: dict, digit_map: dict) -> str:
    """문자열 하나를 치환. 알파벳→매핑, 숫자→매핑, 나머지 유지."""
    out = []
    for ch in s:
        up = ch.upper()
        if up in alpha_map:
            result = alpha_map[up]
            out.append(result if ch.isupper() else result.lower())
        elif ch in digit_map:
            out.append(digit_map[ch])
        elif ch == '\n' or ch == '\r':
            out.append(ch)
        elif ch.isalpha():
            # 한글 등 비라틴 문자
            out.append('[X]')
        else:
            # 소수점, 마이너스, 공백, 구두점 등 구조 문자 유지
            out.append(ch)
    return "".join(out)


def _transform_key(key: str, alpha_map: dict, digit_map: dict) -> str:
    """JSON 키 치환 (소문자 알파벳 + 숫자 + _ 구성)."""
    out = []
    for ch in key:
        up = ch.upper()
        if up in alpha_map:
            out.append(alpha_map[up].lower())
        elif ch in digit_map:
            out.append(digit_map[ch])
        else:
            out.append(ch)
    return "".join(out)


def _transform_value(val, alpha_map: dict, digit_map: dict):
    """값 타입별 치환."""
    if isinstance(val, str):
        return _transform_str(val, alpha_map, digit_map)
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return _transform_str(str(val), alpha_map, digit_map)
    if isinstance(val, dict):
        return {
            _transform_key(k, alpha_map, digit_map): _transform_value(v, alpha_map, digit_map)
            for k, v in val.items()
        }
    if isinstance(val, list):
        return [_transform_value(item, alpha_map, digit_map) for item in val]
    return val


# ── 공개 API ──────────────────────────────────────────────────
def encrypt(data, table: dict):
    """원본 데이터 → 치환본 (저장/반환용)."""
    return _transform_value(data, table['forward'], table['digit_f'])


def decrypt(data, table: dict):
    """치환본 → 원본 복원 (정상 접근 시)."""
    return _transform_value(data, table['backward'], table['digit_b'])
