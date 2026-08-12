# NotebookLM batchexecute + upload (reference)

Load only when implementing the API path or debugging RPCs. Values (`bl`, `f.sid`, `at` / SNlM0e, `authuser`) come from the live page; re-read them each session.

Base:

```text
POST https://notebook.google.com/_/LabsTailwindUi/data/batchexecute
  ?rpcids=<RPC>
  &source-path=/notebook/<NOTEBOOK_ID>
  &bl=<cfb2h from page>
  &f.sid=<FdrFJe from page>
  &hl=en
  &authuser=<n>
  &_reqid=<random>
  &rt=c
Content-Type: application/x-www-form-urlencoded;charset=UTF-8
x-same-domain: 1
body: f.req=<json>&at=<SNlM0e>
```

`f.req` shape: `[[[rpcId, JSON.stringify(innerPayload), null, "generic"]]]`.

Call from page JS with `fetch(..., { credentials: "include" })` so cookies attach.

## Tokens from page

- `at` / CSRF: `"SNlM0e":"..."` in HTML
- `bl`: `"cfb2h":"boq_labs-tailwind-frontend_..."`
- `f.sid`: `"FdrFJe":"..."`
- `NOTEBOOK_ID`: UUID in `/notebook/<uuid>`

## Upload a text source

### 1. Create source — `o4cbdc`

Inner payload (observed):

```json
[[["filename.ext"]], "<NOTEBOOK_ID>", [2, null, [1], [1, null, null, null, null, null, null, null, null, null, [1, 3]]]]
```

Response embeds `SOURCE_ID` (UUID) next to the filename.

### 2. Start resumable upload

```http
POST https://notebook.google.com/upload/_/?authuser=<n>
Content-Type: text/plain;charset=UTF-8

{"PROJECT_ID":"<NOTEBOOK_ID>","SOURCE_NAME":"filename.ext","SOURCE_ID":"<SOURCE_ID>"}
```

Optional Google resumable headers if required by the current frontend:

- `x-goog-upload-command: start`
- `x-goog-upload-protocol: resumable`
- `x-goog-upload-header-content-type: text/plain`
- `x-goog-upload-header-content-length: <bytes>`

Read `x-goog-upload-url` / `Location` for the next step.

### 3. PUT/POST bytes

```http
POST <upload_url>
Content-Type: text/plain;charset=UTF-8
x-goog-upload-command: upload, finalize
x-goog-upload-offset: 0

<body of file>
```

Success body often: `OK: Enqueued blob bytes to spanner queue for processing.`

### 4. Poll source ready — `rLM1Ne`

Inner payload (observed):

```json
["<NOTEBOOK_ID>", null, [2, null, [1], [1, null, null, null, null, null, null, null, null, null, [1, 3]]], null, 1, [[null, null, []]]]
```

Ready sources expose richer metadata (e.g. type/status fields near the source id; media/download links appear when processing finishes). Poll until the new source is usable for generation.

## List artifacts — `gArtLc`

```json
[[2, null, null, [1, null, null, null, null, null, null, null, null, null, [1]], [[1, 4, 8, 10, 2, 3, 6, 9, 11]]], "<NOTEBOOK_ID>", "NOT artifact.status = \"ARTIFACT_STATUS_SUGGESTED\""]
```

Parse the nested wrb.fr JSON string. Each **artifact** is roughly:

`[artifact_id, title, type, [[[source_id], ...]], ...]`

Ready Audio Overviews include `audio/mp4` media URL triples. Generating items lack media.

## Generate Chinese Audio Overview — `R7cb6c`

Observed inner payload (single source, Chinese):

```json
[
  [2, null, null, [1, null, null, null, null, null, null, null, null, null, [1]], [[1, 4, 8, 10, 2, 3, 6, 9, 11]]],
  "<NOTEBOOK_ID>",
  [
    null,
    null,
    1,
    [[[ "<SOURCE_ID>" ]]],
    null,
    null,
    [null, [null, 2, null, [[ "<SOURCE_ID>" ]], "zh_hans", null, 1]]
  ]
]
```

- `1` near format: Deep Dive-style overview (as observed).
- Language string: `zh_hans` or later `zh-Hans-CN` on the artifact.

Poll with `gArtLc` until the new artifact has media URLs. **Never re-POST the same source while a generating artifact for it already exists.**

## Delete artifact — `V5N4be`

Observed:

```json
[[2, null, null, [1, null, null, null, null, null, null, null, null, null, [1]], [[1, 4, 8, 10, 2, 3, 6, 9, 11]]], "<ARTIFACT_ID>"]
```

(Some calls wrap the id slightly differently; match a live UI delete if the shape drifts.)

## Download artifact — `HpN0Ub`

Observed:

```json
[[2, null, [1], [1, null, null, null, null, null, null, null, null, null, [1, 3]], [[1, 4, 8, 10, 2, 3, 6, 9, 11]]], null, ["<ARTIFACT_ID>"]]
```

Response is often an empty list; the browser still owns writing the file. Confirm the id in the POST body before assuming the correct podcast was requested. Signed `googleusercontent` / `googlevideo` URLs from `gArtLc` are **not** a reliable curl fallback (403 / IP binding).

## Capture tips

- Start webbridge `network` capture before a manual upload once; use CDP `Network.getRequestPostData` for request bodies (list `detail` is often response-only).
- Prefer page-origin `fetch` over shell curl for authenticated RPCs.
- RPC ids and payload shapes can change with frontend builds (`bl` string bumps). Re-sniff when calls start failing.
