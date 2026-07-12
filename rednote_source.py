"""
RedNote (Xiaohongshu) audio download.

Unlike YouTube, RedNote has no accessible caption/subtitle text API, so
getting a transcript here means: download the post's audio, then run it
through a speech-to-text model (see transcription/backends.py).

Heads-up (as of mid-2026): RedNote actively fights automated downloads
with CAPTCHA walls that, per yt-dlp's own issue tracker, "cannot be
easily bypassed". The site's rebrand from xiaohongshu.com to rednote.com
has also occasionally broken yt-dlp's extractor until a fix lands. This
means downloads can fail here for reasons outside this bot's control —
keep yt-dlp updated (`pip install -U yt-dlp`), since fixes land there,
not in this file.
"""

import os
import re
import uuid

import yt_dlp

REDNOTE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:xiaohongshu\.com|xhslink\.com|rednote\.com)/\S+",
    re.IGNORECASE,
)


class RedNoteDownloadError(Exception):
    """Raised when yt-dlp cannot fetch audio from a RedNote link
    (CAPTCHA wall, broken extractor, deleted post, etc.)."""


def extract_rednote_url(text: str) -> str | None:
    """Returns the RedNote URL found in the text, if any (works for
    xiaohongshu.com, the xhslink.com short-link form, and rednote.com)."""
    match = REDNOTE_URL_RE.search(text)
    return match.group(0) if match else None


def download_audio(url: str, output_dir: str) -> str:
    """Downloads the best available audio for a RedNote post and converts
    it to a .wav file, returning the local file path.

    Requires ffmpeg on the system (apt install ffmpeg / pkg install ffmpeg
    on Termux) for the audio-extraction postprocessor.
    """
    os.makedirs(output_dir, exist_ok=True)
    unique_id = uuid.uuid4().hex
    output_template = os.path.join(output_dir, f"rednote_{unique_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise RedNoteDownloadError(str(e)) from e

    expected_path = os.path.join(output_dir, f"rednote_{unique_id}.wav")
    if not os.path.exists(expected_path):
        raise RedNoteDownloadError(
            "Audio file download ke baad mila nahi (ffmpeg postprocessing fail hui ho sakti hai — "
            "check karo ffmpeg installed hai)."
        )

    return expected_path


def cleanup(*paths: str) -> None:
    """Deletes temp files, ignoring any that are already gone."""
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass
