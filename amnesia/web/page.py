"""The single-page UI.

One string, no build step, no framework, no CDN. A judge runs one command and
gets the interface; nothing about the demo depends on npm being in a good mood.

The layout answers three questions in the order a person asks them: what has it
noticed about me, when did I actually work, and can I talk to it. Charts are
hand-drawn SVG for the same reason there is no framework: a chart library is
another thing that can fail to load while someone is watching.
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Amnesia — memory for your AI agents</title>
<style>
  :root {
    --bg:#0a0e1a; --panel:#111827; --panel2:#161f33; --line:#233049;
    --text:#e9edf7; --muted:#8b98b8; --dim:#5b6784;
    --a1:#60a5fa; --a2:#c084fc; --warn:#f472b6; --ok:#34d399;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--bg); color:var(--text);
    font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  }
  header {
    padding:22px 28px; border-bottom:1px solid var(--line);
    display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  }
  h1 { margin:0; font-size:20px; letter-spacing:.2px; }
  h1 span {
    background:linear-gradient(90deg,var(--a1),var(--a2));
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .sub { color:var(--muted); font-size:13.5px; }
  .live { margin-left:auto; display:flex; align-items:center; gap:7px;
          color:var(--muted); font-size:12.5px; }
  .dot { width:7px; height:7px; border-radius:50%; background:var(--ok); }

  .wrap { max-width:1240px; margin:0 auto; padding:22px 28px 70px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  @media (max-width:1000px){ .grid { grid-template-columns:1fr; } }

  .card {
    background:var(--panel); border:1px solid var(--line);
    border-radius:14px; padding:18px 20px;
  }
  .card + .card { margin-top:18px; }
  .card h2 {
    margin:0 0 4px; font-size:12px; letter-spacing:1.5px; text-transform:uppercase;
    color:var(--muted); font-weight:600;
  }
  .card .hint { color:var(--dim); font-size:12.5px; margin:0 0 14px; }

  /* ---- headline stats ---- */
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }
  @media (max-width:700px){ .stats { grid-template-columns:repeat(2,1fr); } }
  .stat {
    background:var(--panel); border:1px solid var(--line);
    border-radius:14px; padding:16px 18px;
  }
  .stat b { display:block; font-size:30px; line-height:1.15; }
  .stat span { font-size:11px; color:var(--muted); letter-spacing:1.2px; text-transform:uppercase; }
  .stat em { display:block; font-style:normal; font-size:12px; color:var(--dim); margin-top:3px; }

  /* ---- calendar ---- */
  .months { display:flex; gap:26px; flex-wrap:wrap; }
  .month-label { font-size:12px; color:var(--muted); margin-bottom:8px; }
  .cal { display:grid; grid-template-columns:repeat(7,1fr); gap:5px; }
  .dow { font-size:10px; color:var(--dim); text-align:center; padding-bottom:2px; }
  .day {
    aspect-ratio:1; border-radius:6px; background:#0e1626; border:1px solid #1b2540;
    display:flex; align-items:center; justify-content:center;
    font-size:11px; color:var(--dim); cursor:default; position:relative;
  }
  .day.has { cursor:pointer; color:#04101f; font-weight:700; border-color:transparent; }
  .day.has:hover { outline:2px solid var(--a1); outline-offset:1px; }
  .day.sel { outline:2px solid var(--a2); outline-offset:1px; }
  .day.empty { background:transparent; border-color:transparent; }
  .legend { display:flex; align-items:center; gap:7px; margin-top:12px;
            font-size:11.5px; color:var(--dim); }
  .sw { width:13px; height:13px; border-radius:3px; }

  /* ---- day detail ---- */
  .entry { border-top:1px solid var(--line); padding:11px 0; }
  .entry:first-child { border-top:0; }
  .entry .meta { font-size:12px; color:var(--muted); display:flex; gap:9px; flex-wrap:wrap; }
  .entry .txt { margin-top:4px; font-size:14px; }
  .pill {
    display:inline-block; padding:1px 8px; border-radius:20px;
    background:#1c2740; color:#a9b8dc; font-size:11px;
  }

  /* ---- beliefs ---- */
  .belief { border-top:1px solid var(--line); padding:12px 0; }
  .belief:first-child { border-top:0; }
  .kind { font-size:10.5px; letter-spacing:1.2px; text-transform:uppercase; color:var(--a1); }
  .bmeta { display:flex; gap:10px; align-items:center; margin-top:6px;
           font-size:12px; color:var(--muted); flex-wrap:wrap; }
  .bar { width:64px; height:4px; border-radius:2px; background:#1c2740; overflow:hidden; }
  .bar i { display:block; height:100%; background:linear-gradient(90deg,var(--a1),var(--a2)); }
  .corrected { opacity:.45; text-decoration:line-through; }

  /* ---- chat ---- */
  #log { height:290px; overflow-y:auto; display:flex; flex-direction:column; gap:11px; }
  .msg { padding:10px 13px; border-radius:11px; max-width:88%; white-space:pre-wrap; font-size:14px; }
  .me { background:#22314f; align-self:flex-end; }
  .ai { background:var(--panel2); align-self:flex-start; border:1px solid var(--line); }
  .tools { font-size:11.5px; color:var(--dim); font-family:ui-monospace,Menlo,monospace; }
  form { display:flex; gap:9px; margin-top:13px; }
  input[type=text] {
    flex:1; background:#0c1424; border:1px solid var(--line); color:var(--text);
    border-radius:10px; padding:11px 13px; font-size:14px;
  }
  button {
    background:linear-gradient(90deg,var(--a1),var(--a2)); color:#08101f;
    border:0; border-radius:10px; padding:11px 17px; font-weight:700; cursor:pointer;
  }
  button.ghost {
    background:transparent; border:1px solid var(--line); color:var(--text);
    font-weight:500; padding:6px 11px; font-size:12.5px;
  }
  button.ghost:hover { border-color:var(--a1); }
  .row { display:flex; gap:7px; flex-wrap:wrap; margin-top:11px; }

  .stuck {
    background:#2a1a2e; border:1px solid #5b3f6b; border-radius:10px;
    padding:11px 13px; margin-top:10px; font-size:13.5px;
  }
  #card { width:100%; border-radius:12px; display:block; margin-top:6px; }
  pre {
    white-space:pre-wrap; background:#0c1424; border:1px solid var(--line);
    border-radius:10px; padding:11px; font-size:12px; color:var(--muted);
    max-height:190px; overflow:auto;
  }
  .empty-note { color:var(--dim); font-size:13.5px; }
</style>
</head>
<body>
<header>
  <h1><span>Amnesia</span></h1>
  <div class="sub">Your AI agents forget you every morning. This one doesn't.</div>
  <div class="live"><span class="dot"></span><span id="live">reading your sessions…</span></div>
</header>

<div class="wrap">
  <div class="stats" id="stats"></div>

  <div class="grid">
    <div>
      <div class="card">
        <h2>When you actually worked</h2>
        <p class="hint">Counted from real sessions. Overlapping clients count once, not twice. Click any day.</p>
        <div class="months" id="calendar"></div>
        <div class="legend">
          <span>less</span>
          <span class="sw" style="background:#131d33"></span>
          <span class="sw" style="background:#1e3a8a"></span>
          <span class="sw" style="background:#3b82f6"></span>
          <span class="sw" style="background:#93c5fd"></span>
          <span>more</span>
        </div>
      </div>

      <div class="card" id="day-card" style="display:none">
        <h2 id="day-title">Day</h2>
        <p class="hint" id="day-sum"></p>
        <div id="day-entries"></div>
      </div>

      <div class="card">
        <h2>The shape of your day</h2>
        <p class="hint">Sessions started per hour, local time</p>
        <div id="hours"></div>
      </div>

      <div class="card">
        <h2>Where the hours went</h2>
        <p class="hint">Active hours per project</p>
        <div id="projects"></div>
      </div>
    </div>

    <div>
      <div class="card">
        <h2>What it worked out about you</h2>
        <p class="hint">Learned from your sessions, never told to it. Every claim names its evidence.</p>
        <div id="beliefs" class="empty-note">Loading…</div>
        <div class="row">
          <button class="ghost" onclick="runDistill()">Run background pass</button>
          <button class="ghost" onclick="document.getElementById('distill').style.display='none'">Hide output</button>
        </div>
        <pre id="distill" style="display:none"></pre>
      </div>

      <div class="card" id="stuck-card" style="display:none">
        <h2>It noticed you were stuck</h2>
        <p class="hint">Sessions where effort stopped turning into progress</p>
        <div id="stuck"></div>
      </div>

      <div class="card">
        <h2>Ask it something</h2>
        <p class="hint">It reads its memory first, so it only asks what it cannot already know.</p>
        <div id="log"></div>
        <form id="chat">
          <input id="msg" type="text" autocomplete="off"
                 placeholder="Give it a vague task and watch what it asks…"/>
          <button>Send</button>
        </form>
        <div class="row">
          <button class="ghost" onclick="say('I need to add rate limiting to my API')">Vague task</button>
          <button class="ghost" onclick="say('What do you know about how I work?')">What do you know?</button>
          <button class="ghost" onclick="say('Have I been stuck on anything lately?')">Am I stuck?</button>
        </div>
      </div>

      <div class="card">
        <h2>Your working style card</h2>
        <p class="hint">Every number on it is counted, not guessed</p>
        <img id="card" alt="Working style card"/>
        <div class="row">
          <button class="ghost" onclick="reloadCard()">Regenerate</button>
          <button class="ghost" onclick="copyShare()">Copy share text</button>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let CAL = null, selected = null;

/* ------------------------------------------------------------------ stats */
function renderStats(t) {
  $('stats').innerHTML = `
    <div class="stat"><b>${t.active_hours}h</b><span>active</span><em>overlaps counted once</em></div>
    <div class="stat"><b>${t.sessions}</b><span>sessions</span><em>over ${t.span_days} days</em></div>
    <div class="stat"><b>${t.peak_hour ?? '--'}:00</b><span>peak hour</span><em>${esc(t.chronotype)}</em></div>
    <div class="stat"><b>${t.median_minutes}m</b><span>median session</span><em>${esc(t.focus)}</em></div>`;
  $('live').textContent = `${t.sessions} sessions · ${t.clients.map(c => c[0]).join(', ')}`;
}

/* --------------------------------------------------------------- calendar */
// A month grid rather than a heatmap strip: people navigate their own past by
// date, and "which Tuesday was that" is not a question a strip can answer.
function shade(hours, max) {
  if (!hours) return null;
  const t = Math.min(hours / (max || 1), 1);
  if (t > 0.66) return '#93c5fd';
  if (t > 0.33) return '#3b82f6';
  if (t > 0.12) return '#1e3a8a';
  return '#131d33';
}

function renderCalendar(days) {
  const keys = Object.keys(days).sort();
  if (!keys.length) { $('calendar').innerHTML = '<span class="empty-note">No sessions found.</span>'; return; }
  const max = Math.max(...Object.values(days));
  const months = [...new Set(keys.map(k => k.slice(0, 7)))].sort();
  const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  $('calendar').innerHTML = months.map(m => {
    const [y, mo] = m.split('-').map(Number);
    const first = new Date(y, mo - 1, 1);
    // Monday-first: the week people plan in, not the week the US prints.
    const offset = (first.getDay() + 6) % 7;
    const total = new Date(y, mo, 0).getDate();
    let cells = ['Mo','Tu','We','Th','Fr','Sa','Su'].map(d => `<div class="dow">${d}</div>`).join('');
    cells += Array(offset).fill('<div class="day empty"></div>').join('');
    for (let d = 1; d <= total; d++) {
      const key = `${y}-${String(mo).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const h = days[key] || 0;
      const bg = shade(h, max);
      cells += bg
        ? `<div class="day has" style="background:${bg}" data-day="${key}"
             title="${key}: ${h}h" onclick="openDay('${key}')">${d}</div>`
        : `<div class="day">${d}</div>`;
    }
    return `<div><div class="month-label">${names[mo-1]} ${y}</div><div class="cal">${cells}</div></div>`;
  }).join('');
}

async function openDay(day) {
  document.querySelectorAll('.day.sel').forEach(el => el.classList.remove('sel'));
  const el = document.querySelector(`.day[data-day="${day}"]`);
  if (el) el.classList.add('sel');
  selected = day;

  $('day-card').style.display = 'block';
  $('day-title').textContent = day;
  $('day-sum').textContent = 'Loading…';
  $('day-entries').innerHTML = '';
  $('day-card').scrollIntoView({behavior:'smooth', block:'nearest'});

  const d = await (await fetch(`/api/day/${day}`)).json();
  const projects = d.projects.map(p => p[0]).join(', ') || 'unknown';
  $('day-sum').textContent =
    `${d.active_hours}h active · ${d.sessions} sessions · ${projects}`;
  $('day-entries').innerHTML = d.entries.map(e => `
    <div class="entry">
      <div class="meta">
        <span>${esc(e.at)}</span>
        <span class="pill">${esc(e.project)}</span>
        <span class="pill">${esc(e.client)}</span>
        <span>${e.minutes} min</span>
        <span>${e.turns} messages</span>
      </div>
      <div class="txt">${esc(e.opening || '(no opening message)')}</div>
    </div>`).join('') || '<span class="empty-note">No sessions.</span>';
}

/* ----------------------------------------------------------------- charts */
// Hand-drawn SVG rather than a chart library: one less thing that can fail to
// load while somebody is watching.
function renderHours(hours) {
  const max = Math.max(...hours, 1);
  const W = 560, H = 130, pad = 22, bw = (W - pad * 2) / 24;
  let bars = '', labels = '';
  hours.forEach((v, h) => {
    const bh = v ? Math.max(3, (v / max) * (H - 42)) : 0;
    const x = pad + h * bw;
    if (bh) bars += `<rect x="${x+1.5}" y="${H-26-bh}" width="${bw-3}" height="${bh}"
      rx="2.5" fill="${v === max ? '#c084fc' : '#3b82f6'}"><title>${h}:00 — ${v} sessions</title></rect>`;
    if (h % 3 === 0) labels += `<text x="${x+bw/2}" y="${H-9}" fill="#5b6784"
      font-size="10" text-anchor="middle">${h}</text>`;
  });
  $('hours').innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${bars}${labels}</svg>`;
}

function renderProjects(projects) {
  if (!projects.length) { $('projects').innerHTML = '<span class="empty-note">No projects yet.</span>'; return; }
  const max = Math.max(...projects.map(p => p[1]), 0.1);
  $('projects').innerHTML = projects.map(([name, h]) => `
    <div style="display:flex;align-items:center;gap:11px;margin:9px 0">
      <div style="width:150px;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;
                  white-space:nowrap">${esc(name)}</div>
      <div style="flex:1;height:9px;background:#141d31;border-radius:5px;overflow:hidden">
        <div style="width:${Math.max(3,(h/max)*100)}%;height:100%;
                    background:linear-gradient(90deg,#60a5fa,#c084fc)"></div>
      </div>
      <div style="width:52px;text-align:right;font-size:13px;color:#8b98b8">${h}h</div>
    </div>`).join('');
}

function renderStuck(stuck) {
  if (!stuck.length) return;
  $('stuck-card').style.display = 'block';
  $('stuck').innerHTML = stuck.slice(0,3).map(s => `
    <div class="stuck">
      <b>${esc(s.project)}</b> · severity ${s.severity}<br/>${esc(s.reason)}
    </div>`).join('');
}

/* ---------------------------------------------------------------- beliefs */
async function loadBeliefs() {
  const d = await (await fetch('/api/memory')).json();
  if (!d.count) {
    $('beliefs').innerHTML =
      '<span class="empty-note">Nothing learned yet. Run the background pass.</span>';
    return;
  }
  $('beliefs').innerHTML = d.beliefs.map(b => `
    <div class="belief">
      <div class="kind">${esc(b.kind)}</div>
      <div class="${b.status === 'corrected' ? 'corrected' : ''}">${esc(b.claim)}</div>
      <div class="bmeta">
        <span class="bar"><i style="width:${Math.round(b.confidence*100)}%"></i></span>
        <span>${b.evidence_count} sessions</span>
        <button class="ghost" onclick="correct('${b.id}')">That's wrong</button>
      </div>
    </div>`).join('');
}

async function correct(id) {
  const correction = prompt('What is actually true?');
  if (!correction) return;
  await fetch('/api/feedback', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({belief_id:id, correction})
  });
  loadBeliefs();
}

async function runDistill() {
  const pre = $('distill');
  pre.style.display = 'block';
  pre.textContent = 'Reading your sessions and distilling with Gemini… (~90s)';
  try {
    const d = await (await fetch('/api/distill', {method:'POST'})).json();
    pre.textContent = JSON.stringify(d, null, 2);
    loadBeliefs(); reloadCard();
  } catch (e) { pre.textContent = 'Failed: ' + e; }
}

/* ------------------------------------------------------------------- chat */
const history = [];
function add(text, cls, tools) {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.textContent = text;
  $('log').appendChild(div);
  if (tools && tools.length) {
    const t = document.createElement('div');
    t.className = 'tools';
    t.textContent = '↳ called ' + tools.join('  ');
    $('log').appendChild(t);
  }
  $('log').scrollTop = $('log').scrollHeight;
}

async function send(text) {
  if (!text.trim()) return;
  add(text, 'me');
  history.push({role:'user', text});
  const thinking = document.createElement('div');
  thinking.className = 'msg ai';
  thinking.textContent = 'thinking…';
  $('log').appendChild(thinking);
  $('log').scrollTop = $('log').scrollHeight;
  try {
    const r = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message:text, history:history.slice(0,-1)})
    });
    const d = await r.json();
    thinking.remove();
    add(d.reply, 'ai', d.tool_calls);
    history.push({role:'model', text:d.reply});
    loadBeliefs();
  } catch (e) { thinking.remove(); add('Request failed: ' + e, 'ai'); }
}
const say = send;

$('chat').addEventListener('submit', e => {
  e.preventDefault();
  send($('msg').value);
  $('msg').value = '';
});

/* ------------------------------------------------------------------- card */
function reloadCard() { $('card').src = '/api/card.svg?t=' + Date.now(); }
async function copyShare() {
  const d = await (await fetch('/api/card')).json();
  await navigator.clipboard.writeText(d.share_text);
  alert('Copied:\n\n' + d.share_text);
}

/* ------------------------------------------------------------------- boot */
async function boot() {
  reloadCard();
  loadBeliefs();
  try {
    CAL = await (await fetch('/api/calendar')).json();
    renderStats(CAL.totals);
    renderCalendar(CAL.days);
    renderHours(CAL.hours);
    renderProjects(CAL.projects);
    renderStuck(CAL.stuck);
    // Open the busiest day, so the panel is never an empty box on arrival.
    const busiest = Object.entries(CAL.days).sort((a,b) => b[1]-a[1])[0];
    if (busiest) openDay(busiest[0]);
  } catch (e) {
    $('live').textContent = 'could not load: ' + e;
  }
}

add("I read your real sessions across jcode, Claude Code and Codex. Ask me to plan something and I'll only ask what I don't already know.", 'ai');
boot();
</script>
</body>
</html>
"""
