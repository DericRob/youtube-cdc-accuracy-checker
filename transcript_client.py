"""
YouTube transcript and video metadata extraction.
Handles: single video URL, multiple video URLs, or a playlist URL.
Primary: youtube-transcript-api (InnerTube, no API key)
Fallback: yt-dlp subtitle download
"""

from __future__ import annotations

import re
import subprocess
import os
import tempfile


# ── URL parsing ───────────────────────────────────────────────────────────────

def parse_video_id(url: str) -> str | None:
    """Extract a YouTube video ID from any common URL format."""
    url = url.strip()
    # youtu.be/ID
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # watch?v=ID or shorts/ID or embed/ID
    m = re.search(r"(?:v=|/shorts/|/embed/|/v/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # Bare 11-char ID
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    return None


def is_playlist_url(url: str) -> bool:
    return "playlist?list=" in url or ("/playlist" in url and "list=" in url)


def parse_input(raw: str) -> dict:
    """
    Parse the user's raw input into a job spec.
    Returns:
        {
          "type": "playlist" | "videos",
          "playlist_url": str | None,       # if type == playlist
          "video_urls": [str, ...] | None,  # if type == videos (raw URLs)
        }
    """
    lines = [l.strip() for l in re.split(r"[\n,]+", raw) if l.strip()]

    # If any line looks like a playlist, treat the whole input as a playlist
    for line in lines:
        if is_playlist_url(line):
            return {"type": "playlist", "playlist_url": line, "video_urls": None}

    # Otherwise treat each line as a video URL or ID
    video_urls = [l for l in lines if parse_video_id(l)]
    return {"type": "videos", "playlist_url": None, "video_urls": video_urls}


# ── Playlist enumeration ──────────────────────────────────────────────────────

def get_playlist_videos(playlist_url: str) -> list[dict]:
    """
    Extract all video IDs and plain-English titles from a playlist using yt-dlp.
    Returns list of {id, title, url}.  No video data is downloaded.
    """
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s",
        "--no-warnings",
        playlist_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        videos = []
        for line in result.stdout.strip().splitlines():
            if "\t" in line:
                vid_id, title = line.split("\t", 1)
                vid_id, title = vid_id.strip(), title.strip()
                if vid_id:
                    videos.append({
                        "id": vid_id,
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                    })
        return videos
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timed out fetching playlist. Check the URL and try again.")
    except FileNotFoundError:
        raise RuntimeError("yt-dlp not found. Run: pip install yt-dlp")


def get_video_metadata(video_id: str) -> dict:
    """
    Fetch the plain-English title and URL for a single video using yt-dlp.
    """
    cmd = [
        "yt-dlp",
        "--print", "%(title)s",
        "--no-warnings",
        "--skip-download",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        title = result.stdout.strip().splitlines()[0] if result.stdout.strip() else video_id
        return {
            "id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
    except Exception:
        return {
            "id": video_id,
            "title": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }


def resolve_videos(job_spec: dict) -> list[dict]:
    """
    Convert a job spec into a list of {id, title, url} dicts.
    """
    if job_spec["type"] == "playlist":
        return get_playlist_videos(job_spec["playlist_url"])

    videos = []
    for raw_url in job_spec.get("video_urls") or []:
        vid_id = parse_video_id(raw_url)
        if vid_id:
            meta = get_video_metadata(vid_id)
            videos.append(meta)
    return videos


# ── Transcript extraction ─────────────────────────────────────────────────────

def get_transcript_via_api(video_id: str) -> str | None:
    """Primary: youtube-transcript-api via YouTube InnerTube (no API key)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        try:
            transcript = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        except Exception:
            transcript = api.fetch(video_id)
        snippets = transcript.snippets if hasattr(transcript, "snippets") else transcript
        return " ".join(
            s.text if hasattr(s, "text") else s.get("text", "")
            for s in snippets
        ).strip()
    except Exception:
        return None


def get_transcript_via_ytdlp(video_id: str) -> str | None:
    """Fallback: yt-dlp subtitle download → parse SRT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-auto-sub", "--write-subs",
            "--sub-lang", "en",
            "--convert-subs", "srt",
            "--skip-download", "--no-warnings",
            "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
            for fname in os.listdir(tmpdir):
                if fname.endswith(".srt"):
                    with open(os.path.join(tmpdir, fname), "r", encoding="utf-8") as f:
                        return _parse_srt(f.read())
        except Exception:
            pass
    return None


def _parse_srt(srt_text: str) -> str:
    cleaned = re.sub(r"^\d+\s*$", "", srt_text, flags=re.MULTILINE)
    cleaned = re.sub(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", "", cleaned)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)


def get_transcript(video_id: str) -> str | None:
    """Try API first, fall back to yt-dlp subtitles."""
    t = get_transcript_via_api(video_id)
    if t and len(t) > 100:
        return t
    return get_transcript_via_ytdlp(video_id)
