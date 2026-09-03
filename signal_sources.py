# signal_sources.py
"""
Baseband Message Signal Ingestion Module
========================================
Thread-safe streaming sources:
  - WaveformSource : Real-time Sine, Square, Triangle, Sawtooth, Chirp synthesis
  - MicSource      : Live hardware microphone capture via sounddevice
  - WavSource      : WAV / MP3 file streaming
  - ToneSource     : Multi-tone harmonic generator
"""

import threading
import numpy as np
import sounddevice as sd
from waveforms import generate_waveform

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

CHUNK = 1024
SR = 44100.0


class RingBuffer:
    """Fixed-size thread-safe circular buffer."""
    def __init__(self, size: int):
        self._buf = np.zeros(int(size), dtype=np.float32)
        self._size = int(size)
        self._write_pos = 0
        self._lock = threading.Lock()

    def write(self, data: np.ndarray):
        n = len(data)
        if n == 0:
            return
        with self._lock:
            if n >= self._size:
                self._buf[:] = data[-self._size:]
                self._write_pos = 0
            else:
                end = self._write_pos + n
                if end <= self._size:
                    self._buf[self._write_pos:end] = data
                else:
                    first = self._size - self._write_pos
                    self._buf[self._write_pos:] = data[:first]
                    self._buf[:n - first] = data[first:]
                self._write_pos = (self._write_pos + n) % self._size

    def read_last(self, n: int) -> np.ndarray:
        with self._lock:
            n_read = min(n, self._size)
            start = (self._write_pos - n_read) % self._size
            if start + n_read <= self._size:
                return self._buf[start:start + n_read].copy()
            else:
                first = self._size - start
                return np.concatenate([self._buf[start:], self._buf[:n_read - first]]).copy()


class WaveformSource:
    """
    Synthesizes standard mathematical waveforms in real-time.
    """
    def __init__(self, wave_type: str = 'sine', fm: float = 1000.0, am: float = 1.0,
                 phase_rad: float = 0.0, sr: float = SR, buf_secs: float = 4.0):
        if fm >= sr / 2:
            print(f"Warning: fm {fm} exceeds Nyquist frequency for sr {sr}")
        self.wave_type = wave_type
        self.fm = float(fm)
        self.am = float(am)
        self.phase_rad = float(phase_rad)
        self.sr = float(sr)
        self.buffer = RingBuffer(int(self.sr * buf_secs))
        self.active = False
        self.level = 0.0
        self._t_idx = 0
        self._thread = None
        self._stop_evt = threading.Event()

    def set_params(self, wave_type: str = None, fm: float = None,
                   am: float = None, phase_rad: float = None):
        if wave_type is not None:
            self.wave_type = wave_type
        if fm is not None:
            self.fm = float(fm)
        if am is not None:
            self.am = float(am)
        if phase_rad is not None:
            self.phase_rad = float(phase_rad)

    def _worker(self):
        chunk_size = 1024
        while not self._stop_evt.is_set():
            # Generate chunk
            sig = generate_waveform(self.wave_type, self.fm, self.am, self.phase_rad,
                                    chunk_size, self.sr, t_offset=self._t_idx / self.sr)
            self._t_idx += chunk_size
            
            self.level = float(np.sqrt(np.mean(sig ** 2)))
            self.buffer.write(sig)
            self._stop_evt.wait(0.015)

    def start(self):
        if not self.active:
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
            self.active = True

    def stop(self):
        if self.active:
            self._stop_evt.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=0.1)
            self.active = False

    def read_last(self, n: int) -> np.ndarray:
        return self.buffer.read_last(n)


