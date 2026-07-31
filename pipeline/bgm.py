"""산뜻하고 가벼운, 오케스트라풍 BGM을 코드로 직접 생성한다 (저작권/표시 의무 없음).

무드 참고: Joe Hisaishi "Summer" — 밝은 장조, 세련된 7th 코드,
가볍게 통통 튀는 스타카토 피아노. (실제 곡 멜로디는 쓰지 않고,
그 분위기만 살린 오리지널 멜로디를 매번 생성한다.)

구성:
- 현악 앙상블 패드: 코드를 두툼하게 지속(여러 음 디튠 겹침 = 섹션 느낌)
- 첼로 베이스: 따뜻한 저음 지속
- 피아노 오른손: 밝은 스타카토 멜로디(장음계 랜덤워크, 강박은 코드음 안착)
- 피아노 왼손: 가벼운 브로큰 코드 반짝임
출력: 16-bit PCM WAV (스테레오).
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100

_NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
         "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _freq(name: str, octave: int) -> float:
    semis = _NOTE[name] + (octave - 4) * 12 - 9  # A4=440 기준
    return 440.0 * (2.0 ** (semis / 12.0))


# 세련된 진행(7th 코드): I△7 – vi7 – ii7 – V7 – I△7 – vi7 – IV△7 – V7 (C major)
_PROGRESSION = [
    ("C", ["C", "E", "G", "B"]),   # Cmaj7
    ("A", ["A", "C", "E", "G"]),   # Am7
    ("D", ["D", "F", "A", "C"]),   # Dm7
    ("G", ["G", "B", "D", "F"]),   # G7
    ("C", ["C", "E", "G", "B"]),   # Cmaj7
    ("A", ["A", "C", "E", "G"]),   # Am7
    ("F", ["F", "A", "C", "E"]),   # Fmaj7
    ("G", ["G", "B", "D", "F"]),   # G7
]

# 멜로디용 C 장음계 (C5 ~ E6) — 밝고 가벼운 상단 음역
_MELODY_SCALE = [("C", 5), ("D", 5), ("E", 5), ("F", 5), ("G", 5),
                 ("A", 5), ("B", 5), ("C", 6), ("D", 6), ("E", 6)]


def _piano(freq: float, dur: float, amp: float = 0.5,
           decay: float = 5.0, attack: float = 0.005) -> np.ndarray:
    """피아노 느낌: 빠른 어택 + 배음 가중 + 지수 감쇠. decay 크면 스타카토."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    weights = [1.0, 0.55, 0.35, 0.2, 0.12, 0.07]
    sig = np.zeros_like(t)
    for k, w in enumerate(weights, start=1):
        sig += w * np.sin(2 * np.pi * k * freq * t)
    sig /= sum(weights)
    a = max(1, int(SR * attack))
    env = np.exp(-t * decay)
    env[:a] *= np.linspace(0, 1, a)
    return amp * sig * env


