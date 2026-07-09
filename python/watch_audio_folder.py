#!/usr/bin/env python3
"""Watch 01_Audio/ and transcribe every new recording automatically — locally.

Start it, leave it running, and drop audio files into 01_Audio/ whenever you
like. Each new file is transcribed as soon as it has finished copying. Stop
with Ctrl+C.

Typical use:

    python3 _scripts/python/watch_audio_folder.py           (keeps watching)
    python3 _scripts/python/watch_audio_folder.py --once    (do the backlog, then stop)

Transcription itself is done by transcribe_whisper_local.py, so everything in
its help (model choice, language) applies here too, e.g. --model medium.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from qv_common import find_vault, ok, step, warn

# .webm is what Obsidian's built-in Audio recorder saves; .opus common on phones
AUDIO_TYPES = {".mp3", ".m4a", ".wav", ".aiff", ".flac", ".ogg", ".mp4", ".aac",
               ".wma", ".webm", ".opus"}


def pending(vault: Path) -> list[Path]:
    audio_dir = vault / "01_Audio"
    out_dir = vault / "02_Transcripts"
    todo = []
    for f in sorted(audio_dir.iterdir()):
        if f.suffix.lower() in AUDIO_TYPES and not (out_dir / f"{f.stem}_raw.md").exists():
            todo.append(f)
    return todo


def is_still_copying(f: Path, wait: float = 2.0) -> bool:
    """A file that is still growing is still being copied — leave it alone."""
    size1 = f.stat().st_size
    time.sleep(wait)
    try:
        return f.stat().st_size != size1
    except FileNotFoundError:
        return True


def transcribe(vault: Path, f: Path, passthrough: list[str]) -> None:
    script = vault / "_scripts" / "python" / "transcribe_whisper_local.py"
    cmd = [sys.executable, str(script), str(f), "--vault", str(vault)] + passthrough
    result = subprocess.run(cmd)
    if result.returncode != 0:
        warn(f"Transcription of {f.name} did not finish — see the message above. "
             "The watcher keeps running; fix the problem and the file will be retried.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="Transcribe what is waiting now, then stop (no watching).")
    ap.add_argument("--interval", type=int, default=15,
                    help="How often to look for new files, in seconds (default 15).")
    ap.add_argument("--model", default=None, help="Whisper model size, passed through.")
    ap.add_argument("--language", default=None, help="Language code, passed through.")
    ap.add_argument("--vocab", default=None, help="Your study's words, passed through.")
    ap.add_argument("--vault", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    vault = find_vault(args.vault)
    passthrough = []
    if args.model:
        passthrough += ["--model", args.model]
    if args.language:
        passthrough += ["--language", args.language]
    if args.vocab:
        passthrough += ["--vocab", args.vocab]

    step(f"Watching {vault / '01_Audio'} — drop recordings in, they will be "
         "transcribed here. Stop with Ctrl+C.")
    failed: set[str] = set()

    try:
        while True:
            for f in pending(vault):
                if f.name in failed:
                    continue
                if is_still_copying(f):
                    step(f"{f.name} is still copying — waiting.")
                    continue
                step(f"New recording: {f.name}")
                transcribe(vault, f, passthrough)
                if not (vault / "02_Transcripts" / f"{f.stem}_raw.md").exists():
                    failed.add(f.name)  # do not retry in a loop; the message said why
            if args.once:
                left = [f.name for f in pending(vault) if f.name not in failed]
                if not left:
                    ok("Backlog done." if not failed else
                       f"Backlog done, except: {', '.join(sorted(failed))} (see messages above).")
                    return
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        ok("Watcher stopped. Restart it any time.")


if __name__ == "__main__":
    main()
