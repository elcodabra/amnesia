# Submission kit

**Live:** <https://amnesia-orkuraibfa-uc.a.run.app>
**Project:** `amnesia-agent-87425` · us-central1 · Cloud Run + Firestore + Cloud Scheduler

Everything needed to submit, in the order Devpost asks for it. Numbers marked
`[LIVE]` must be re-read from the running service before recording, because they
change as sessions accumulate and a stale figure on screen is the fastest way to
lose a judge's trust.

---

## 1. Category

**The Collaborative Partner**

Why this track and not Taskmaster: Amnesia's job is not to complete a chore. It
is to lead a conversation with someone it already knows, ask only what its
memory cannot answer, and capture every correction so the next conversation
starts further along.

---

## 2. Elevator pitch (Devpost tagline, 200 chars)

> Your AI agents forget you every morning. Amnesia reads your real coding sessions across every AI client, learns how you actually work, and becomes the memory they are missing.

---

## 3. Text description

### The problem

You have been working with AI coding agents for months. Claude Code knows
nothing about what you did in Cursor yesterday. ChatGPT has never heard of the
architecture decision you spent two hours making in Codex last week. Every
session, you re-explain who you are, how you like to work, and what you already
tried.

The context is not missing. It is sitting on your disk, in the transcripts every
one of these tools already writes. Nobody reads it.

### What it does

Amnesia is a background agent that reads those transcripts, learns how you
actually work, and serves that memory back to every AI client you use.

- **It arrives already knowing you.** Give it an underspecified task and it does
  not interrogate you from zero. It knows your projects, your rhythm and the
  mistakes you repeat, so the single question it asks is the one its memory
  genuinely cannot answer.
- **It shows its evidence.** Every belief carries the sessions that produced it.
  Nothing is asserted about you that you cannot trace and overrule in one click,
  and a correction outranks anything the model inferred, permanently.
- **It notices when you are stuck.** The background pass looks for sessions
  where effort stopped converting into progress: the same question asked five
  times, ninety minutes on one thread, wording that says the fix is not landing.
- **It follows you into your editor.** An MCP bridge exposes the same memory to
  Claude Code and Cursor. State a preference once and every client knows it.
- **It gives you something to share.** A Working Style Card, generated from
  measured facts, not from vibes.

### Features and functionality

| Feature | What it does |
| --- | --- |
| Cross-client ingestion | Normalises jcode, Claude Code and Codex transcripts into one timeline |
| Gemini distillation | Turns raw sessions into durable beliefs with cited evidence |
| Measured profile | Active hours, chronotype, session rhythm, context switching, counted from timestamps |
| Stuck detection | Flags sessions where repetition and frustration replaced progress |
| Feedback capture | One-click correction; the correction outranks the inference |
| MCP bridge | Four tools, so Claude Code and Cursor read the same memory |
| Working Style Card | Shareable SVG portrait generated from real data |
| Background pass | Cloud Scheduler runs distillation hourly, with or without a user present |

### Technologies used

- **Gemini 3.5 Flash** via `google-genai`, for distillation, the agent tool loop
  and the card's interpretation
- **Google GenAI SDK** with declared function tools and a bounded tool loop
- **Cloud Run** for the service, **Firestore** for cross-session memory,
  **Cloud Scheduler** for the background pass, **Cloud Build** for the image
- **FastAPI** and **uvicorn**, one process, no build step, no CDN
- **MCP** over stdio JSON-RPC, dependency-free

### Other data sources used

Only the user's own AI coding transcripts, already written to disk by tools they
already run. No new tracking is introduced and no third-party data is used.
Ingestion strips tool output, reasoning traces, file contents and paths before
anything is stored or sent.

### Findings and learnings

**The evidence already exists; nobody reads it.** Collection was never the hard
part. The hard part is that a transcript says what happened, and a person needs
to know what it means.

**A guess must never outrank a count.** The first version let Gemini assign its
own confidence, and inferred beliefs immediately outranked measured facts in
ranking. Capping inference at 0.75 while measurement stays uncapped fixed the
ranking and, more importantly, made every number defensible enough to publish.

