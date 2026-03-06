# YouTube–CDC Accuracy Checker
`~/Documents/CDC/`

Checks YouTube health videos against official CDC.gov pages — claim by claim. Reports show the plain-English video title and the exact CDC URL used for every comparison.

## Setup

```bash
cd ~/Documents/CDC
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5050**

## What You Can Paste

| Input | Example |
|---|---|
| Single video URL | `https://www.youtube.com/watch?v=VIDEO_ID` |
| Multiple video URLs | One URL per line |
| Playlist URL | `https://www.youtube.com/playlist?list=PLAYLIST_ID` |
| Short URL | `https://youtu.be/VIDEO_ID` |
| Bare video ID | `dQw4w9WgXcQ` |

## What the Report Shows

- **YouTube Video** — Plain-English title + URL (prominent, top of every report)
- **CDC Source Used for Comparison** — Exact CDC page name + URL, clearly labeled
- **Claim-by-Claim Table** — Verdict (TRUE → FALSE), CDC's position, explanation
- **Overall Score** — 0–100% accuracy, plain-English verdict

## How It Works

1. `yt-dlp` gets video IDs + plain-English titles (no API key, no quota)
2. `youtube-transcript-api` fetches captions via YouTube's InnerTube API (no API key)
3. `yt-dlp` subtitle download as fallback if captions unavailable
4. Claude extracts the health topic and 5–10 verifiable claims
5. CDC Content Syndication API (`tools.cdc.gov/api/v2`) finds the best CDC page
6. Claude compares each claim against CDC content and assigns a verdict
7. HTML report generated — one per video + a summary for the full job

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask web app |
| `processor.py` | Background job orchestration |
| `transcript_client.py` | YouTube transcript + URL parsing |
| `cdc_client.py` | CDC Syndication API wrapper |
| `analyzer.py` | Claude topic/claim extraction + comparison |
| `report_renderer.py` | HTML report generation |
| `reports/` | Generated HTML reports |
