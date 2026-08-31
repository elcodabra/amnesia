# Devpost form: copy-paste answers

Every field on the submission form, filled in, in order. Numbers verified
against the live service on 2026-08-31.

---

## Project name

```
Amnesia
```

## Elevator pitch (max 200 characters)

```
Your AI agents forget you every morning. Amnesia reads your real coding sessions across every AI client, learns how you actually work, and becomes the memory they are missing.
```

*(173 characters)*

---

## Category

```
The Collaborative Partner
```

---

## About the project

### Inspiration

I have four AI coding agents. Every single morning, all four of them meet me for
the first time.

Claude Code knows nothing about what I did in Cursor yesterday. Codex has never
heard of the architecture decision I spent two hours making last week. Every
session begins with me re-explaining who I am, how I like to work, and what I
already tried.

Then I noticed something: the context is not missing. Every one of these tools
writes a full transcript to my disk. Months of evidence about how I actually
work, sitting there, read by nobody.

### What it does

Amnesia is a background agent that reads those transcripts, learns how you
actually work, and serves that memory back to every AI client you use.

**It arrives already knowing you.** Give it an underspecified task and it does
not interrogate you from zero. Asked to add rate limiting to my API, it recalled
what it knew, asked a single question about my stack, and volunteered a warning
about my Node version drifting from `.nvmrc`, because it had learned from my own
sessions that this is what breaks my environment. I never told it that.

**It shows its evidence.** Every belief carries the sessions that produced it.
Nothing is asserted about you that you cannot trace and overrule in one click,
and a correction outranks anything the model inferred, permanently.

**It notices when you are stuck.** The hourly background pass looks for sessions
where effort stopped converting into progress. On my own history it found a
92-minute session where I asked nearly the same question seven times, which was
uncomfortable and correct.

**It follows you into your editor.** An MCP bridge exposes the same memory to
Claude Code and Cursor. State a preference once and every client knows it.

**It gives you something to share.** A Working Style Card generated from measured
facts, not from vibes.

On my own history it read 19 sessions across 30 days, measured 13.9 active
hours, and distilled 7 durable beliefs, each citing the sessions behind it.

### How I built it

The system splits into four layers, and the split is the point.

**Ingestion** normalises transcripts from jcode, Claude Code and Codex into one
timeline. Each client gets a small adapter that knows only its own layout, so
the rest of the system never learns which tool a session came from. Tool output,
reasoning traces, file contents and paths are stripped here, before anything is
stored or sent.

**Measurement** counts what can be counted: active hours, chronotype, session
rhythm, context switching. Session spans are unioned rather than summed, so two
clients open for an hour is one hour of work rather than two. This layer needs
no model and no network, which means the agent is never empty on a first run.

**Distillation** sends batches of sessions to Gemini 3.5 Flash and asks what
they mean. Every returned claim must cite session ids that actually exist;
claims citing invented sessions are dropped, because a claim the UI cannot
justify is worse than no claim. Inferred confidence is capped at 0.75 while
measured facts are uncapped, so a guess can never outrank a count.

**The agent** is a bounded Gemini tool loop over four tools: recall, remember,
correct and check-stuck. Its system prompt is built fresh from current memory
and current measurements, so it is grounded before it says a word.

Deployed on Cloud Run with Firestore for cross-session memory and Cloud
Scheduler driving the hourly background pass. The service scales to zero between
runs, so the whole thing costs close to nothing while still being a genuinely
asynchronous agent rather than a web app that happens to call a model.

### Challenges I ran into

**A guess outranking a count.** The first version let Gemini assign its own
confidence, and inferred beliefs immediately outranked measured facts in
ranking. Capping inference below measurement fixed the ordering and, more
importantly, made every number defensible enough to put on a card people share.

**Three bugs that only exist in the cloud.** Cloud Run sets
`GOOGLE_CLOUD_PROJECT` on every service, and passing it alongside an API key
makes the Gemini API reject the call outright: the first deployed distill pass
failed while identical code worked locally. Google's frontend intercepts
`/healthz` before the request reaches the container, so the conventional health
path answered 404 from outside. And `gemini-3.5-flash` returned 503 under load
while `flash-lite` answered in under a second. Each is now covered by a test.

**Summing durations claimed 30 hours in a 24-hour day.** Running two agents at
once is normal, and every parallel session was being counted twice. Unioning
intervals fixed it.

**Truncating the wrong end.** The outcome of a session is at its end: whether it
worked, or whether the person gave up. Early versions clipped the tail and
distilled the greeting.

### Accomplishments that I'm proud of

The agent told me something true about myself that I had not noticed and would
not have admitted: that I had spent 92 minutes asking one question seven
different ways. That is the moment the project stopped being a demo.

Every number it reports can be defended. Hours are unioned, evidence is cited,
inference is capped below measurement, and 51 tests cover the arithmetic and the
rules with no network and no cloud account required.

### What I learned

The evidence about how we work already exists; collection was never the hard
part. The hard part is that a transcript says what happened, and a person needs
to know what it means.

And a memory without provenance cannot be corrected. Once every belief carried
its sessions, "that's wrong" became a one-click action with somewhere to put the
correction, instead of an argument with a model.

### What's next for Amnesia

Browser and ChatGPT web sessions, which no local hook can currently observe.
Per-project memory scoping, so a work machine and a side project do not share a
profile. And team mode, where a shared Amnesia onboards a new engineer by
knowing how the team actually works rather than how the wiki says it does.

---

## Built with

```
gemini, google-genai, google-adk, cloud-run, firestore, cloud-scheduler, cloud-build, python, fastapi, mcp, docker
```

---

## Try it out links

```
https://amnesia-orkuraibfa-uc.a.run.app
https://github.com/elcodabra/amnesia
```

---

## Technologies used (long form, if a separate field appears)

- **Gemini 3.5 Flash** via the Google GenAI SDK, for distillation, the agent
  tool loop and the card's interpretation, with automatic fallback to
  `gemini-3.5-flash-lite` when the primary model is at capacity
- **Google GenAI SDK** with declared function tools and a bounded tool loop
- **Cloud Run** for the service, **Firestore** for cross-session memory,
  **Cloud Scheduler** for the hourly background pass, **Cloud Build** for the
  image
- **FastAPI** and **uvicorn** in a single container, no build step, no CDN
- **MCP** over stdio JSON-RPC, so Claude Code and Cursor read the same memory
- **Python 3.11**, 51 tests that run with no network and no cloud account

## Other data sources used

Only the user's own AI coding transcripts, already written to disk by tools they
already run. No new tracking is introduced and no third-party data is used.
Ingestion strips tool output, reasoning traces, file contents and paths before
anything is stored or transmitted.

---

## Repository access

The repository is private. Access has been granted to `devposttesting`
(the GitHub account whose public email is `testing@devpost.com`).

If judges from Google need access under a different account, the repository can
be made public immediately on request.

---

## Verified before submission

| Claim in this form | How it was checked |
| --- | --- |
| 19 sessions, 13.9 active hours, 30 days | `scripts/demo_check.py` against live data |
| 7 beliefs, all with evidence | `GET /api/memory` on the deployed service |
| Stuck signal, 92 minutes, 7 repeats | `GET /api/profile` on the deployed service |
| Distillation runs in the cloud | `POST /api/distill` returned 7 beliefs, no error |
| Correction outranks inference | `POST /api/feedback` on the deployed service |
| Scheduler runs hourly | `gcloud scheduler jobs list`, state ENABLED |
| 51 tests pass | `pytest tests/ -q` |
