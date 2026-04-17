"""Análise determinística de áudio com librosa.

Extrai métricas OBJETIVAS (BPM, key, RMS, centroide espectral) de um arquivo
de áudio. Essas métricas são fornecidas ao Claude como contexto factual para
ele focar apenas na interpretação subjetiva (mood, timbre vocal, produção).

Por que híbrido:
- BPM de LLM multimodal é estimativa imprecisa (±10 BPM comum)
- librosa é determinístico, ~1% erro em BPM
- Mesma lib usada por Spotify/YouTube Music
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import librosa
import numpy as np


# ---------------------------------------------------------------------------
# Resultado estruturado
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AudioFeatures:
    """Features objetivas extraídas do áudio. Sempre mesmos tipos e ranges."""

    duration_seconds: float
    bpm: float                          # tempo estimado
    bpm_confidence: float               # 0-1 (derivado da estabilidade do beat)
    key: str                            # ex: "F minor", "C major"
    key_confidence: float               # 0-1
    rms_energy: float                   # 0-1 (energia média)
    spectral_centroid_hz: float         # brightness (< 2000 = dark, > 4000 = bright)
    zero_crossing_rate: float           # alto = percussivo/noisy; baixo = tonal
    sample_rate: int

    def to_prompt_context(self) -> str:
        """Formata as features em texto claro para enviar ao Claude."""
        brightness = (
            "dark/mellow" if self.spectral_centroid_hz < 2000
            else "balanced" if self.spectral_centroid_hz < 4000
            else "bright/airy"
        )
        energy_desc = (
            "low energy" if self.rms_energy < 0.08
            else "medium energy" if self.rms_energy < 0.2
            else "high energy"
        )
        return (
            f"- BPM: {self.bpm:.1f} (confidence: {self.bpm_confidence:.2f})\n"
            f"- Key: {self.key} (confidence: {self.key_confidence:.2f})\n"
            f"- Energy (RMS): {self.rms_energy:.3f} ({energy_desc})\n"
            f"- Spectral brightness: {self.spectral_centroid_hz:.0f} Hz ({brightness})\n"
            f"- Zero-crossing rate: {self.zero_crossing_rate:.4f}\n"
            f"- Duration: {self.duration_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# Extrator principal
# ---------------------------------------------------------------------------

class AudioFeatureExtractor:
    """Extrai features objetivas de um arquivo de áudio usando librosa.

    Análise de 60s é o sweet spot (StemSplit pattern): curto demais perde
    precisão, longo demais não melhora significativamente.
    """

    def __init__(
        self,
        analysis_duration_seconds: float = 60.0,
        sample_rate: int = 22050,  # default librosa, suficiente pra BPM/key
    ):
        self.analysis_duration = analysis_duration_seconds
        self.sample_rate = sample_rate

    def extract(self, source: str | Path | IO[bytes]) -> AudioFeatures:
        """Extrai features do áudio. Aceita path ou file-like (BytesIO)."""
        # librosa.load aceita ambos
        y, sr = librosa.load(
            source,
            sr=self.sample_rate,
            duration=self.analysis_duration,
            mono=True,
        )

        if len(y) == 0:
            raise ValueError("Arquivo de áudio vazio ou ilegível")

        duration = float(len(y) / sr)

        # BPM com confidence
        bpm, bpm_conf = self._detect_bpm(y, sr)

        # Key
        key, key_conf = self._detect_key(y, sr)

        # RMS energy
        rms = float(np.mean(librosa.feature.rms(y=y)))

        # Spectral centroid (brightness)
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))

        # Zero-crossing rate
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))

        return AudioFeatures(
            duration_seconds=duration,
            bpm=float(bpm),
            bpm_confidence=float(bpm_conf),
            key=key,
            key_confidence=float(key_conf),
            rms_energy=rms,
            spectral_centroid_hz=centroid,
            zero_crossing_rate=zcr,
            sample_rate=sr,
        )

    # -----------------------------------------------------------------------
    # Algoritmos
    # -----------------------------------------------------------------------

    @staticmethod
    def _detect_bpm(y: np.ndarray, sr: int) -> tuple[float, float]:
        """Detecta BPM com indicador de confidence baseado em estabilidade do beat."""
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)

        # tempo vem como np.ndarray de 1 elemento em versões modernas
        tempo_value = float(np.atleast_1d(tempo)[0])

        # Confidence: estabilidade dos intervalos entre beats
        if len(beats) < 4:
            return tempo_value, 0.3  # poucos beats = baixa confidence

        beat_times = librosa.frames_to_time(beats, sr=sr)
        intervals = np.diff(beat_times)
        # Coeficiente de variação inverso: estável = alta confidence
        cv = float(np.std(intervals) / np.mean(intervals)) if np.mean(intervals) > 0 else 1.0
        confidence = max(0.0, min(1.0, 1.0 - cv * 2))

        return tempo_value, confidence

    @staticmethod
    def _detect_key(y: np.ndarray, sr: int) -> tuple[str, float]:
        """Detecta tonalidade usando correlação com perfis de Krumhansl-Schmuckler."""
        # Chroma features (12 semitons)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = np.mean(chroma, axis=1)

        # Perfis de Krumhansl para maior e menor
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        best_corr = -1.0
        best_key = "C major"

        for i in range(12):
            # Rotaciona o perfil para cada tônica possível
            major_shifted = np.roll(major_profile, i)
            minor_shifted = np.roll(minor_profile, i)

            major_corr = np.corrcoef(chroma_mean, major_shifted)[0, 1]
            minor_corr = np.corrcoef(chroma_mean, minor_shifted)[0, 1]

            if major_corr > best_corr:
                best_corr = major_corr
                best_key = f"{notes[i]} major"

            if minor_corr > best_corr:
                best_corr = minor_corr
                best_key = f"{notes[i]} minor"

        # Confidence: correlação do best normalizada
        confidence = max(0.0, min(1.0, float(best_corr)))

        return best_key, confidence


# ---------------------------------------------------------------------------
# Geração de espectrograma (imagem PNG para Claude "ver" o áudio)
# ---------------------------------------------------------------------------

def generate_spectrogram_png(
    source: str | Path | IO[bytes],
    duration_seconds: float = 30.0,
    sample_rate: int = 22050,
) -> bytes:
    """Gera espectrograma como PNG (bytes) para enviar ao Claude como imagem.

    Usa matplotlib. Salva em BytesIO e retorna os bytes.
    """
    import matplotlib
    matplotlib.use("Agg")  # backend sem display (servidor)
    import matplotlib.pyplot as plt

    y, sr = librosa.load(source, sr=sample_rate, duration=duration_seconds, mono=True)

    # Mel-spectrogram em dB (mais informativo visualmente que STFT bruto)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
    S_db = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots(figsize=(10, 4), dpi=80)
    img = librosa.display.specshow(
        S_db, x_axis="time", y_axis="mel", sr=sr, fmax=8000, ax=ax
    )
    ax.set_title("Mel-Spectrogram")
    fig.colorbar(img, ax=ax, format="%+2.0f dB")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
