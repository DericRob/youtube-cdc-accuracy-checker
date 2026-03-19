"""
Multi-provider AI analysis:
  Supports Claude (Anthropic), ChatGPT (OpenAI), and Gemini (Google).
  1. Extract medical topic + key claims from transcript
  2. Compare claims against CDC authoritative content
"""

from __future__ import annotations

import json

PROVIDERS = {
    "claude":  {"name": "Claude (Anthropic)",  "model": "claude-sonnet-4-6"},
    "openai":  {"name": "ChatGPT (OpenAI)",     "model": "gpt-4o-mini"},
    "gemini":  {"name": "Gemini (Google)",      "model": "gemini-1.5-flash"},
}


def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _call(provider: str, api_key: str, prompt: str, max_tokens: int) -> str:
    """Dispatch a single prompt to the chosen provider and return the text response."""
    if provider == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=PROVIDERS["claude"]["model"],
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=PROVIDERS["openai"]["model"],
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    elif provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=PROVIDERS["gemini"]["model"],
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return resp.text

    else:
        raise ValueError(f"Unknown provider: {provider!r}. Must be one of: {list(PROVIDERS)}")


def extract_topic_and_claims(video_title: str, transcript: str,
                              provider: str, api_key: str) -> dict:
    """
    Returns:
        {
          "topic": "Type 2 Diabetes",
          "cdc_search_query": "type 2 diabetes symptoms",
          "claims": ["Claim text…", …]
        }
    """
    excerpt = transcript[:12000]
    prompt = f"""You are a medical fact-checking assistant. Analyze this YouTube video and extract health claims for CDC verification.

YouTube Video Title: {video_title}

Transcript (may be truncated):
{excerpt}

Tasks:
1. Identify the primary medical/health topic
2. Extract 5–10 specific, verifiable health claims made in the video
3. Write a short CDC search query (2–5 words) to find the most relevant CDC page

Only extract factual health claims (e.g., "Sugar causes diabetes", "Vaccine X prevents Y").
Ignore opinions, personal anecdotes, and non-health content.

Respond ONLY with valid JSON:
{{
  "topic": "Plain-English topic name",
  "cdc_search_query": "2-5 word search query",
  "claims": ["Claim 1", "Claim 2", "..."]
}}"""

    text = _call(provider, api_key, prompt, max_tokens=1024)
    return _parse_json(text)


def compare_claims_to_cdc(
    video_title: str,
    topic: str,
    claims: list[str],
    cdc_page_name: str,
    cdc_page_url: str,
    cdc_content: str,
    provider: str,
    api_key: str,
) -> dict:
    """
    Returns:
        {
          "overall_score": 0.0–1.0,
          "overall_verdict": "ACCURATE|MOSTLY_ACCURATE|MIXED|MOSTLY_INACCURATE|INACCURATE",
          "summary": "Plain-English summary",
          "claim_verdicts": [
            {
              "claim": "...",
              "verdict": "TRUE|MOSTLY_TRUE|PARTLY_TRUE|MOSTLY_FALSE|FALSE|UNSUPPORTED",
              "cdc_position": "What CDC says",
              "explanation": "Why this verdict"
            }
          ]
        }
    """
    claims_txt = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
    prompt = f"""You are a medical fact-checker. Compare health claims from a YouTube video against the official CDC position.

VIDEO TITLE: "{video_title}"
HEALTH TOPIC: {topic}

CLAIMS FROM THE VIDEO:
{claims_txt}

CDC SOURCE: {cdc_page_name}
CDC URL: {cdc_page_url}
CDC CONTENT:
{cdc_content[:8000]}

For each claim, assign one verdict:
  TRUE          – Matches CDC accurately
  MOSTLY_TRUE   – Largely correct, minor oversimplification
  PARTLY_TRUE   – Mix of accurate and inaccurate elements
  MOSTLY_FALSE  – Contradicts CDC in significant ways
  FALSE         – Directly contradicts clear CDC statements
  UNSUPPORTED   – CDC content does not address this claim

Respond ONLY with valid JSON:
{{
  "overall_score": 0.75,
  "overall_verdict": "MOSTLY_ACCURATE",
  "summary": "2–3 sentence plain-English summary of the video's overall accuracy vs CDC.",
  "claim_verdicts": [
    {{
      "claim": "Original claim text",
      "verdict": "TRUE",
      "cdc_position": "What CDC says on this point",
      "explanation": "Why this verdict was assigned"
    }}
  ]
}}

overall_score: 0.0 (completely wrong) – 1.0 (perfectly accurate)."""

    text = _call(provider, api_key, prompt, max_tokens=2048)
    return _parse_json(text)