**A memory without provenance cannot be corrected.** Once each belief carried
its sessions, "that's wrong" became a one-click action with somewhere to put the
correction, rather than an argument with a model.

**Truncate from the front, not the back.** The outcome of a session is at its
end: whether it worked, or whether the person gave up. Early versions clipped
the tail and distilled the greeting.

**Union intervals, never sum durations.** Running two agents at once is normal.
Summing session lengths claimed 30 hours in a 24-hour day the first time it ran.

---

## 4. Demo video script (~4 minutes)

Record unedited, in one take, screen plus voice. Judges reward a live demo over
a polished one.

### 0:00–0:30 · The problem, stated as a fact about them

> "I have four AI coding agents. Every single morning, all four of them meet me
> for the first time."

Open Claude Code, ask "what do you know about how I work?", show the empty
answer. This is the hook: the audience lives this daily.

### 0:30–1:10 · What it already knows

Open the Amnesia UI. Do not explain the architecture yet, show the memory.

- Point at the beliefs panel: claims about how you work, each with an evidence
  count.
- Click **that's wrong** on one, type the correction, show it replaced. Say the
  line that matters: *"A correction outranks anything the model inferred, and it
  survives the next distill pass."*

### 1:10–2:00 · The partner, not the chatbot

Type: *"I need to add rate limiting to my API."*

Show that it does not ask five generic questions. It grounds itself in memory
(the tool call line is visible under the reply) and asks one thing its memory
cannot answer.

Then: *"Have I been stuck on anything lately?"* Show the real stuck signal.
`[LIVE]` Currently: 7 near-identical asks, 92 minutes on one thread.

### 2:00–2:45 · The background agent on Google Cloud

This is the section judges score for Production Readiness. Show, in order:

1. Cloud Run console, service healthy, revision list.
2. Cloud Scheduler job `amnesia-distill`, hourly schedule.
3. `curl -X POST https://amnesia-orkuraibfa-uc.a.run.app/api/distill` and the
   JSON that comes back: sessions read, beliefs learned. It takes about 90
   seconds, so start it before you need it on screen.
4. Firestore console, the `amnesia_memory` collection, one document expanded to
   show `evidence` and `confidence`.

Say: *"This runs whether or not I have the page open. That is the difference
between an app and an agent."*

### 2:45–3:20 · The part that makes it infrastructure

Switch to Claude Code. Ask *"what do you know about how I work?"* again.

Now it answers, from the same memory, through MCP. Then tell it a new
preference, switch to Cursor, and show Cursor already knows it.

This is the strongest shot in the video. Do not rush it.

### 3:20–4:00 · The card, and the close

Show the Working Style Card generating. Read the nickname aloud.

> "Every number on that card is counted, not guessed. That is why I am
> comfortable posting it."

Close on the one line: *"Your agents don't have to meet you for the first time
every morning."*

---

## 5. Social post (bonus points)

Include `#AllThingsAgenticHackathon`. Attach the card image.

> My AI agents used to forget me every morning.
>
> So I built Amnesia: it reads my real coding sessions across Claude Code,
> Cursor and Codex, learns how I actually work, and hands that memory back to
> every one of them.
>
> It read `[LIVE]` sessions and told me I am an afternoon builder who ships in
> rapid-fire bursts. It also caught me asking the same question 7 times in 92
> minutes, which stung.
>
> Every belief cites the sessions it came from, so I can tell it it's wrong.
> Built on Gemini 3.5 Flash, Cloud Run, Firestore and Cloud Scheduler.
>
> #AllThingsAgenticHackathon

---

## 6. Pre-submission checklist

- [ ] Repo public, or shared with `testing@devpost.com` and `cloudhackathons@google.com`
- [x] README has spin-up instructions that work on a clean clone
- [x] Architecture diagram present (mermaid in README, renders on GitHub)
- [ ] Demo video under 4 minutes, shows Google Cloud console
- [x] Category selected: **The Collaborative Partner**
- [x] Hosted URL provided: https://amnesia-orkuraibfa-uc.a.run.app
- [ ] Social post published with `#AllThingsAgenticHackathon`
- [ ] `[LIVE]` numbers re-read from the running service before recording
