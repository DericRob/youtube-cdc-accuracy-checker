"""
HTML report generation.
Per-video reports + job summary.
Each report explicitly shows:
  - YouTube video plain-English title + URL
  - Exact CDC URL and page title used for comparison
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import html as _html

VERDICT_META = {
    "TRUE":         ("#d4edda", "#155724", "✅ TRUE"),
    "MOSTLY_TRUE":  ("#d4edda", "#155724", "✅ MOSTLY TRUE"),
    "PARTLY_TRUE":  ("#fff3cd", "#856404", "⚠️ PARTLY TRUE"),
    "MOSTLY_FALSE": ("#f8d7da", "#721c24", "❌ MOSTLY FALSE"),
    "FALSE":        ("#f8d7da", "#721c24", "❌ FALSE"),
    "UNSUPPORTED":  ("#e2e3e5", "#383d41", "❓ UNSUPPORTED"),
}

def _score_color(score: float) -> str:
    if score >= 0.80: return "#28a745"
    if score >= 0.60: return "#ffc107"
    return "#dc3545"

def e(s) -> str:
    return _html.escape(str(s or ""))

def _badge(verdict: str) -> str:
    bg, fg, label = VERDICT_META.get(verdict, ("#e2e3e5", "#383d41", verdict))
    return f'<span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:700;">{label}</span>'

SHARED_CSS = """
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     margin:0;background:#f5f5f5;color:#222}
.wrap{max-width:960px;margin:0 auto;padding:24px 16px}
h1{font-size:1.5rem;margin:0 0 4px}
h2{font-size:1.15rem;margin:28px 0 10px}
.card{background:#fff;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.1);
      padding:22px 26px;margin-bottom:18px}
.src-box{border-left:4px solid #0056b3;background:#e8f4fd;padding:12px 16px;
         border-radius:0 8px 8px 0;margin:10px 0}
