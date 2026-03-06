"""
YouTube–CDC Accuracy Checker
~/Documents/CDC/youtube-accuracy/app.py

Run:  python app.py
      No environment variables required — provider and API key are entered in the browser.
"""

import os
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from processor import create_job, get_job

app = Flask(__name__)
REPORTS_DIR = Path(__file__).parent / "reports"

# ─────────────────────────────────────────────────────────────────────────────
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube–CDC Accuracy Checker</title>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     margin:0;background:#f0f4f8;min-height:100vh;
     display:flex;align-items:flex-start;justify-content:center;padding:40px 16px}
.card{background:#fff;border-radius:14px;box-shadow:0 4px 20px rgba(0,0,0,.1);
      padding:36px 40px;max-width:640px;width:100%}
h1{font-size:1.65rem;margin:0 0 4px;color:#1a1a2e}
.sub{color:#666;font-size:.92rem;margin-bottom:26px;line-height:1.5}
label{font-weight:600;font-size:.88rem;display:block;margin-bottom:6px}
textarea,input[type=password],input[type=text]{
  width:100%;padding:12px 14px;border:2px solid #ddd;border-radius:8px;
  font-size:.92rem;font-family:inherit;outline:none;transition:border .2s}
textarea{resize:vertical;min-height:110px;line-height:1.5}
textarea:focus,input:focus{border-color:#0056b3}
.hint{font-size:.78rem;color:#888;margin-top:5px;line-height:1.5}
.section{margin-top:20px}
.provider-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
.pcard{border:2px solid #ddd;border-radius:10px;padding:12px 10px;cursor:pointer;
       text-align:center;transition:all .2s;user-select:none;background:#fafafa}
.pcard:hover{border-color:#0056b3;background:#f0f7ff}
.pcard.active{border-color:#0056b3;background:#e8f4fd}
.pcard .icon{font-size:1.5rem;display:flex;align-items:center;justify-content:center;height:36px;margin-bottom:6px}
.pcard .icon img{display:block}
.pcard .name{font-size:.82rem;font-weight:700;color:#333}
.pcard .sub2{font-size:.72rem;color:#777;margin-top:2px}
.key-wrap{position:relative}
.key-wrap input{padding-right:44px}
.toggle-key{position:absolute;right:12px;top:50%;transform:translateY(-50%);
            background:none;border:none;cursor:pointer;font-size:1rem;padding:0;
            color:#888;width:auto;margin:0}
.key-hint{font-size:.76rem;color:#888;margin-top:5px;line-height:1.5}
.key-hint a{color:#0056b3}
.saved-badge{display:inline-block;background:#d4edda;color:#155724;font-size:.72rem;
             padding:2px 8px;border-radius:20px;margin-left:6px;font-weight:700}
button.primary{width:100%;margin-top:18px;padding:13px;background:#0056b3;color:#fff;
       border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;
       transition:background .2s}
button.primary:hover{background:#004494}
button.primary:disabled{background:#aaa;cursor:not-allowed}
.err{color:#c00;font-size:.85rem;margin-top:8px;display:none}
.divider{border:none;border-top:1px solid #eee;margin:22px 0}
.examples h3{font-size:.85rem;font-weight:700;margin:0 0 8px;color:#444}
.ex{font-size:.78rem;color:#0056b3;cursor:pointer;margin-bottom:5px;
    display:block;text-decoration:underline}
.ex:hover{color:#004494}
.how{font-size:.82rem;color:#555;line-height:1.7}
.how ol{margin:6px 0 0;padding-left:18px}
</style>
</head>
<body>
<div class="card">
  <h1>🎬 YouTube–CDC Accuracy Checker</h1>
  <p class="sub">
    Analyzes YouTube videos for health accuracy against official CDC.gov content.
    Each video is checked claim-by-claim — reports show the exact CDC source used.
  </p>

  <!-- YouTube Input -->
  <label for="inp">YouTube URL(s) or Playlist</label>
  <textarea id="inp" placeholder="Paste one of:
• A single video URL
• Multiple video URLs (one per line)
• A playlist URL"></textarea>
  <div class="hint">Accepts: single video · multiple videos (one per line) · full playlist URL</div>

  <!-- AI Provider Selection -->
  <div class="section">
    <label>AI Provider</label>
    <div class="provider-grid">
      <div class="pcard" id="p-claude" onclick="selectProvider('claude')">
        <span class="icon">
          <img src="https://cdn.simpleicons.org/anthropic/191919" width="32" height="32" alt="Anthropic" onerror="this.replaceWith('🤖')">
        </span>
        <div class="name">Claude</div>
        <div class="sub2">Anthropic</div>
      </div>
      <div class="pcard" id="p-openai" onclick="selectProvider('openai')">
        <span class="icon">
          <img src="https://cdn.simpleicons.org/chatgpt/191919" width="32" height="32" alt="ChatGPT" onerror="this.replaceWith('💬')">
        </span>
        <div class="name">ChatGPT</div>
        <div class="sub2">OpenAI</div>
      </div>
      <div class="pcard" id="p-gemini" onclick="selectProvider('gemini')">
        <span class="icon">
          <img src="https://cdn.simpleicons.org/googlegemini/191919" width="32" height="32" alt="Gemini" onerror="this.replaceWith('✨')">
        </span>
        <div class="name">Gemini</div>
        <div class="sub2">Google</div>
      </div>
    </div>

    <!-- API Key Input -->
    <label id="key-label">
      API Key
      <span class="saved-badge" id="saved-badge" style="display:none">✓ Saved</span>
    </label>
    <div class="key-wrap">
      <input type="password" id="apikey" placeholder="Paste your API key here" oninput="onKeyInput()">
      <button class="toggle-key" onclick="toggleKeyVis()" title="Show/hide key">👁</button>
    </div>
    <div class="key-hint" id="key-hint"></div>
  </div>

  <button class="primary" id="btn" onclick="go()">Analyze</button>
  <div class="err" id="err"></div>

  <hr class="divider">

  <div class="examples">
    <h3>Examples — click to fill</h3>
    <span class="ex" onclick="fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ')">Single video URL</span>
    <span class="ex" onclick="fill('https://www.youtube.com/playlist?list=PLvrp9iOILTQaJa78zFQ0QgvShQ2HEwHxP')">COVID playlist (210 videos)</span>
  </div>

  <div class="how" style="margin-top:16px">
    <strong>How it works:</strong>
    <ol>
      <li>Transcripts extracted via YouTube's internal API (no quota)</li>
      <li>AI identifies the health topic and key factual claims</li>
      <li>The most relevant CDC.gov page is found via the CDC Syndication API</li>
      <li>Claims are compared against CDC content, verdict per claim</li>
      <li>Report cites the exact CDC URL used — every time</li>
    </ol>
  </div>
</div>

<script>
const HINTS = {
  claude: 'Get your key at <a href="https://console.anthropic.com/settings/api-keys" target="_blank">console.anthropic.com</a> · Model: claude-sonnet-4-6',
  openai: 'Get your key at <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a> · Model: gpt-4o-mini',
  gemini: 'Get your key at <a href="https://aistudio.google.com/app/apikey" target="_blank">aistudio.google.com</a> · Model: gemini-1.5-flash (free tier available)',
};
const STORE_KEY = 'cdc_checker_prefs';
const STORAGE = sessionStorage;

let currentProvider = 'claude';

function loadPrefs(){
  try {
    const p = JSON.parse(STORAGE.getItem(STORE_KEY)||'{}');
    if(p.provider) selectProvider(p.provider, false);
    if(p.keys && p.keys[currentProvider]){
      document.getElementById('apikey').value = p.keys[currentProvider];
      document.getElementById('saved-badge').style.display='inline-block';
    }
  } catch(e){}
}

function saveKey(){
  try {
    const p = JSON.parse(STORAGE.getItem(STORE_KEY)||'{}');
    if(!p.keys) p.keys = {};
    const k = document.getElementById('apikey').value.trim();
    if(k) p.keys[currentProvider] = k;
    p.provider = currentProvider;
    STORAGE.setItem(STORE_KEY, JSON.stringify(p));
  } catch(e){}
}

function selectProvider(id, loadSaved=true){
  currentProvider = id;
  document.querySelectorAll('.pcard').forEach(c => c.classList.remove('active'));
  document.getElementById('p-'+id).classList.add('active');
  document.getElementById('key-hint').innerHTML = HINTS[id] || '';
  if(loadSaved){
    try {
      const p = JSON.parse(STORAGE.getItem(STORE_KEY)||'{}');
      const saved = p.keys && p.keys[id];
      document.getElementById('apikey').value = saved || '';
      document.getElementById('saved-badge').style.display = saved ? 'inline-block' : 'none';
    } catch(e){ document.getElementById('apikey').value=''; }
  }
}

function onKeyInput(){
  document.getElementById('saved-badge').style.display='none';
}

function toggleKeyVis(){
  const f = document.getElementById('apikey');
  f.type = f.type==='password' ? 'text' : 'password';
}

function fill(s){ document.getElementById('inp').value=s; }

async function go(){
  const inp = document.getElementById('inp').value.trim();
  const key = document.getElementById('apikey').value.trim();
  const err = document.getElementById('err');
  const btn = document.getElementById('btn');
  err.style.display='none';
  if(!inp){ err.textContent='Please enter at least one YouTube URL.'; err.style.display='block'; return; }
  if(!key){ err.textContent='Please enter your API key for the selected AI provider.'; err.style.display='block'; return; }
  saveKey();
  btn.disabled=true; btn.textContent='Starting…';
  try{
    const r = await fetch('/analyze',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({input:inp, provider:currentProvider, api_key:key})
    });
    const d = await r.json();
    if(d.job_id){ window.location.href='/status/'+d.job_id; }
    else{ throw new Error(d.error||'Unknown error'); }
  }catch(ex){
    err.textContent='Error: '+ex.message; err.style.display='block';
    btn.disabled=false; btn.textContent='Analyze';
  }
}

document.addEventListener('keydown',e=>{ if(e.key==='Enter'&&e.ctrlKey) go(); });
loadPrefs();
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
STATUS_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Processing… — CDC Checker</title>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     margin:0;background:#f0f4f8;min-height:100vh;
     display:flex;align-items:flex-start;justify-content:center;padding:40px 16px}
.card{background:#fff;border-radius:14px;box-shadow:0 4px 20px rgba(0,0,0,.1);
      padding:30px 36px;max-width:720px;width:100%}
h1{font-size:1.35rem;margin:0 0 4px}
.sub{color:#666;font-size:.85rem;margin-bottom:18px;word-break:break-all}
.bar-wrap{background:#f0f0f0;border-radius:8px;height:10px;margin:10px 0}
.bar{background:#0056b3;height:10px;border-radius:8px;transition:width .4s}
.log{background:#1a1a2e;color:#a8dadc;border-radius:8px;padding:14px 16px;
     font-family:monospace;font-size:.78rem;max-height:340px;overflow-y:auto;margin-top:14px}
.ll{margin:2px 0}
.btn{display:inline-block;padding:10px 24px;background:#0056b3;color:#fff;
     border-radius:8px;text-decoration:none;font-weight:600;font-size:.95rem}
.btn:hover{background:#004494}
.s-running{color:#0056b3;font-weight:700}
.s-done{color:#28a745;font-weight:700}
.s-error{color:#dc3545;font-weight:700}
</style>
</head>
<body>
<div class="card">
  <h1>🔬 Analyzing…</h1>
  <p class="sub" id="sub">Loading…</p>

  <div>Status: <span id="slbl" class="s-running">queued</span>
       · <span id="plbl">0 / ? videos</span></div>
  <div class="bar-wrap"><div class="bar" id="bar" style="width:0%"></div></div>

  <div id="rarea" style="display:none;margin:14px 0">
    <a id="rlink" class="btn" href="#">📊 View Full Report</a>
  </div>

  <div class="log" id="log"><div class="ll">Waiting…</div></div>
</div>

<script>
const jobId="{{job_id}}";
let timer;
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
async function poll(){
  try{
    const r=await fetch('/api/status/'+jobId);
    const j=await r.json();
    document.getElementById('sub').textContent=j.raw_input||'';
    const sl=document.getElementById('slbl');
    sl.textContent=j.status; sl.className='s-'+j.status;
    const tot=j.total_videos||'?', cur=j.current_video||0;
    document.getElementById('plbl').textContent=cur+' / '+tot+' videos';
    if(tot!=='?') document.getElementById('bar').style.width=Math.round(cur/tot*100)+'%';
    const lines=(j.progress||[]).map(p=>
      `<div class="ll">[${esc(p.time.split('T')[1].split('.')[0])}] ${esc(p.message)}</div>`
    ).join('');
    const lg=document.getElementById('log');
    lg.innerHTML=lines||'<div class="ll">Starting…</div>';
    lg.scrollTop=lg.scrollHeight;
    if(j.status==='done'){
      clearInterval(timer);
      document.getElementById('bar').style.width='100%';
      if(j.report_path){
        document.getElementById('rlink').href='/reports/'+j.report_path;
        document.getElementById('rarea').style.display='block';
      }
    } else if(j.status==='error') clearInterval(timer);
  }catch(e){console.error(e);}
}
poll(); timer=setInterval(poll,2000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/analyze", methods=["POST"])
def analyze():
    data     = request.get_json(force=True)
    raw      = (data.get("input")    or "").strip()
    provider = (data.get("provider") or "claude").strip()
    api_key  = (data.get("api_key")  or "").strip()
    if not raw:
        return jsonify({"error": "No input provided"}), 400
    if not api_key:
        return jsonify({"error": "No API key provided"}), 400
    if provider not in ("claude", "openai", "gemini"):
        return jsonify({"error": f"Unknown provider: {provider}"}), 400
    job_id = create_job(raw, provider=provider, api_key=api_key)
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status_page(job_id):
    return STATUS_HTML.replace("{{job_id}}", job_id)

@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(REPORTS_DIR, filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n  YouTube–CDC Accuracy Checker")
    print(f"  Open:   http://localhost:{port}")
    print(f"  Models: Claude · ChatGPT · Gemini (select in browser)")
    print(f"  Stop:   Ctrl+C\n")
    app.run(debug=False, port=port, threaded=True)
