"""
YouTube transcript fetching.

Given a YouTube URL, lists available transcript languages, then fetches
the text of a chosen one. Uses youtube_transcript_api, which talks to
YouTube's own caption endpoints directly (no video download needed).
"""

import os
import re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    InvalidVideoId,
    NoTranscriptFound,
    PoTokenRequired,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import WebshareProxyConfig

# Re-exported so bot.py can catch these via youtube_source.<ExceptionName>
# without a second import from youtube_transcript_api._errors.
__all__ = [
    "extract_video_id",
    "build_transcript_api",
    "list_transcripts",
    "fetch_transcript_text",
    "AgeRestricted",
    "InvalidVideoId",
    "NoTranscriptFound",
    "PoTokenRequired",
    "RequestBlocked",
    "TranscriptsDisabled",
    "VideoUnavailable",
]

YOUTUBE_URL_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/|live/)|youtu\.be/)([0-9A-Za-z_-]{11})"
)


def extract_video_id(text: str) -> str | None:
    """Pulls the 11-character video ID out of common YouTube URL shapes,
    or accepts a bare video ID typed directly."""
    match = YOUTUBE_URL_RE.search(text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", text.strip()):
        return text.strip()
    return None


def build_transcript_api() -> YouTubeTranscriptApi:
    """Creates the transcript API client, routed through a Webshare
    residential proxy when credentials are configured in .env (needed
    because YouTube blocks most VPS / cloud-provider IPs)."""
    username = os.environ.get("WEBSHARE_PROXY_USERNAME")
    password = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    if username and password:
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=username,
                proxy_password=password,
            )
        )
    return YouTubeTranscriptApi()


def list_transcripts(video_id: str):
    """Returns the TranscriptList for a video (one entry per available
    language / manual-vs-auto combination). Raises the youtube_transcript_api
    exceptions re-exported above on failure."""
    return build_transcript_api().list(video_id)


def fetch_transcript_text(transcript_list, video_id: str, lang_code: str, is_generated: bool) -> str:
    """Fetches one transcript and flattens it to a single plain-text string."""
    transcript_obj = (
        transcript_list.find_generated_transcript([lang_code])
        if is_generated
        else transcript_list.find_manually_created_transcript([lang_code])
    )
    fetched = transcript_obj.fetch()
    return " ".join(snippet.text.replace("\n", " ") for snippet in fetched)
