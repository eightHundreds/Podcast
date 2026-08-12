---
name: notebooklm-podcast
description: >
  Drive Gemini Notebook / NotebookLM in the user's real browser to turn chaptered
  documents into Chinese Audio Overviews (podcasts), one per chapter. Use when
  the user wants NotebookLM podcasts, Audio Overview per chapter, upload EPUB/md
  chapters into a notebook, generate 中文播客, or runs /notebooklm-podcast.
  Requires kimi-webbridge for browser control.
---

# NotebookLM chapter podcasts

Turn chapter sources into **one Chinese Audio Overview per chapter** in the user's logged-in Gemini Notebook (notebook.google.com / notebooklm.google.com).

**Stack:** kimi-webbridge (session + `group_title` in the user's language) · page `fetch` with cookies for **batchexecute** / upload · UI for Audio Overview when reliable.

**Leading words:** **source** (uploaded doc), **artifact** (generated Audio Overview), **trusted click** (user gesture; synthetic click may not download).

## Preconditions

1. kimi-webbridge daemon + extension ready (`kimi-webbridge start` if needed).
2. User Google account known; switch via AccountChooser if wrong account is active.
3. Chapter files ready (ignore prefaces unless asked). Prefer one file per chapter (`.md` / `.txt`).

**Done when:** correct account visible in the account chip; chapter files exist on disk.

## Steps

### 1. Open NotebookLM on the right account

- Navigate `https://notebooklm.google.com/` or `https://notebook.google.com/` with a task session.
- If the account chip is wrong, go to AccountChooser with `continue=` back to NotebookLM and pick the requested account.
- Prefer `authuser=` that matches the chosen account for later deep links.

**Done when:** homepage loads and the account chip matches the user.

### 2. Create a notebook

- Click **Create new** / **Create new notebook**.
- If an add-source dialog appears, leave it open for step 3.

**Done when:** URL contains `/notebook/<uuid>` (and usually `authuser=`).

### 3. Add one source per chapter

Prefer **Upload files** if the upload control works.

If upload/file picker fails (common under automation), use the **API path** — load [`references/apis.md`](references/apis.md) and run **create source → resumable upload → poll ready** from the page with `credentials: 'include'`.

Rules:

- One **source** per chapter file; do not merge chapters.
- Skip 版权 / Digital Lab / 目录 / 序言 unless the user wants them.
- After upload, poll until each source is ready before generating audio.

**Done when:** Studio/Sources lists every intended chapter as ready (not stuck processing).

### 4. Generate one Chinese Audio Overview per chapter

For **each** chapter, isolate that source and generate:

1. Open **Audio Overview** → customize.
2. Language: **中文（简体）** / `zh_hans` / `zh-Hans-CN`.
3. Sources: select **only** this chapter's source (deselect others).
4. Optional focus prompt in Chinese for that chapter.
5. **Generate** (Deep Dive default unless user asks otherwise).

If UI is flaky, use the generate RPC in [`references/apis.md`](references/apis.md) with the single `source_id` and `zh_hans`.

**Do not** fire the same chapter twice. Parallel generate is allowed only when the product accepts concurrent jobs; otherwise wait for the previous **artifact** to leave "Generating".

**Done when:** each chapter has exactly one ready Audio Overview **artifact** (playable; media URLs present in `gArtLc` / Studio).

### 5. Dedupe artifacts

If a chapter has multiple **artifacts** (double-submit), keep one ready title and delete the rest (⋯ → Delete → confirm). Prefer the ready item with the best title; drop pending duplicates first.

**Done when:** artifact count equals chapter count.

### 6. Download audio to disk

Order of attempts:

1. Studio ⋯ → **Download** for each artifact (verify request body targets the intended artifact id).
2. Poll the user's download directories (including Chrome `savefile.default_directory` if set) for a new stable `.m4a`/`.mp4`.
3. Copy into the requested output dir with stable names, e.g. `01_<chapter>.m4a`.

**Hard limits (do not thrash):**

- Signed media URLs (`googleusercontent` / `googlevideo`) often **403** outside the player; curl/page `fetch` is unreliable.
- Synthetic clicks may call download RPC successfully yet **never write a file** (Chrome multi-download / untrusted gesture). After one failed poll cycle, ask the user for a **trusted click** Download on the remaining items, then copy files when they appear.

**Done when:** every chapter has a local audio file of non-trivial size (`file` reports audio/ISO Media), or the user has been asked only for the residual trusted-click items.

## Failure modes

| Symptom | Cause | Move |
| --- | --- | --- |
| Wrong notebooks / PRO missing | Wrong Google account | AccountChooser; keep `authuser` |
| Upload button no-ops | Automation file picker | API path in `references/apis.md` |
| 3 podcasts for 2 chapters | Double generate | Step 5 delete |
| Download RPC ok, no file | Untrusted / multi-download block | Trusted click; then copy |
| curl 403 on media URL | Signed URL / IP / session | Don't curl; use Download or user |

## Optional prep

Chapter split from EPUB without third-party deps: project `scripts/split_epub_chapters.py` (toc.ncx / spine → one file per chapter).
