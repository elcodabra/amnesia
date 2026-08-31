"""The single-page UI.

Kept as one string with no build step, no framework and no CDN. A judge runs
one command and gets the interface; nothing about the demo depends on npm being
in a good mood.
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Amnesia — memory for your AI agents</title>
<style>
  :root {
    --bg: #0b1020; --panel: #131a30; --line: #24304f;
    --text: #e8ecf8; --muted: #8b97b8; --accent: #7c9cff; --accent2: #c084fc;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  header {
    padding: 26px 32px; border-bottom: 1px solid var(--line);
    display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap;
  }
  h1 { margin: 0; font-size: 21px; letter-spacing: .3px; }
  h1 span { background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; background-clip: text; color: transparent; }
  .tag { color: var(--muted); font-size: 13px; }
  main { display: grid; grid-template-columns: 1.15fr .85fr; gap: 22px; padding: 22px 32px 60px; }
  @media (max-width: 980px) { main { grid-template-columns: 1fr; } }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 18px; }
  .panel h2 { margin: 0 0 12px; font-size: 13px; letter-spacing: 1.6px;
    text-transform: uppercase; color: var(--muted); font-weight: 600; }
  #log { height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
  .msg { padding: 11px 14px; border-radius: 11px; max-width: 88%; white-space: pre-wrap; }
  .me { background: #23305a; align-self: flex-end; }
  .ai { background: #1a2340; align-self: flex-start; border: 1px solid var(--line); }
  .tools { font-size: 12px; color: var(--muted); font-family: ui-monospace, Menlo, monospace; }
  form { display: flex; gap: 10px; margin-top: 14px; }
  input[type=text] { flex: 1; background: #0e1526; border: 1px solid var(--line);
    color: var(--text); border-radius: 10px; padding: 12px 14px; font-size: 14px; }
  button { background: linear-gradient(90deg, var(--accent), var(--accent2)); color: #0b1020;
    border: 0; border-radius: 10px; padding: 12px 18px; font-weight: 700; cursor: pointer; }
  button.ghost { background: transparent; border: 1px solid var(--line); color: var(--text);
    font-weight: 500; padding: 7px 12px; font-size: 13px; }
  .belief { border-bottom: 1px solid var(--line); padding: 11px 0; }
  .belief:last-child { border-bottom: 0; }
  .kind { font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px; color: var(--accent); }
  .meta { font-size: 12px; color: var(--muted); margin-top: 5px;
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .corrected { opacity: .5; text-decoration: line-through; }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 8px; }
  .stat b { display: block; font-size: 23px; }
  .stat span { font-size: 11px; color: var(--muted); letter-spacing: 1.1px; text-transform: uppercase; }
  .stuck { background: #2a1a2e; border: 1px solid #5b3f6b; border-radius: 10px;
    padding: 11px 13px; margin-top: 10px; font-size: 13px; }
  #card { width: 100%; border-radius: 14px; margin-top: 12px; display: block; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  pre { white-space: pre-wrap; background: #0e1526; border: 1px solid var(--line);
    border-radius: 10px; padding: 12px; font-size: 12.5px; color: var(--muted); }
</style>
</head>
<body>
<header>
  <h1><span>Amnesia</span></h1>
  <div class="tag">Your AI agents forget you every morning. This one doesn't.</div>
</header>
<main>
  <div>
    <div class="panel">
      <h2>Partner</h2>
      <div id="log"></div>
      <form id="chat">
        <input id="msg" type="text" autocomplete="off"
               placeholder="Ask it to plan something, or tell it how you like to work..."/>
        <button>Send</button>
      </form>
      <div class="row">
        <button class="ghost" type="button" onclick="say('I need to add rate limiting to my API')">Underspecified task</button>
        <button class="ghost" type="button" onclick="say('What do you know about how I work?')">What do you know?</button>
        <button class="ghost" type="button" onclick="say('Have I been stuck on anything lately?')">Am I stuck?</button>
      </div>
    </div>
    <div class="panel" style="margin-top:22px">
      <h2>Measured profile</h2>
      <div class="stats" id="stats"></div>
      <div id="stuck"></div>
    </div>
  </div>
  <div>
    <div class="panel">
      <h2>What it believes about you</h2>
      <div id="beliefs">Loading...</div>
      <div class="row">
        <button class="ghost" type="button" onclick="runDistill()">Run background pass</button>
      </div>
      <pre id="distill" style="display:none"></pre>
    </div>
    <div class="panel" style="margin-top:22px">
      <h2>Working style card</h2>
      <img id="card" alt="Working style card"/>
      <div class="row">
        <button class="ghost" type="button" onclick="document.getElementById('card').src='/api/card.svg?t='+Date.now()">Regenerate</button>
        <button class="ghost" type="button" onclick="copyShare()">Copy share text</button>
      </div>
    </div>
  </div>
</main>
<script>
const log = document.getElementById('log');
const history = [];

function add(text, cls, tools) {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.textContent = text;
  log.appendChild(div);
  if (tools && tools.length) {
    const t = document.createElement('div');
    t.className = 'tools';
    t.textContent = '↳ ' + tools.join('  ');
    log.appendChild(t);
  }
  log.scrollTop = log.scrollHeight;
}

async function send(text) {
  if (!text.trim()) return;
  add(text, 'me');
  history.push({role: 'user', text});
  const thinking = document.createElement('div');
  thinking.className = 'msg ai';
  thinking.textContent = 'thinking...';
  log.appendChild(thinking);
  try {
    const r = await fetch('/api/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, history: history.slice(0, -1)})
    });
    const data = await r.json();
    thinking.remove();
    add(data.reply, 'ai', data.tool_calls);
    history.push({role: 'model', text: data.reply});
    loadBeliefs();
  } catch (e) {
    thinking.remove();
    add('Request failed: ' + e, 'ai');
  }
}

function say(text) { send(text); }

document.getElementById('chat').addEventListener('submit', e => {
  e.preventDefault();
  const input = document.getElementById('msg');
  send(input.value);
  input.value = '';
});

async function loadBeliefs() {
  const r = await fetch('/api/memory');
  const data = await r.json();
  const el = document.getElementById('beliefs');
  if (!data.count) {
    el.innerHTML = '<div class="tag">Nothing learned yet. Run the background pass.</div>';
    return;
  }
  el.innerHTML = data.beliefs.map(b => `
    <div class="belief">
      <div class="kind">${b.kind}</div>
      <div class="${b.status === 'corrected' ? 'corrected' : ''}">${escapeHtml(b.claim)}</div>
      <div class="meta">
        <span>confidence ${b.confidence}</span>
        <span>${b.evidence_count} sessions</span>
        <button class="ghost" onclick="correct('${b.id}')">That's wrong</button>
      </div>
    </div>`).join('');
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

async function correct(id) {
  const correction = prompt('What is actually true?');
  if (!correction) return;
  await fetch('/api/feedback', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({belief_id: id, correction})
  });
  loadBeliefs();
}

async function loadProfile() {
  const r = await fetch('/api/profile');
  const p = await r.json();
  document.getElementById('stats').innerHTML = `
    <div class="stat"><b>${p.active_hours}h</b><span>active</span></div>
    <div class="stat"><b>${p.sessions}</b><span>sessions</span></div>
    <div class="stat"><b>${p.projects.length}</b><span>projects</span></div>
    <div class="stat"><b>${p.peak_hour ?? '--'}:00</b><span>peak</span></div>`;
  document.getElementById('stuck').innerHTML = p.stuck.length
    ? p.stuck.map(s => `<div class="stuck"><b>Stuck signal · ${s.project}</b><br/>${escapeHtml(s.reason)}</div>`).join('')
    : '<div class="tag">No stuck patterns detected.</div>';
}

async function runDistill() {
  const pre = document.getElementById('distill');
  pre.style.display = 'block';
  pre.textContent = 'Reading sessions and distilling with Gemini...';
  const r = await fetch('/api/distill', {method: 'POST'});
  const d = await r.json();
  pre.textContent = JSON.stringify(d, null, 2);
  loadBeliefs();
  document.getElementById('card').src = '/api/card.svg?t=' + Date.now();
}

async function copyShare() {
  const r = await fetch('/api/card');
  const d = await r.json();
  await navigator.clipboard.writeText(d.share_text);
  alert('Copied:\n\n' + d.share_text);
}

document.getElementById('card').src = '/api/card.svg';
loadBeliefs();
loadProfile();
add('I read your real coding sessions across jcode, Claude Code and Codex. Ask me to plan something and I will only ask what I do not already know.', 'ai');
</script>
</body>
</html>
"""
