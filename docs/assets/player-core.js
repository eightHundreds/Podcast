/**
 * Pure player helpers (no DOM). Loaded in browser and Node tests.
 * Keep semantics aligned with scripts/podcast_core/player_logic.py.
 */
(function (global) {
  "use strict";

  var ALLOWED_RATES = [0.75, 1, 1.25, 1.5, 1.75, 2];

  function parseDuration(value) {
    if (value == null || value === "") return 0;
    if (typeof value === "number") return Math.max(0, value);
    var s = String(value).trim();
    if (/^\d+(\.\d+)?$/.test(s)) return Math.max(0, parseFloat(s));
    var parts = s.split(":");
    if (!parts.every(function (p) { return /^\d+(\.\d+)?$/.test(p); })) {
      throw new Error("invalid duration: " + value);
    }
    var nums = parts.map(parseFloat);
    if (nums.length === 3) return nums[0] * 3600 + nums[1] * 60 + nums[2];
    if (nums.length === 2) return nums[0] * 60 + nums[1];
    if (nums.length === 1) return nums[0];
    throw new Error("invalid duration: " + value);
  }

  function formatTime(seconds) {
    if (seconds == null || isNaN(seconds)) seconds = 0;
    var total = Math.floor(Math.max(0, Number(seconds)));
    var h = Math.floor(total / 3600);
    var m = Math.floor((total % 3600) / 60);
    var s = total % 60;
    if (h > 0) {
      return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    }
    return m + ":" + String(s).padStart(2, "0");
  }

  function clampSeek(position, duration) {
    if (duration == null || isNaN(duration) || duration <= 0) return 0;
    if (position == null || isNaN(position)) return 0;
    if (position < 0) return 0;
    if (position > duration) return Number(duration);
    return Number(position);
  }

  function setPlaybackRate(rate, allowed) {
    allowed = allowed || ALLOWED_RATES;
    if (rate == null || isNaN(rate)) return 1;
    var best = allowed[0];
    var bestDist = Math.abs(allowed[0] - rate);
    for (var i = 1; i < allowed.length; i++) {
      var d = Math.abs(allowed[i] - rate);
      if (d < bestDist) {
        best = allowed[i];
        bestDist = d;
      }
    }
    return best;
  }

  function progressKey(showId, episodeId) {
    return "podcast:progress:" + showId + ":" + episodeId;
  }

  // Cache Storage holds the audio blob; TTL metadata lives on the Response.
  var AUDIO_CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  var AUDIO_CACHE_NAME = "podcast-audio-v1";
  var AUDIO_CACHE_META_HEADER = "X-Podcast-Cached-At";

  function isAudioCacheFresh(cachedAt, now, ttlMs) {
    if (cachedAt == null || cachedAt === "") return false;
    var t = Number(cachedAt);
    var n = now == null ? Date.now() : Number(now);
    var ttl = ttlMs == null ? AUDIO_CACHE_TTL_MS : Number(ttlMs);
    if (!isFinite(t) || !isFinite(n) || !isFinite(ttl) || ttl < 0) return false;
    var age = n - t;
    return age >= 0 && age <= ttl;
  }

  function cachedAtFromHeaders(headers) {
    if (!headers || typeof headers.get !== "function") return null;
    var raw = headers.get(AUDIO_CACHE_META_HEADER);
    if (raw == null || raw === "") return null;
    var n = Number(raw);
    return isFinite(n) ? n : null;
  }

  function audioCacheDecision(cachedAt, now, ttlMs) {
    if (cachedAt == null || cachedAt === "") return "miss";
    return isAudioCacheFresh(cachedAt, now, ttlMs) ? "fresh" : "expired";
  }

  function expiredAudioCacheUrls(entries, now, ttlMs) {
    var out = [];
    if (!entries || !entries.length) return out;
    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      if (!entry || !entry.url) continue;
      if (audioCacheDecision(entry.cachedAt, now, ttlMs) !== "fresh") {
        out.push(entry.url);
      }
    }
    return out;
  }

  function parseTs(ts) {
    ts = String(ts).trim();
    var m = ts.match(/^(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$/);
    if (m) {
      var ms = (m[4] || "0").padEnd(3, "0").slice(0, 3);
      return (
        parseInt(m[1], 10) * 3600 +
        parseInt(m[2], 10) * 60 +
        parseInt(m[3], 10) +
        parseInt(ms, 10) / 1000
      );
    }
    m = ts.match(/^(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?$/);
    if (m) {
      var ms2 = (m[3] || "0").padEnd(3, "0").slice(0, 3);
      return parseInt(m[1], 10) * 60 + parseInt(m[2], 10) + parseInt(ms2, 10) / 1000;
    }
    throw new Error("bad VTT timestamp: " + ts);
  }

  function parseVtt(text) {
    if (!text || !String(text).trim()) return [];
    var raw = String(text).replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    var blocks = raw.trim().split(/\n\n+/);
    var cues = [];
    for (var b = 0; b < blocks.length; b++) {
      var block = blocks[b].trim();
      if (!block) continue;
      var upper = block.toUpperCase();
      if (upper.indexOf("WEBVTT") === 0 || upper.indexOf("NOTE") === 0 || upper.indexOf("STYLE") === 0) {
        continue;
      }
      var lines = block.split("\n");
      var headIdx = 0;
      if (lines[0].indexOf("-->") === -1 && lines.length > 1 && lines[1].indexOf("-->") !== -1) {
        headIdx = 1;
      }
      if (lines[headIdx].indexOf("-->") === -1) continue;
      var head = lines[headIdx];
      var parts = head.split(/\s*-->\s*/);
      if (parts.length < 2) continue;
      var startS = parts[0].trim();
      var endS = parts[1].trim().split(/\s+/)[0];
      var start, end;
      try {
        start = parseTs(startS);
        end = parseTs(endS);
      } catch (e) {
        continue;
      }
      var cueText = lines.slice(headIdx + 1).join("\n").trim();
      if (cueText) cues.push(normalizeCue(start, end, cueText));
    }
    cues.sort(function (a, c) { return a.start - c.start; });
    return cues;
  }

  function normalizeCue(start, end, rawText) {
    var parsed = splitSpeaker(rawText);
    return {
      start: start,
      end: end,
      text: parsed.text,
      speaker: parsed.speaker,
      raw: rawText,
    };
  }

  /** Parse leading "[S01] " / "S01: " speaker tags used by diarization exports. */
  function splitSpeaker(raw) {
    var s = String(raw || "").trim();
    var m = s.match(/^\[([^\]]+)\]\s*([\s\S]*)$/);
    if (m) return { speaker: m[1].trim(), text: (m[2] || "").trim() };
    m = s.match(/^(S\d+)\s*[:：]\s*([\s\S]*)$/);
    if (m) return { speaker: m[1].trim(), text: (m[2] || "").trim() };
    return { speaker: "", text: s };
  }

  function cueAt(cues, t) {
    var idx = cueIndexAt(cues, t);
    return idx < 0 ? null : cues[idx];
  }

  /** Index of active cue at time t, or -1. Binary search on start times. */
  function cueIndexAt(cues, t) {
    if (!cues || !cues.length) return -1;
    t = Number(t);
    if (isNaN(t)) return -1;
    var lo = 0;
    var hi = cues.length - 1;
    var ans = -1;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (cues[mid].start <= t) {
        ans = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (ans < 0) return -1;
    var c = cues[ans];
    if (c.start <= t && t < c.end) return ans;
    return -1;
  }

  function cueSeekTarget(cue) {
    return Number(cue.start);
  }

  function formatCueLine(cue) {
    if (!cue) return "";
    if (cue.speaker) return cue.speaker + ": " + (cue.text || "");
    return cue.text || cue.raw || "";
  }

  /**
   * Full transcript plain text for copy/export.
   * @param {Array} cues
   * @param {{includeTimestamps?: boolean, includeSpeakers?: boolean, title?: string}} opts
   */
  function formatFullTranscript(cues, opts) {
    opts = opts || {};
    var includeTs = opts.includeTimestamps !== false;
    var includeSp = opts.includeSpeakers !== false;
    var lines = [];
    if (opts.title) lines.push(String(opts.title), "");
    if (!cues || !cues.length) return lines.join("\n").trim();
    for (var i = 0; i < cues.length; i++) {
      var c = cues[i];
      var body = includeSp ? formatCueLine(c) : c.text || c.raw || "";
      if (includeTs) {
        lines.push("[" + formatTime(c.start) + "] " + body);
      } else {
        lines.push(body);
      }
    }
    return lines.join("\n");
  }

  var api = {
    ALLOWED_RATES: ALLOWED_RATES,
    parseDuration: parseDuration,
    formatTime: formatTime,
    clampSeek: clampSeek,
    setPlaybackRate: setPlaybackRate,
    progressKey: progressKey,
    parseVtt: parseVtt,
    splitSpeaker: splitSpeaker,
    cueAt: cueAt,
    cueIndexAt: cueIndexAt,
    cueSeekTarget: cueSeekTarget,
    formatCueLine: formatCueLine,
    formatFullTranscript: formatFullTranscript,
    AUDIO_CACHE_TTL_MS: AUDIO_CACHE_TTL_MS,
    AUDIO_CACHE_NAME: AUDIO_CACHE_NAME,
    AUDIO_CACHE_META_HEADER: AUDIO_CACHE_META_HEADER,
    isAudioCacheFresh: isAudioCacheFresh,
    cachedAtFromHeaders: cachedAtFromHeaders,
    audioCacheDecision: audioCacheDecision,
    expiredAudioCacheUrls: expiredAudioCacheUrls,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  global.PodcastPlayerCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
