"""
Background job processor.
Handles: single video, list of videos, or a full playlist.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from transcript_client import resolve_videos, get_transcript, parse_input
from cdc_client import find_best_cdc_page
from analyzer import extract_topic_and_claims, compare_claims_to_cdc
from report_renderer import render_video_report, render_job_summary

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def create_job(raw_input: str, provider: str = "claude", api_key: str = "") -> str:
    """Parse raw user input and start a background job. Returns job_id."""
    job_id = str(uuid.uuid4())[:8]
    spec = parse_input(raw_input)
    spec["provider"] = provider
    spec["api_key"]  = api_key
    with _lock:
        _jobs[job_id] = {
            "id":           job_id,
            "raw_input":    raw_input.strip(),
            "provider":     provider,
            "input_type":   spec["type"],   # "playlist" or "videos"
            "status":       "queued",
            "progress":     [],
            "total_videos": None,
            "current_video":0,
            "videos":       [],
            "report_path":  None,
            "created_at":   datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error":        None,
        }
    threading.Thread(target=_run, args=(job_id, spec), daemon=True).start()
    return job_id


def get_job(job_id: str) -> dict | None:
    with _lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def _log(job_id: str, msg: str):
    print(f"[{job_id}] {msg}")
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["progress"].append({
                "time": datetime.now(timezone.utc).isoformat(),
                "message": msg,
            })


def _set(job_id: str, **kw):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def _run(job_id: str, spec: dict):
    try:
        _set(job_id, status="running")
        provider = spec.get("provider", "claude")
        api_key  = spec.get("api_key", "")

        # ── 1. Resolve video list ──────────────────────────────────────────────
        _log(job_id, f"Resolving videos ({spec['type']})…")
        videos = resolve_videos(spec)
        if not videos:
            raise RuntimeError("No valid videos found. Check your input.")
        _log(job_id, f"Found {len(videos)} video(s).")
        _set(job_id, total_videos=len(videos))

        # Label shown in summary report
        if spec["type"] == "playlist":
            input_label = spec["playlist_url"]
        elif len(videos) == 1:
            input_label = videos[0]["url"]
        else:
            input_label = f"{len(videos)} videos"

        results = []

        # ── 2. Process each video ─────────────────────────────────────────────
        for idx, video in enumerate(videos, 1):
            _set(job_id, current_video=idx)
            vid_id    = video["id"]
            vid_title = video["title"]   # plain-English title from yt-dlp
            vid_url   = video["url"]
            _log(job_id, f'[{idx}/{len(videos)}] "{vid_title}"')

            result = {
                "index":    idx,
                "id":       vid_id,
                "title":    vid_title,
                "url":      vid_url,
                "status":   "ok",
                "error":    None,
                "topic":    None,
                "transcript":   None,
                "cdc_source":   None,
                "analysis":     None,
                "report_file":  None,
            }

            try:
                # 2a — Transcript
                _log(job_id, "  Fetching transcript…")
                transcript = get_transcript(vid_id)
                if not transcript:
                    result.update(status="skipped", error="No captions/transcript available.")
                    _log(job_id, "  Skipped — no captions.")
                    results.append(result)
                    continue
                _log(job_id, f"  Transcript: {len(transcript):,} chars")
                result["transcript"] = transcript

                # 2b — Topic + claims
                from analyzer import PROVIDERS
                _log(job_id, f"  Extracting claims with {PROVIDERS.get(provider,{}).get('name', provider)}…")
                extraction = extract_topic_and_claims(vid_title, transcript, provider, api_key)
                topic   = extraction.get("topic", "Unknown")
                query   = extraction.get("cdc_search_query", topic)
                claims  = extraction.get("claims", [])
                result["topic"] = topic
                _log(job_id, f"  Topic: {topic} | {len(claims)} claim(s)")

                if not claims:
                    result.update(status="skipped", error="No verifiable health claims found.")
                    results.append(result)
                    continue

                # 2c — CDC page
                _log(job_id, f'  Searching CDC: "{query}"…')
                cdc = find_best_cdc_page(query) or find_best_cdc_page(topic)
                if not cdc:
                    result.update(status="skipped", error=f"No CDC page found for: {topic}")
                    results.append(result)
                    continue

                result["cdc_source"] = {
                    "name":    cdc["name"],
                    "url":     cdc["sourceUrl"],
                    "id":      cdc["id"],
                }
                _log(job_id, f"  CDC: {cdc['name']} — {cdc['sourceUrl']}")

                # 2d — Comparison
                _log(job_id, f"  Comparing against CDC…")
                analysis = compare_claims_to_cdc(
                    video_title  = vid_title,
                    topic        = topic,
                    claims       = claims,
                    cdc_page_name= cdc["name"],
                    cdc_page_url = cdc["sourceUrl"],
                    cdc_content  = cdc["content"],
                    provider     = provider,
                    api_key      = api_key,
                )
                result["analysis"] = analysis
                sc = analysis.get("overall_score", 0)
                vd = analysis.get("overall_verdict", "?")
                _log(job_id, f"  → {vd} ({sc:.0%})")

                # 2e — Per-video HTML report
                report_file = f"{job_id}_{vid_id}.html"
                render_video_report(result, REPORTS_DIR / report_file)
                result["report_file"] = report_file

            except Exception as ex:
                result.update(status="error", error=str(ex))
                _log(job_id, f"  ERROR: {ex}")
                # Still generate a partial report so the transcript is visible
                report_file = f"{job_id}_{vid_id}.html"
                try:
                    render_video_report(result, REPORTS_DIR / report_file)
                    result["report_file"] = report_file
                except Exception:
                    pass

            results.append(result)

        # ── 3. Summary report ─────────────────────────────────────────────────
        _log(job_id, "Generating summary report…")
        summary_file = f"{job_id}_summary.html"
        render_job_summary(job_id, input_label, results, REPORTS_DIR / summary_file)

        _set(
            job_id,
            status="done",
            videos=results,
            report_path=summary_file,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        _log(job_id, "Complete.")

    except Exception as ex:
        _log(job_id, f"FATAL: {ex}\n{traceback.format_exc()}")
        _set(job_id, status="error", error=str(ex))
