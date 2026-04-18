"""Verify audio pipeline doesn't block event loop."""
from __future__ import annotations
import asyncio
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

pytestmark = pytest.mark.asyncio


@pytest.fixture
def synthetic_wav(tmp_path: Path) -> Path:
    """5s sine wave at 440Hz, 22050Hz sample rate, mono."""
    sr = 22050
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    path = tmp_path / "sine.wav"
    sf.write(str(path), y, sr)
    return path


class TestAsyncAudioExtractor:
    async def test_extract_async_runs_sync_in_thread(self, synthetic_wav: Path):
        """Two parallel calls should finish in ~time of 1 (concurrency proven)."""
        from app.services.audio_analyzer import AudioFeatureExtractor
        extractor = AudioFeatureExtractor()

        start = time.monotonic()
        await extractor.extract_async(synthetic_wav)
        single_dur = time.monotonic() - start

        start = time.monotonic()
        await asyncio.gather(
            extractor.extract_async(synthetic_wav),
            extractor.extract_async(synthetic_wav),
        )
        parallel_dur = time.monotonic() - start

        # Parallel must be <1.7x single (would be 2x if blocking)
        assert parallel_dur < single_dur * 1.7, (
            f"Audio extract is blocking: parallel {parallel_dur:.2f}s vs "
            f"single {single_dur:.2f}s"
        )

    async def test_extract_async_returns_same_features_as_sync(self, synthetic_wav: Path):
        from app.services.audio_analyzer import AudioFeatureExtractor
        extractor = AudioFeatureExtractor()
        sync_features = extractor.extract(synthetic_wav)
        async_features = await extractor.extract_async(synthetic_wav)
        assert sync_features == async_features