class MicSource:
    """
    Captures live audio from default system microphone.
    """
    def __init__(self, sr: float = SR, buf_secs: float = 4.0):
        self.sr = float(sr)
        self.buffer = RingBuffer(int(self.sr * buf_secs))
        self.active = False
        self.level = 0.0
        self._stream = None

    def _cb(self, indata, frames, time_info, status):
        mono = indata[:, 0].astype(np.float32)
        self.level = float(np.sqrt(np.mean(mono ** 2)))
        self.buffer.write(mono)

    def start(self):
        if self.active:
            return
        try:
            self._stream = sd.InputStream(
                samplerate=self.sr, channels=1, dtype='float32',
                blocksize=CHUNK, callback=self._cb
            )
            self._stream.start()
            self.active = True
        except Exception as e:
            print(f"[MicSource] Warning: Microphone start failed: {e}")
            self.active = False

    def stop(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.active = False

    def read_last(self, n: int) -> np.ndarray:
        return self.buffer.read_last(n)


class WavSource:
    """
    Streams audio from a local WAV or MP3 file.
    """
    def __init__(self, path: str, sr: float = SR, buf_secs: float = 4.0, play_audio: bool = False):
        self.sr = float(sr)
        self.buffer = RingBuffer(int(self.sr * buf_secs))
        self.active = False
        self.level = 0.0
        self.play_audio = play_audio
        self._pos = 0
        self._data = np.zeros(int(self.sr), dtype=np.float32)
        self._thread = None
        self._stop_evt = threading.Event()

        # Load file
        self._load(path)

    def _load(self, path: str):
        if HAS_LIBROSA:
            try:
                y, _ = librosa.load(path, sr=self.sr, mono=True)
                self._data = y.astype(np.float32)
                print(f"[WavSource] Loaded '{path}' ({len(y)/self.sr:.1f}s)")
                return
            except Exception as e:
                print(f"[WavSource] librosa load failed: {e}")

        try:
            from scipy.io import wavfile
            fsr, data = wavfile.read(path)
            if data.ndim > 1:
                data = data[:, 0]
            data = data.astype(np.float32)
            mx = np.abs(data).max()
            if mx > 0:
                data /= mx
            if fsr != self.sr:
                n_new = int(len(data) * self.sr / fsr)
                data = np.interp(
                    np.linspace(0, len(data)-1, n_new),
                    np.arange(len(data)), data
                ).astype(np.float32)
            self._data = data
            print(f"[WavSource] Loaded (scipy) '{path}'")
        except Exception as e:
            print(f"[WavSource] scipy load failed: {e}")

    def _worker(self):
        chunk_size = 1024
        data_len = len(self._data)
        if data_len == 0:
            return

        while not self._stop_evt.is_set():
            end = self._pos + chunk_size
            if end > data_len:
                chunk = np.concatenate([self._data[self._pos:], self._data[:end - data_len]])
                self._pos = end - data_len
            else:
                chunk = self._data[self._pos:end]
                self._pos = end

            chunk = chunk.astype(np.float32)
            self.level = float(np.sqrt(np.mean(chunk ** 2)))
            self.buffer.write(chunk)
            self._stop_evt.wait(0.02)

    def start(self):
        if not self.active:
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
            self.active = True

    def stop(self):
        if self.active:
            self._stop_evt.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=0.1)
            self.active = False

    def read_last(self, n: int) -> np.ndarray:
        return self.buffer.read_last(n)


class ToneSource:
    """
    Multi-tone harmonic frequency generator.
    """
    def __init__(self, tones: list = None, sr: float = SR, buf_secs: float = 4.0):
        self.sr = float(sr)
        self.tones = tones or [(440.0, 0.6), (880.0, 0.3), (1320.0, 0.1)]
        self.buffer = RingBuffer(int(self.sr * buf_secs))
        self.active = False
        self.level = 0.0
        self._t_idx = 0
        self._thread = None
        self._stop_evt = threading.Event()

    def set_tones(self, tones: list):
        self.tones = tones

    def _worker(self):
        chunk_size = 1024
        while not self._stop_evt.is_set():
            t = (self._t_idx + np.arange(chunk_size)) / self.sr
            
            sig = np.zeros(chunk_size, dtype=np.float32)
            for f, a in self.tones:
                sig += float(a) * np.cos(2.0 * np.pi * float(f) * t).astype(np.float32)
            
            self._t_idx += chunk_size
            
            # Global normalization
            tot_amp = sum(a for _, a in self.tones)
            if tot_amp > 0:
                sig /= tot_amp

            self.level = float(np.sqrt(np.mean(sig ** 2)))
            self.buffer.write(sig)
            self._stop_evt.wait(0.02)

    def start(self):
        if not self.active:
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()
            self.active = True

    def stop(self):
        if self.active:
            self._stop_evt.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=0.1)
            self.active = False

    def read_last(self, n: int) -> np.ndarray:
        return self.buffer.read_last(n)
