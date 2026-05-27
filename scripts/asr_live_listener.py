from __future__ import annotations

import argparse
import json
import queue
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

if __package__ in {None, ""}:
  sys.path.append(str(Path(__file__).resolve().parents[1]))
  from scripts.asr_parse_commands import parse_command
else:
  from .asr_parse_commands import parse_command

try:
  import webrtcvad  # type: ignore
except Exception:
  webrtcvad = None


def _int16_bytes(chunk: np.ndarray) -> bytes:
  arr = np.clip(chunk, -1.0, 1.0)
  arr = (arr * 32767.0).astype(np.int16)
  return arr.tobytes()


def _append_jsonl(path: Path, payload: dict) -> None:
  with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _is_blacklisted_noise(text_norm: str) -> bool:
  noise_markers = (
    "продолжение следует",
    "субтитры сделал",
    "субтитры создавал",
    "редактор субтитров",
    "подписывайтесь на наш канал",
    "корректор а",
  )
  return any(marker in text_norm for marker in noise_markers)


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
  parser.add_argument("--energy-threshold", type=float, default=0.015, help="Fallback speech threshold when webrtcvad is unavailable")
  parser.add_argument("--device-id", type=int, default=None, help="Input device id from sounddevice query")
  parser.add_argument("--triggers", default="альфа", help="Comma-separated trigger words")
  parser.add_argument(
    "--log-no-trigger",
    action="store_true",
    help="Also log segments without trigger word (debug mode)",
  )
  parser.add_argument(
    "--print-no-trigger",
    action="store_true",
    help="Also print SKIP lines for segments without trigger word",
  )
  args = parser.parse_args()
  triggers = tuple(part.strip().lower() for part in str(args.triggers).split(",") if part.strip())

  out_path = Path(args.out)
  frame_samples = int(args.samplerate * args.frame_ms / 1000)
  frame_duration = args.frame_ms / 1000.0

  vad = webrtcvad.Vad(args.vad_mode) if webrtcvad is not None else None
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
    text_norm = " ".join(text.lower().replace("ё", "е").split())
    if _is_blacklisted_noise(text_norm):
      return
    parsed = parse_command(text, triggers=triggers)
    payload = parsed.to_dict()
    payload["duration_sec"] = round(len(audio_f32) / args.samplerate, 3)
    # By default we suppress random room/media chatter that doesn't contain trigger word.
    if parsed.error == "no_trigger" and not args.log_no_trigger:
      if args.print_no_trigger:
        print(f"SKIP | {text}")
      return
    _append_jsonl(out_path, payload)
    if parsed.ok:
      print(f"OK | {text}")
    else:
      print(f"SKIP | {text}")

  print("Listening... Ctrl+C to stop")
  if vad is None:
    print("webrtcvad unavailable -> using energy-based fallback VAD")
  with sd.InputStream(
    samplerate=args.samplerate,
    channels=1,
    dtype="float32",
    blocksize=frame_samples,
    device=args.device_id,
    callback=audio_callback,
  ):
    try:
      while True:
        chunk = q.get()
        frame = _int16_bytes(chunk)
        if vad is not None:
          is_speech = vad.is_speech(frame, sample_rate=args.samplerate)
        else:
          # Fallback VAD: simple RMS threshold from float32 chunk.
          rms = float(np.sqrt(np.mean(np.square(chunk)))) if len(chunk) else 0.0
          is_speech = rms >= float(args.energy_threshold)

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
