"""경쾌하고 아름다운 BGM을 코드로 직접 생성한다 (저작권/표시 의무 없음).

외부 음원을 내려받지 않고 절차적으로 합성하므로 100% 무료로
유튜브에 상업적 사용이 가능하다.

음색: 바이올린(비브라토 활 소리) 리드 + 피아노(또렷한 타건) 반주 중심으로
'선명한' 소리를 목표로 한다.

구성:
- 코드 진행: I–V–vi–IV (C–G–Am–F). 가장 보편적으로 '예쁜' 진행.
- 바이올린 멜로디 + 피아노 코드/아르페지오 + 피아노 베이스.
- 마디마다 멜로디 패턴을 조금씩 바꿔 지루하지 않게.
출력: 16-bit PCM WAV (스테레오).
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100

# 음이름 -> 반음 오프셋 (A4=440 기준 계산)
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


def _violin(freq: float, dur: float, amp: float = 0.42) -> np.ndarray:
    """바이올린 느낌: 배음이 풍부한 톱니파 + 비브라토 + 부드러운 활 엔벨로프."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    # 비브라토(초당 5.5회, ±0.6%)를 위상에 반영
    vib = 1.0 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
    phase = np.cumsum(2 * np.pi * freq * vib / SR)
    sig = np.zeros_like(t)
    harmonics = 12                       # 배음 많이 -> 선명/밝은 현 소리
    norm = 0.0
    for k in range(1, harmonics + 1):
        a = 1.0 / k
        sig += a * np.sin(k * phase)
        norm += a
    sig /= norm
    # 활 엔벨로프: 부드러운 어택 + 약한 스웰 + 릴리즈
    a = max(1, int(SR * 0.07))
    r = max(1, int(SR * 0.12))
    env = np.ones_like(t)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    env *= 0.9 + 0.1 * np.sin(2 * np.pi * 0.8 * t)  # 미세한 다이내믹
    return amp * sig * env


def _piano(freq: float, dur: float, amp: float = 0.5) -> np.ndarray:
    """피아노 느낌: 또렷한 타건(빠른 어택) + 배음 가중 + 지수 감쇠."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    weights = [1.0, 0.6, 0.4, 0.25, 0.15, 0.1]   # 피아노다운 배음 분포
    sig = np.zeros_like(t)
    for k, w in enumerate(weights, start=1):
        sig += w * np.sin(2 * np.pi * k * freq * t)
    sig /= sum(weights)
    a = max(1, int(SR * 0.005))                   # 아주 빠른 어택 -> 또렷
    env = np.exp(-t * 5.0)                         # 타건 후 감쇠
    env[:a] *= np.linspace(0, 1, a)
    return amp * sig * env


def _place(track: np.ndarray, start: int, chunk: np.ndarray) -> None:
    if start >= len(track) or start < 0:
        return
    end = min(len(track), start + len(chunk))
    track[start:end] += chunk[: end - start]


def generate_bgm(
    out_path: str | Path,
    seconds: int = 240,
    tempo_bpm: int = 112,
    seed: int = 7,
) -> Path:
    """경쾌한 BGM WAV를 생성해 out_path에 저장하고 경로 반환."""
    rng = np.random.default_rng(seed)
    total = int(SR * seconds)
    track = np.zeros(total, dtype=np.float32)

    beat = 60.0 / tempo_bpm
    chord_dur = beat * 4               # 코드 1개 = 1마디(4박)
    chord_samples = int(SR * chord_dur)

    # 바이올린 멜로디 리듬 패턴(박 단위)
    patterns = [
        [1.0, 0.5, 0.5, 1.0, 1.0],
        [0.5, 0.5, 1.0, 1.0, 1.0],
        [1.5, 0.5, 1.0, 1.0],
        [1.0, 1.0, 0.5, 0.5, 1.0],
    ]

    pos = 0
    bar = 0
    while pos < total:
        root, tones = _PROGRESSION[bar % len(_PROGRESSION)]

        # 피아노 코드: 각 박마다 3화음을 가볍게 타건(반주)
        for b in range(4):
            for n in tones:
                _place(track, pos + int(b * beat * SR),
                       _piano(_freq(n, 4), beat * 0.95, amp=0.12))

        # 피아노 베이스: 근음 저음, 다운비트 강조
        for b in (0, 2):
            _place(track, pos + int(b * beat * SR),
                   _piano(_freq(root, 2), beat * 1.8, amp=0.4))

        # 피아노 아르페지오(상단, 선명함 보강)
        for b in range(4):
            _place(track, pos + int((b + 0.5) * beat * SR),
                   _piano(_freq(tones[b % 3], 5), beat * 0.4, amp=0.14))

        # 바이올린 멜로디(리드)
        pat = patterns[(bar + rng.integers(0, len(patterns))) % len(patterns)]
        scale = [_freq(n, 5) for n in tones] + [_freq(tones[0], 6), _freq(tones[1], 5)]
        mel_pos = pos
        for dur_beats in pat:
            note = scale[rng.integers(0, len(scale))]
            if rng.random() > 0.1:     # 가끔 쉼표
                _place(track, mel_pos, _violin(note, beat * dur_beats * 0.98, amp=0.46))
            mel_pos += int(dur_beats * beat * SR)
            if mel_pos >= pos + chord_samples:
                break

        pos += chord_samples
        bar += 1

    # 마스터: 정규화 + 전체 페이드 인/아웃
    peak = float(np.max(np.abs(track))) or 1.0
    track = (track / peak) * 0.9
    fin, fout = int(SR * 1.2), int(SR * 2.5)
    track[:fin] *= np.linspace(0, 1, fin)
    track[-fout:] *= np.linspace(1, 0, fout)

    # 살짝의 스테레오 폭(오른쪽 소폭 지연)
    right = np.concatenate([np.zeros(180, dtype=np.float32), track])[:total]
    stereo = np.stack([track, right], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path