.src-box.yt{border-color:#c00;background:#fff5f5}
.lbl{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#666;margin-bottom:3px}
.val{font-weight:700;font-size:.95rem}
.url{font-size:.82rem;margin-top:3px;word-break:break-all}
.score-row{display:flex;align-items:center;gap:16px;margin:10px 0}
.score-num{font-size:2.8rem;font-weight:700;line-height:1}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{text-align:left;padding:8px 10px;background:#f0f0f0;border-bottom:2px solid #ddd}
td{padding:8px 10px;border-bottom:1px solid #eee;vertical-align:top}
.back{font-size:.85rem;display:block;margin-bottom:14px}
.foot{font-size:.75rem;color:#999;margin-top:20px}
.claim-block{border-radius:8px;padding:14px 16px;margin-bottom:10px}
</style>
"""


def render_video_report(result: dict, output_path: Path):
    vid_title  = result.get("title", "Unknown Video")   # plain-English title
    vid_url    = result.get("url", "")
    topic      = result.get("topic", "")
    transcript = result.get("transcript") or ""
    error      = result.get("error") or ""
    cdc        = result.get("cdc_source") or {}
    analysis   = result.get("analysis") or {}
    has_analysis = bool(analysis)

    score      = analysis.get("overall_score", 0)
    verdict    = analysis.get("overall_verdict", "UNKNOWN")
    summary    = analysis.get("summary", "")
    verdicts   = analysis.get("claim_verdicts", [])
    color      = _score_color(score)

    # Detect API credits error specifically
    credits_error = "credit balance is too low" in error.lower() or "credit balance" in error.lower()

    error_banner = ""
    if error and not has_analysis:
        if credits_error:
            error_banner = """
<div style="background:#fff3cd;border:2px solid #ffc107;border-radius:10px;
            padding:16px 20px;margin-bottom:18px">
  <div style="font-size:1rem;font-weight:700;color:#856404;margin-bottom:6px">
    ⚠️ Analysis Could Not Run — Anthropic API Credits Required
  </div>
  <div style="font-size:.88rem;color:#856404;line-height:1.6">
    The transcript was fetched successfully but Claude could not analyze it because
    the API key has no remaining credits.<br>
    <strong>Fix:</strong> Add credits at
    <a href="https://console.anthropic.com/settings/billing" target="_blank">
    console.anthropic.com/settings/billing</a>, then re-run the analysis.
  </div>
</div>"""
        else:
            error_banner = f"""
<div style="background:#f8d7da;border:2px solid #f5c6cb;border-radius:10px;
            padding:16px 20px;margin-bottom:18px">
  <div style="font-size:1rem;font-weight:700;color:#721c24;margin-bottom:6px">
    ❌ Analysis Failed
  </div>
  <div style="font-size:.88rem;color:#721c24">{e(error)}</div>
</div>"""

    claims_html = ""
    for cv in verdicts:
        v = cv.get("verdict", "UNSUPPORTED")
        bg, fg, _ = VERDICT_META.get(v, ("#e2e3e5", "#383d41", v))
        claims_html += f"""
<div class="claim-block" style="background:{bg}22;border-left:4px solid {bg}">
  <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
    <p style="margin:0 0 8px;font-style:italic;color:#444">"{e(cv.get('claim',''))}"</p>
    {_badge(v)}
  </div>
  <div style="font-size:.88rem;color:#333;margin-top:6px">
    <strong style="color:#0056b3">CDC says:</strong> {e(cv.get('cdc_position',''))}
  </div>
  <div style="font-size:.83rem;color:#555;margin-top:5px">{e(cv.get('explanation',''))}</div>
</div>"""

    now = datetime.now(timezone.utc)

    score_section = ""
    if has_analysis:
        score_section = f"""
  <!-- ③ Overall Score -->
  <div class="card">
    <h2 style="margin-top:0">Overall Accuracy vs CDC</h2>
    <div class="score-row">
      <div class="score-num" style="color:{color}">{score:.0%}</div>
      <div>
        <div style="font-size:1.05rem;font-weight:700;color:{color}">
          {e(verdict.replace('_',' '))}
        </div>
        <div style="font-size:.87rem;color:#555;margin-top:4px">{e(summary)}</div>
      </div>
    </div>
  </div>

  <!-- ④ Claim-by-claim -->
  <div class="card">
    <h2 style="margin-top:0">Claim-by-Claim Analysis</h2>
    <p style="font-size:.8rem;color:#777;margin-top:0">
      Each claim compared against:
      <a href="{e(cdc.get('url',''))}" target="_blank">{e(cdc.get('name',''))}</a>
    </p>
    {claims_html or '<p style="color:#777">No claims analyzed.</p>'}
  </div>"""

    cdc_section = ""
    if cdc:
        cdc_section = f"""
  <!-- ② CDC Source — exact URL and page title used for comparison -->
  <div class="card">
    <h2 style="margin-top:0">📋 CDC Source Used for Comparison</h2>
    <div class="src-box">
      <div class="lbl">CDC Page Title</div>
      <div class="val">{e(cdc.get('name',''))}</div>
      <div class="lbl" style="margin-top:8px">CDC Comparison URL</div>
      <div class="url">
        <a href="{e(cdc.get('url',''))}" target="_blank">{e(cdc.get('url',''))}</a>
      </div>
    </div>
    <p style="font-size:.8rem;color:#666;margin:8px 0 0">
      Content retrieved via the
      <a href="https://tools.cdc.gov/api/docs/info.aspx" target="_blank">CDC Content Syndication API</a>
      on {now.strftime('%B %d, %Y')}.
    </p>
  </div>"""

    transcript_section = ""
    if transcript:
        transcript_section = f"""
  <!-- Transcript -->
  <details class="card" style="cursor:default">
    <summary style="cursor:pointer;font-size:1rem;font-weight:700;list-style:none;
                    display:flex;align-items:center;gap:8px;outline:none">
      <span style="font-size:1.1rem">📝</span> Full Video Transcript
      <span style="font-size:.78rem;font-weight:400;color:#888;margin-left:4px">
        ({len(transcript):,} chars) — click to expand
      </span>
    </summary>
    <div style="margin-top:14px;max-height:500px;overflow-y:auto;
                background:#f9f9f9;border-radius:6px;padding:14px 16px;
                font-size:.87rem;line-height:1.7;color:#333;white-space:pre-wrap;
                border:1px solid #e0e0e0">{e(transcript)}</div>
  </details>"""
    elif not transcript and not has_analysis:
        transcript_section = """
  <div class="card" style="border:1px solid #dee2e6;background:#f8f9fa">
    <div style="color:#6c757d;font-size:.9rem">
      📝 <strong>No transcript available</strong> — this video may have no captions,
      be a music-only clip, or a silent visual.
    </div>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Accuracy Report — {e(vid_title)}</title>
{SHARED_CSS}
</head>
<body>
<div class="wrap">
  <a class="back" href="javascript:history.back()">← Back to summary</a>

  {error_banner}

  <!-- ① YouTube Video — plain-English title prominently displayed -->
  <div class="card">
    <h1>Accuracy Report</h1>
    <div class="src-box yt">
      <div class="lbl">📺 YouTube Video</div>
      <div class="val">{e(vid_title)}</div>
      <div class="url"><a href="{e(vid_url)}" target="_blank">{e(vid_url)}</a></div>
    </div>
    {f'<div style="font-size:.82rem;color:#666;margin-top:6px">Health Topic: <strong>{e(topic)}</strong></div>' if topic else ''}
    <div style="font-size:.82rem;margin-top:8px;padding:6px 10px;border-radius:6px;
                background:{'#d4edda' if transcript else '#f8d7da'};
                color:{'#155724' if transcript else '#721c24'}">
      {'✅ Transcript fetched: ' + f'{len(transcript):,} chars' if transcript else '❌ No transcript available'}
    </div>
  </div>

  {cdc_section}
  {score_section}
  {transcript_section}

  <p class="foot">
    Generated {now.strftime('%Y-%m-%d %H:%M UTC')} ·
    YouTube–CDC Accuracy Checker
  </p>
</div>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")


def render_job_summary(job_id: str, input_label: str, videos: list[dict], output_path: Path):
    """Summary report for a full job (playlist or multi-video)."""
    analyzed = [v for v in videos if v.get("status") == "ok" and v.get("analysis")]
    credits_errors = [v for v in videos if "credit balance" in (v.get("error") or "").lower()]
    skipped  = [v for v in videos if v.get("status") in ("skipped", "error")]
    avg = sum(v["analysis"]["overall_score"] for v in analyzed) / len(analyzed) if analyzed else 0
    color = _score_color(avg)
    now = datetime.now(timezone.utc)

    # Global credits warning banner
    credits_banner = ""
    if credits_errors and not analyzed:
        credits_banner = f"""
  <div style="background:#fff3cd;border:2px solid #ffc107;border-radius:10px;
              padding:18px 22px;margin-bottom:18px">
    <div style="font-size:1.05rem;font-weight:700;color:#856404;margin-bottom:8px">
      ⚠️ No Videos Were Analyzed — Anthropic API Credits Required
    </div>
    <div style="font-size:.9rem;color:#856404;line-height:1.7">
      Transcripts were fetched from YouTube successfully, but Claude could not analyze them
      because the API key has no remaining credits. This is why all scores show 0%.<br><br>
      <strong>To fix:</strong> Add credits at
      <a href="https://console.anthropic.com/settings/billing" target="_blank" style="color:#856404">
      console.anthropic.com/settings/billing</a>, then re-submit the playlist.
      ({len(credits_errors)} of {len(videos)} videos affected)
    </div>
  </div>"""

    rows = ""
    for v in videos:
        an   = v.get("analysis") or {}
        sc   = an.get("overall_score")
        verd = an.get("overall_verdict", "—")
        cdc  = v.get("cdc_source") or {}
        err  = v.get("error") or ""
        transcript = v.get("transcript") or ""

        score_cell = f'<strong style="color:{_score_color(sc)}">{sc:.0%}</strong>' if sc is not None else "—"
        verd_cell  = _badge(verd) if verd != "—" else "—"

        if v.get("report_file"):
            link_cell = f'<a href="{e(v["report_file"])}">View Report</a>'
        elif "credit balance" in err.lower():
            link_cell = '<span style="color:#856404;font-size:.82rem">⚠️ API credits needed</span>'
        elif err:
            link_cell = f'<span style="color:#856404;font-size:.82rem">{e(err[:80])}</span>'
        else:
            link_cell = "—"

        cdc_cell = (
            f'<a href="{e(cdc.get("url",""))}" target="_blank" style="font-size:.82rem">'
            f'{e(cdc.get("name",""))}</a>'
            if cdc.get("url") else "—"
        )

        transcript_cell = (
            f'<span style="color:#155724;font-size:.82rem">✅ {len(transcript):,} chars</span>'
            if transcript
            else '<span style="color:#6c757d;font-size:.82rem">—</span>'
        )

        rows += f"""<tr>
          <td>
            <strong>{e(v.get('title',''))}</strong><br>
            <a href="{e(v.get('url',''))}" target="_blank" style="font-size:.78rem">YouTube ↗</a>
          </td>
          <td>{transcript_cell}</td>
          <td style="font-size:.85rem">{e(v.get('topic',''))}</td>
          <td>{cdc_cell}</td>
          <td>{score_cell}</td>
          <td>{verd_cell}</td>
          <td>{link_cell}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CDC Accuracy Report — Summary</title>
{SHARED_CSS}
</head>
<body>
<div class="wrap">
  {credits_banner}

  <div class="card">
    <h1>YouTube–CDC Accuracy Report</h1>
    <div class="src-box yt">
      <div class="lbl">📺 Source</div>
      <div class="val" style="font-size:.9rem">{e(input_label)}</div>
    </div>
    <div class="score-row" style="margin-top:14px">
      <div class="score-num" style="color:{color}">{avg:.0%}</div>
      <div>
        <div style="font-weight:700;color:{color}">Average Accuracy vs CDC</div>
        <div style="font-size:.85rem;color:#555;margin-top:3px">
          {len(analyzed)} of {len(videos)} video(s) analyzed · {len(skipped)} skipped/errored
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2 style="margin-top:0">Videos</h2>
    <p style="font-size:.82rem;color:#777;margin-top:0">
      Each video was compared against the most relevant CDC.gov page for its health topic.
      The exact CDC source used is shown in each video's report.
    </p>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Video Title</th>
          <th>Transcript</th>
          <th>Health Topic</th>
          <th>CDC Source Used</th>
          <th>Score</th>
          <th>Verdict</th>
          <th>Report</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
  </div>

  <p class="foot">
    Job ID: {job_id} ·
    {now.strftime('%Y-%m-%d %H:%M UTC')} ·
    CDC data via <a href="https://tools.cdc.gov/api/docs/info.aspx" target="_blank">
    CDC Content Syndication API</a>
  </p>
</div>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")
