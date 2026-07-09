#!/usr/bin/env python3
"""Turn audio files into raw transcripts — on this computer only. Nothing is uploaded.

Typical use, from the vault folder in Terminal:

    python3 _scripts/python/transcribe_whisper_local.py

That transcribes every new audio file in 01_Audio/. Or name one file:

    python3 _scripts/python/transcribe_whisper_local.py 01_Audio/interview1.mp3
"""

from __future__ import annotations

import argparse
from pathlib import Path

from qv_common import (audit, die, find_vault, next_steps, ok, refuse_overwrite,
                       step, today, warn)

# .webm is what Obsidian's built-in Audio recorder saves; .opus common on phones
AUDIO_TYPES = {".mp3", ".m4a", ".wav", ".aiff", ".flac", ".ogg", ".mp4", ".aac",
               ".wma", ".webm", ".opus"}


def hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio", nargs="*", help="Audio file(s). Leave empty to take all new files in 01_Audio/.")
    ap.add_argument("--model", default="large-v3", help="Whisper model size (default: large-v3). 'small' is faster, less exact.")
    ap.add_argument("--language", default=None, help="Language code like fi, sv, en. Leave empty to auto-detect. Force it for bilingual interviews — auto-detection can flip mid-file.")
    ap.add_argument("--vocab", default=None,
                    help="Your study's words, comma-separated (place names, drug names, institutions). "
                         "The model spells terms it has seen once far better.")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true", help="Only show what would happen. Change nothing.")
    args = ap.parse_args()

    vault = find_vault(args.vault)
    out_dir = vault / "02_Transcripts"

    if args.audio:
        files = [Path(a).expanduser().resolve() for a in args.audio]
        for f in files:
            if not f.exists():
                die(f"Audio file not found: {f}", "Check the file name and path for typing mistakes.")
    else:
        files = sorted(p for p in (vault / "01_Audio").iterdir()
                       if p.suffix.lower() in AUDIO_TYPES)
        if not files:
            die("No audio files found in 01_Audio/.",
                "Copy your recording into the 01_Audio folder, then run this again.")

    todo = []
    for f in files:
        out = out_dir / f"{f.stem}_raw.md"
        if out.exists():
            warn(f"Skipping {f.name} — transcript already exists ({out.name}).")
        else:
            todo.append((f, out))

    if not todo:
        ok("Nothing to do. Every audio file already has a transcript.")
        return

    if args.dry_run:
        for f, out in todo:
            step(f"Would transcribe {f.name} -> 02_Transcripts/{out.name}")
        ok("Dry run only. Nothing was changed.")
        return

    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
    except ImportError:
        die("The Python package 'faster-whisper' is missing.",
            "In Terminal, run: pip3 install faster-whisper   (one-time setup)")

    step(f"Loading Whisper model '{args.model}' (first time can take a while — it downloads the model once, then it stays on this computer).")
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)

    for f, out in todo:
        refuse_overwrite(out, "Transcript")
        step(f"Transcribing {f.name} ... this runs at roughly the speed of the recording on a laptop. Coffee is allowed.")
        segments, info = model.transcribe(str(f), language=args.language,
                                          initial_prompt=args.vocab)

        lines = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                lines.append(f"[{hms(seg.start)}] ?: {text}")
        if not lines:
            warn(f"No speech found in {f.name}. Skipping it.")
            continue

        duration_min = round(getattr(info, "duration", 0.0) / 60, 1)
        body = "\n\n".join(lines)
        out.write_text(
            "---\n"
            "type: transcript\n"
            "stage: raw\n"
            f"transcript_id: {f.stem}\n"
            f"source_audio: 01_Audio/{f.name}\n"
            f"transcription_model: faster-whisper {args.model} ({args.device}/{args.compute_type})\n"
            f"language_detected: {getattr(info, 'language', '?')} "
            f"(model's own certainty {round(getattr(info, 'language_probability', 0.0), 2)})\n"
            f"duration_min: {duration_min}\n"
            f"transcribed: {today()}\n"
            "speakers_checked: false\n"
            "---\n\n"
            f"# Raw transcript — {f.stem}\n\n"
            "> Machine output. Every speaker is marked `?` because the model cannot tell who is talking.\n"
            "> Fix the speakers and obvious errors before any coding.\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        ok(f"Wrote 02_Transcripts/{out.name} ({len(lines)} segments, {duration_min} min of audio).")
        audit(vault, "transcribe_whisper_local.py", f.name,
              f"faster-whisper {args.model} {args.device}/{args.compute_type}", out.name)

    next_steps(
        "Open the new transcript in Obsidian (folder 02_Transcripts).",
        "Listen to the recording and fix names, medical/technical terms, and anything the model misheard.",
        "Replace every '?' with who is speaking (for example: Interviewer, P01). Keep the [time] stamps.",
        "When the frontmatter line 'speakers_checked' is true in your judgment, set it to true.",
        "Then run: python3 _scripts/python/clean_transcript.py <transcript name>",
    )


if __name__ == "__main__":
    main()
