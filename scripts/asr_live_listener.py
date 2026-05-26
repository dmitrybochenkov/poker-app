from __future__ import annotations

import argparse
import json
import queue
from pathlib import Path

import numpy as np
import sounddevice as sd
import webrtcvad
from faster_whisper import WhisperModel

from scripts.asr_parse_commands import parse_command


def _int16_bytes(chunk: np.ndarray) -> bytes:
  arr = np.clip(chunk, -1.0, 1.0)
  arr = (arr * 32767.0).astype(np.int16)
  return arr.tobytes()


def _append_jsonl(path: Path, payload: dict) -> None:
  with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
  parser = argparse.ArgumentParser(description="Always-on ASR listener for poker voice commands")
  parser.add_argument("--out", default="asr_events.jsonl", help="Output JSONL file")
  parser.add_argument("--samplerate", type=int, default=16000)
  parser.add_argument("--frame-ms", type=int, default=30, choices=[10, 20, 30])
  parser.add_argument("--vad-mode", type=int, default=2, choices=[0, 1, 2, 3])
  parser.add_argument("--model-size", default="small", help="faster-whisper model size")
  parser.add_argument("--compute-type", default="int8", help="int8 / float16 / float32")
  parser.add_argument("--silence-end-frames", type=int, default=12, help="How many silent frames close utterance")
  parser.add_argument("--min-speech-frames", type=int, default=8, help="Drop very short noises")
  args = parser.parse_args()

  out_path = Path(args.out)
  frame_samples = int(args.samplerate * args.frame_ms / 1000)
  frame_duration = args.frame_ms / 1000.0

  vad = webrtcvad.Vad(args.vad_mode)
  model = WhisperModel(args.model_size, compute_type=args.compute_type)
  q: queue.Queue[np.ndarray] = queue.Queue()

  in_speech = False
  speech_frames: list[bytes] = []
  speech_count = 0
  silence_count = 0

  def audio_callback(indata: np.ndarray, frames: int, time, status) -> None:  # noqa: ANN001
    if status:
      pass
    # mono float32 in [-1..1]
    mono = indata[:, 0].copy()
    q.put(mono)

  def process_utterance(raw_pcm_frames: list[bytes]) -> None:
    pcm = b"".join(raw_pcm_frames)
    if not pcm:
      return
    audio_int16 = np.frombuffer(pcm, dtype=np.int16)
    audio_f32 = (audio_int16.astype(np.float32) / 32768.0).copy()
    segments, _info = model.transcribe(audio_f32, language="ru", vad_filter=False)
    text = " ".join((seg.text or "").strip() for seg in segments).strip()
    if not text:
      return
    parsed = parse_command(text)
    payload = parsed.to_dict()
    payload["duration_sec"] = round(len(audio_f32) / args.samplerate, 3)
    _append_jsonl(out_path, payload)
    print(f"{'OK' if parsed.ok else 'SKIP'} | {text}")

  print("Listening... Ctrl+C to stop")
  with sd.InputStream(
    samplerate=args.samplerate,
    channels=1,
    dtype="float32",
    blocksize=frame_samples,
    callback=audio_callback,
  ):
    try:
      while True:
        chunk = q.get()
        frame = _int16_bytes(chunk)
        is_speech = vad.is_speech(frame, sample_rate=args.samplerate)

        if is_speech:
          if not in_speech:
            in_speech = True
            speech_frames = []
            speech_count = 0
            silence_count = 0
          speech_frames.append(frame)
          speech_count += 1
          silence_count = 0
          continue

        # silence
        if in_speech:
          speech_frames.append(frame)
          silence_count += 1
          if silence_count >= args.silence_end_frames:
            in_speech = False
            if speech_count >= args.min_speech_frames:
              process_utterance(speech_frames)
            speech_frames = []
            speech_count = 0
            silence_count = 0
    except KeyboardInterrupt:
      print("\nStopped.")
      return


if __name__ == "__main__":
  main()