def _strings(freq: float, dur: float, amp: float = 0.16,
             attack: float = 0.18, release: float = 0.22) -> np.ndarray:
    """현악 앙상블: 톱니파(배음 풍부) + 미세 디튠 3보이스 + 비브라토 + 부드러운 스웰."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    vib = 1.0 + 0.005 * np.sin(2 * np.pi * 5.2 * t)   # 잔잔한 비브라토
    detunes = (0.997, 1.0, 1.003)                     # ±약 5센트 = 합주 두께
    sig = np.zeros_like(t)
    harmonics = 9
    hnorm = sum(1.0 / k for k in range(1, harmonics + 1))
    for d in detunes:
        phase = np.cumsum(2 * np.pi * freq * d * vib / SR)
        for k in range(1, harmonics + 1):
            sig += (1.0 / k) * np.sin(k * phase)
    sig /= (len(detunes) * hnorm)
    # 활 느낌 엔벨로프: 느린 어택 + 미세 스웰 + 릴리즈
    a = max(1, int(SR * attack))
    r = max(1, int(SR * release))
    env = np.ones_like(t)
    env[:a] = np.linspace(0, 1, a)
    if r < len(env):
        env[-r:] = np.linspace(1, 0, r)
    env *= 0.9 + 0.1 * np.sin(2 * np.pi * 0.5 * t)
    return amp * sig * env


def _place(track: np.ndarray, start: int, chunk: np.ndarray) -> None:
    if start >= len(track) or start < 0:
        return
    end = min(len(track), start + len(chunk))
    track[start:end] += chunk[: end - start]


def _nearest_chord_index(tones: list[str], cur_idx: int) -> int:
    """멜로디 스케일에서 현재 위치와 가장 가까운 코드음 인덱스로 스냅."""
    best, best_d = cur_idx, 99
    for i, (name, _) in enumerate(_MELODY_SCALE):
        if name in tones:
            d = abs(i - cur_idx)
            if d < best_d:
                best, best_d = i, d
    return best


def generate_bgm(
    out_path: str | Path,
    seconds: int = 120,
    tempo_bpm: int = 104,
    seed: int = 7,
) -> Path:
    """산뜻한 피아노 BGM WAV를 생성해 out_path에 저장하고 경로 반환."""
    rng = np.random.default_rng(seed)
    total = int(SR * seconds)
    track = np.zeros(total, dtype=np.float32)

    beat = 60.0 / tempo_bpm
    chord_dur = beat * 4
    chord_samples = int(SR * chord_dur)

    pos = 0
    bar = 0
    mel_idx = 4  # 멜로디 시작 위치(G5 근처)
    while pos < total:
        root, tones = _PROGRESSION[bar % len(_PROGRESSION)]

        # 현악 앙상블 패드: 코드 3화음을 한 마디 내내 지속(두툼한 배경)
        for n in tones[:3]:
            _place(track, pos, _strings(_freq(n, 4), chord_dur, amp=0.14))

        # 첼로 베이스: 따뜻한 저음 지속(반마디씩 근음)
        for b in (0, 2):
            _place(track, pos + int(b * beat * SR),
                   _strings(_freq(root, 2), beat * 2.0, amp=0.22, attack=0.08))

        # 왼손 브로큰 코드(분산화음): 가벼운 반짝임으로 얹기
        broken = [tones[0], tones[2], tones[1], tones[2]]
        for e in range(8):
            n = broken[e % len(broken)]
            octave = 4 if e % 2 == 0 else 5
            _place(track, pos + int(e * 0.5 * beat * SR),
                   _piano(_freq(n, octave), beat * 0.5, amp=0.09, decay=4.5))

        # 오른손 스타카타 멜로디: 8분음표 8개, 강박은 코드음에 안착, 가끔 쉼표
        for e in range(8):
            on_strong = (e % 2 == 0)
            if on_strong:
                mel_idx = _nearest_chord_index(tones, mel_idx)
            else:
                mel_idx += int(rng.integers(-2, 3))  # 약박은 걸어다니기
            mel_idx = max(0, min(len(_MELODY_SCALE) - 1, mel_idx))

            # 가벼움을 위해 약박 일부는 쉼표
            if not on_strong and rng.random() < 0.35:
                continue
            name, octave = _MELODY_SCALE[mel_idx]
            # 스타카토: 슬롯보다 짧게 울리고 빠르게 감쇠
            _place(track, pos + int(e * 0.5 * beat * SR),
                   _piano(_freq(name, octave), beat * 0.42, amp=0.5, decay=7.5))

        pos += chord_samples
        bar += 1

    # 마스터: 정규화 + 전체 페이드 인/아웃
    peak = float(np.max(np.abs(track))) or 1.0
    track = (track / peak) * 0.9
    fin, fout = int(SR * 1.0), int(SR * 2.5)
    track[:fin] *= np.linspace(0, 1, fin)
    track[-fout:] *= np.linspace(1, 0, fout)

    # 살짝의 스테레오 폭
    right = np.concatenate([np.zeros(160, dtype=np.float32), track])[:total]
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
