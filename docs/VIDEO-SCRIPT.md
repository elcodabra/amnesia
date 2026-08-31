# Demo video script

**Target: 3:40. Hard limit 4:00.** Record in one take, screen plus voice, no
edits. Judges reward a live demo over a polished one, and an unedited take is
itself evidence that the thing works.

Every number below was read from the live service. Re-run
`scripts/demo_check.py` immediately before recording and update anything that
moved.

---

## Before you press record

**Windows, arranged in advance.** Nothing kills a demo like hunting for a tab.

1. Terminal, large font, `cd ~/src/amnesia`, cleared
2. Browser tab A: <https://amnesia-orkuraibfa-uc.a.run.app>
3. Browser tab B: Cloud Run console, service `amnesia`
4. Browser tab C: Firestore console, collection `amnesia_memory`
5. Claude Code, open, ready to type
6. Cursor, open, ready to type

**Start the slow thing first.** Distillation takes about 90 seconds. Run it in
the terminal at 2:00 and talk over it while it works, so nobody watches a
spinner.

**Kill the noise.** Notifications off, no personal repos with client names on
screen, browser bookmarks bar hidden.

**Say numbers out loud.** They are the strongest thing you have, and a judge
skimming at 1.5x speed hears more than they read.

---

## 0:00 – 0:25 · The hook

> "I have four AI coding agents. Every single morning, all four of them meet me
> for the first time."

**On screen:** Claude Code. Type:

```
what do you know about how I work?
```

Let the empty answer land. Do not talk over it.

> "Claude Code knows nothing about what I did in Cursor yesterday. Codex has
> never heard of the decision I spent two hours making last week. Every session,
> I start over."

**Why this opening:** it is not a description of a product, it is a description
of the judge's own morning.

---

## 0:25 – 0:50 · The insight

> "But the context isn't missing. Every one of these tools writes a full
> transcript to my disk. Months of evidence about how I actually work, and
> nobody reads it."

**On screen:** terminal, one command:

```bash
ls ~/.claude/projects ~/.jcode/sessions | head
```

> "So I built Amnesia. It reads them."

---

## 0:50 – 1:30 · What it already knows

**On screen:** switch to the Amnesia UI, tab A. Do not explain the
architecture. Show the memory.

> "This is running on Cloud Run. It has read 19 of my real sessions across 30
> days, and measured 14.8 active hours of actual work."

Scroll to the beliefs panel.

> "These aren't things I told it. It worked them out. It knows I keep getting
> blocked by expired auth sessions in CLI tools, and it's seen that in eight
> separate sessions."

Point at the evidence count.

> "Every belief carries the sessions it came from. Which means I can argue with
> it."

Click **that's wrong** on any belief, type a correction, submit.

> "And that correction outranks anything the model inferred. Permanently. The
> next background pass can't quietly re-derive it."

**Why this section matters:** provenance and correction are the two things most
memory demos skip, and they are exactly what the Collaborative Partner track
asks for.

---

## 1:30 – 2:10 · The partner, not the chatbot

**On screen:** the chat box. Type slowly enough to read:

```
I need to add rate limiting to my API
```

While it thinks:

> "A generic assistant asks you five questions here, because it's starting from
> nothing."

When the reply lands, point at the tool call line underneath it.

> "It called recall first. Grounded itself. Then asked one question, about my
> stack, because that's the one thing its memory genuinely couldn't answer."

Then point at the second paragraph of the reply.

> "And it volunteered that warning about my Node version drifting from .nvmrc.
> I never told it that. It learned it from watching me hit that wall."

**This is the money shot of the whole video.** Give it three full seconds of
silence before moving on.

---

## 2:10 – 2:35 · It notices what you would not admit

Type:

```
have I been stuck on anything lately?
```

> "The background pass looks for sessions where effort stopped turning into
> progress."

Read the result out loud.

> "Ninety-two minutes. Nineteen messages. The same question asked four different
> ways. I did not enjoy being told that, and it was right."

**Start the distillation now, in the terminal, off-camera or in a corner:**

```bash
curl -X POST https://amnesia-orkuraibfa-uc.a.run.app/api/distill
```

---

## 2:35 – 3:05 · It is an agent, not a web app

**On screen:** Cloud Run console, tab B.

> "This is the service on Cloud Run. It scales to zero between runs, so it costs
> nothing when nobody's looking."

**Switch to Cloud Scheduler** (or show the job list):

> "And this is the part that makes it an agent rather than a page: Cloud
> Scheduler wakes it every hour, whether or not I have anything open. It reads
> new sessions, asks Gemini what they mean, and writes what it learned."

**Switch to the terminal**, where the distill call has now returned:

> "That's the pass running live. Nineteen sessions read, beliefs learned, no
> errors."

**Switch to Firestore, tab C.** Expand one document.

> "Stored in Firestore with its evidence and its confidence, so it survives
> restarts and follows me to any machine."

---

## 3:05 – 3:30 · The part that makes it infrastructure

**On screen:** back to Claude Code. Same question as the opening:

```
what do you know about how I work?
```

Now it answers.

> "Same memory, through MCP. This is Claude Code reading what the background
> agent learned."

**Switch to Cursor.** Ask something that needs the memory:

```
based on what you know about me, what should I watch out for in this project?
```

> "And Cursor knows it too. One memory, every client. That's the whole point:
> your agents stop meeting you for the first time every morning."

---

## 3:30 – 3:50 · The card, and the close

**On screen:** back to the Amnesia UI, click **Regenerate** on the card.

> "It also makes this. A portrait of how I actually work."

Read the nickname aloud.

> "And every number on it is counted, not guessed. Hours are unioned, so two
> agents running at once is one hour, not two. Anything the model inferred is
> capped below anything measured. A guess never outranks a count."

Pause.

> "That's why I'm comfortable posting it."

**Final line, straight to camera or over the UI:**

> "Your agents don't have to meet you for the first time every morning."

---

## If something breaks on camera

**Keep going and say what happened.** An unedited demo that survives a hiccup is
more convincing than a suspiciously perfect one.

| If | Say |
| --- | --- |
| Gemini returns 503 | "That's the primary model at capacity. It's falling back to flash-lite automatically, which is why this still works." |
| A reply is slow | Fill with the architecture: unioned intervals, capped inference, evidence on every belief |
| Distillation is slow | It is meant to be. Say "this normally runs on a schedule, nobody waits for it" |
| The card is unremarkable | Regenerate once. Do not regenerate twice on camera |

---

## Numbers to verify before recording

Run this and update anything that moved:

```bash
.venv/bin/python scripts/demo_check.py
```

| Claim in the script | Live value |
| --- | --- |
| Sessions read | 19 |
| Active hours | 14.8 |
| Days covered | 30 |
| Beliefs learned | 14 |
| Top belief evidence count | 8 sessions |
| Stuck signal | 92 minutes, 19 asks, 4 near-identical |
| Tests passing | 53 |

---

## What to cut if you run long

In this order, and no further:

1. The `ls ~/.claude/projects` shot at 0:25. Say the line instead.
2. The Firestore document expansion. The Scheduler shot carries the point.
3. The Cursor half of the MCP section. Claude Code alone still proves it.

**Never cut:** the empty answer at 0:00, the `.nvmrc` moment at 1:30, or the
Cloud Scheduler shot. Those three are the hook, the proof, and the requirement.
