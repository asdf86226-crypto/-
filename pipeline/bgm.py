"""경쾌하고 아름다운 BGM을 코드로 직접 생성한다 (저작권/표시 의무 없음).

외부 음원을 내려받지 않고 절차적으로 합성하므로 100% 무료로
유튜브에 상업적 사용이 가능하다.

구성:
- 코드 진행: I–V–vi–IV (C–G–Am–F). 가장 보편적으로 '예쁜' 진행.
- 패드(코드) + 베이스 + 오르골 느낌 멜로디(plucky) 레이어.
- 마디마다 멜로디 패턴을 조금씩 바꿔 4분 내내 지루하지 않게.
출력: 16-bit PCM WAV (스테레오).
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100

# 음이름 -> 주파수(A4=440) 헬퍼용 반음 오프셋 (C4 기준)
_NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
         "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _freq(name: str, octave: int) -> float:
    semis = _NOTE[name] + (octave - 4) * 12 - 9  # A4 기준
    return 440.0 * (2.0 ** (semis / 12.0))


# I–V–vi–IV 진행. 각 코드의 (근음, 구성음 3개)
_PROGRESSION = [
    ("C", ["C", "E", "G"]),
    ("G", ["G", "B", "D"]),
    ("A", ["A", "C", "E"]),
    ("F", ["F", "A", "C"]),
]


def _pluck(freq: float, dur: float, amp: float = 0.5) -> np.ndarray:
    """오르골/벨 느낌의 감쇠음(배음 합 + 지수 감쇠 엔벨로프)."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    wave_ = (
        1.0 * np.sin(2 * np.pi * freq * t)
        + 0.5 * np.sin(2 * np.pi * 2 * freq * t)
        + 0.25 * np.sin(2 * np.pi * 3 * freq * t)
    )
    env = np.exp(-t * 4.5)  # 빠른 감쇠 -> 맑고 또렷
    return amp * wave_ * env


def _pad(freqs: list[float], dur: float, amp: float = 0.16) -> np.ndarray:
    """코드 패드(부드러운 지속음, 클릭 방지 위해 attack/release 적용)."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    sig = np.zeros_like(t)
    for f in freqs:
        sig += np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    sig /= max(1, len(freqs))
    a = int(SR * 0.05)
    env = np.ones_like(t)
    env[:a] = np.linspace(0, 1, a)
    env[-a:] = np.linspace(1, 0, a)
    return amp * sig * env


def _place(track: np.ndarray, start: int, chunk: np.ndarray) -> None:
    if start >= len(track) or start < 0:
        return
    end = min(len(track), start + len(chunk))
    track[start:end] += chunk[: end - start]


def generate_bgm(
    out_path: str | Path,
    seconds: int = 240,
    tempo_bpm: int = 100,
    seed: int = 7,
) -> Path:
    """경쾌한 BGM WAV를 생성해 out_path에 저장하고 경로 반환."""
    rng = np.random.default_rng(seed)
    total = int(SR * seconds)
    left = np.zeros(total, dtype=np.float32)

    beat = 60.0 / tempo_bpm          # 한 박 길이(초)
    chord_dur = beat * 4             # 코드 1개 = 1마디(4박)
    chord_samples = int(SR * chord_dur)

    # 멜로디 리듬 패턴(박 단위) 몇 가지를 번갈아 사용
    patterns = [
        [0.5, 0.5, 1.0, 1.0, 1.0],
        [1.0, 0.5, 0.5, 1.0, 1.0],
        [0.5, 0.5, 0.5, 0.5, 1.0, 1.0],
        [1.0, 1.0, 0.5, 0.5, 1.0],
    ]

    pos = 0
    bar = 0
    while pos < total:
        root, tones = _PROGRESSION[bar % len(_PROGRESSION)]

        # 패드(코드) - 3화음, 낮은 옥타브
        pad_freqs = [_freq(n, 3 if n in ("C", "D", "E", "F") else 3) for n in tones]
        _place(left, pos, _pad(pad_freqs, chord_dur))

        # 베이스 - 근음, 각 박마다 부드럽게
        for b in range(4):
            _place(left, pos + int(b * beat * SR),
                   _pluck(_freq(root, 2), beat * 0.9, amp=0.28))

        # 멜로디 - 코드 구성음 위주로, 마디마다 패턴/음 바꿈
        pat = patterns[(bar + rng.integers(0, len(patterns))) % len(patterns)]
        mel_pos = pos
        scale = [_freq(n, 5) for n in tones] + [_freq(tones[0], 6)]
        for dur_beats in pat:
            note = scale[rng.integers(0, len(scale))]
            # 가끔 쉼표로 여백
            if rng.random() > 0.12:
                _place(left, mel_pos, _pluck(note, beat * dur_beats * 0.95, amp=0.42))
            mel_pos += int(dur_beats * beat * SR)
            if mel_pos >= pos + chord_samples:
                break

        # 반짝이는 상단 아르페지오(은은하게)
        for b in range(4):
            _place(left, pos + int(b * beat * SR),
                   _pluck(_freq(tones[b % 3], 6), beat * 0.5, amp=0.12))

        pos += chord_samples
        bar += 1

    # 마스터: 정규화 + 전체 페이드 인/아웃
    peak = np.max(np.abs(left)) or 1.0
    left = (left / peak) * 0.85
    fin, fout = int(SR * 1.5), int(SR * 2.5)
    left[:fin] *= np.linspace(0, 1, fin)
    left[-fout:] *= np.linspace(1, 0, fout)

    # 살짝의 스테레오 폭(오른쪽을 몇 샘플 지연)
    right = np.concatenate([np.zeros(220, dtype=np.float32), left])[:total]
    stereo = np.stack([left, right], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path
