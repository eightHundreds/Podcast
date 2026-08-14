/**
 * Podcast show page player - depends on PodcastPlayerCore + embedded JSON.
 * Supports optional time-synced captions (live line + auto-scrolling cue list).
 */
(function (global) {
  "use strict";

  var Core = global.PodcastPlayerCore;
  if (!Core) {
    console.error("PodcastPlayerCore missing - load player-core.js first");
    return;
  }

  var SYNC_KEY = "podcast:caption-sync";

  function $(id) {
    return document.getElementById(id);
  }

  function loadProgress(showId, epId) {
    try {
      var raw = localStorage.getItem(Core.progressKey(showId, epId));
      if (raw == null) return null;
      var n = parseFloat(raw);
      return isNaN(n) ? null : n;
    } catch (e) {
      return null;
    }
  }

  function saveProgress(showId, epId, t) {
    try {
      localStorage.setItem(Core.progressKey(showId, epId), String(t));
    } catch (e) {}
  }

  function clearProgress(showId, epId) {
    try {
      localStorage.removeItem(Core.progressKey(showId, epId));
    } catch (e) {}
  }

  function loadSyncPref() {
    try {
      return localStorage.getItem(SYNC_KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function saveSyncPref(on) {
    try {
      localStorage.setItem(SYNC_KEY, on ? "1" : "0");
    } catch (e) {}
  }

  function hasCacheStorage() {
    return typeof caches !== "undefined" && !!caches && typeof caches.open === "function";
  }

  function openAudioCache() {
    return caches.open(Core.AUDIO_CACHE_NAME);
  }

  function matchFreshCachedAudio(url) {
    if (!hasCacheStorage() || !url) return Promise.resolve(null);
    return openAudioCache()
      .then(function (cache) {
        return cache.match(url).then(function (res) {
          if (!res) return null;
          var cachedAt = Core.cachedAtFromHeaders(res.headers);
          if (!Core.isAudioCacheFresh(cachedAt)) {
            return cache.delete(url).then(function () {
              return null;
            });
          }
          return res;
        });
      })
      .catch(function () {
        return null;
      });
  }

  function pruneExpiredAudioCache(cache) {
    return cache
      .keys()
      .then(function (reqs) {
        return Promise.all(
          reqs.map(function (req) {
            return cache.match(req).then(function (res) {
              if (!res) return;
              if (!Core.isAudioCacheFresh(Core.cachedAtFromHeaders(res.headers))) {
                return cache.delete(req);
              }
            });
          })
        );
      })
      .catch(function () {});
  }

  function stampAudioResponse(res, cachedAt) {
    return res.arrayBuffer().then(function (buf) {
      var headers = new Headers();
      if (res.headers && typeof res.headers.forEach === "function") {
        res.headers.forEach(function (value, key) {
          headers.set(key, value);
        });
      }
      headers.delete("content-encoding");
      headers.set("Content-Type", (res.headers && res.headers.get("Content-Type")) || "audio/mp4");
      headers.set("Content-Length", String(buf.byteLength));
      headers.set(Core.AUDIO_CACHE_META_HEADER, String(cachedAt));
      return new Response(buf, { status: 200, statusText: "OK", headers: headers });
    });
  }

  var audioCacheInflight = Object.create(null);

  function populateAudioCache(url) {
    if (!hasCacheStorage() || !url) return Promise.resolve(false);
    if (audioCacheInflight[url]) return audioCacheInflight[url];
    audioCacheInflight[url] = matchFreshCachedAudio(url)
      .then(function (hit) {
        if (hit) return true;
        return fetch(url, {
          mode: "cors",
          credentials: "omit",
          cache: "force-cache",
        }).then(function (res) {
          if (!res.ok) return false;
          return stampAudioResponse(res, Date.now()).then(function (stored) {
            return openAudioCache().then(function (cache) {
              return cache
                .put(url, stored)
                .catch(function () {
                  return pruneExpiredAudioCache(cache).then(function () {
                    return cache.put(url, stored);
                  });
                })
                .then(function () {
                  return pruneExpiredAudioCache(cache);
                })
                .then(function () {
                  return true;
                });
            });
          });
        });
      })
      .catch(function () {
        return false;
      })
      .then(function (ok) {
        delete audioCacheInflight[url];
        return !!ok;
      });
    return audioCacheInflight[url];
  }

  function resolveCachedAudioBlobUrl(url) {
    if (!url) return Promise.resolve(null);
    return matchFreshCachedAudio(url)
      .then(function (res) {
        if (!res) return null;
        return res.blob().then(function (blob) {
          return URL.createObjectURL(blob);
        });
      })
      .catch(function () {
        return null;
      });
  }

  function mount(dataEl) {
    var data;
    try {
      data = JSON.parse(dataEl.textContent);
    } catch (e) {
      console.error("Invalid show-data JSON", e);
      return;
    }
    var show = data.show || {};
    var episodes = data.episodes || [];
    var showId = show.id || "show";

    var audio = $("audio");
    var btnPlay = $("btn-play");
    var btnBack = $("btn-back15");
    var btnFwd = $("btn-fwd30");
    var seek = $("seek");
    var timeCur = $("time-cur");
    var timeDur = $("time-dur");
    var rateSel = $("rate");
    var list = $("episode-list");
    var npTitle = $("np-title");
    var npEp = $("np-ep");
    var npDesc = $("np-desc");
    var npMeta = $("np-meta");
    var npCover = $("np-cover");
    var cueList = $("cue-list");
    var transcriptPanel = $("transcript-panel");
    var btnTranscript = $("btn-transcript");
    var liveCaption = $("live-caption");
    var liveSpeaker = $("live-caption-speaker");
    var liveText = $("live-caption-text");
    var captionStatus = $("caption-status");
    var btnCopyTranscript = $("btn-copy-transcript");

    var current = null;
    var cues = [];
    var seeking = false;
    var lastSave = 0;
    var lastCueIndex = -1;
    var syncOn = loadSyncPref();
    var userScrollingTranscript = false;
    var scrollUnlockTimer = null;
    var loadGen = 0;
    var sourceTokenReady = 0;
    var playWhenReady = false;
    var audioObjectUrl = null;

    function revokeAudioObjectUrl() {
      if (!audioObjectUrl) return;
      try {
        URL.revokeObjectURL(audioObjectUrl);
      } catch (e) {}
      audioObjectUrl = null;
    }

    function ensurePlayIcons() {
      if (!btnPlay || btnPlay.querySelector(".icon-stack")) return;
      btnPlay.innerHTML =
        '<span class="icon-stack" aria-hidden="true">' +
        '<span class="icon-layer icon-play is-visible">' +
        '<svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22">' +
        '<path d="M8 5.14v13.72a1 1 0 0 0 1.54.84l10.12-6.86a1 1 0 0 0 0-1.68L9.54 4.3A1 1 0 0 0 8 5.14z"/>' +
        "</svg></span>" +
        '<span class="icon-layer icon-pause is-hidden">' +
        '<svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22">' +
        '<rect x="6" y="5" width="4" height="14" rx="1"/>' +
        '<rect x="14" y="5" width="4" height="14" rx="1"/>' +
        "</svg></span></span>";
    }

    ensurePlayIcons();

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function truncate(s, n) {
      s = String(s).replace(/\s+/g, " ").trim();
      return s.length > n ? s.slice(0, n) + "…" : s;
    }

    function formatPubDate(iso) {
      if (!iso) return "";
      try {
        var d = new Date(iso);
        if (isNaN(d.getTime())) return String(iso).slice(0, 10);
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, "0");
        var day = String(d.getDate()).padStart(2, "0");
        return y + "." + m + "." + day;
      } catch (e) {
        return String(iso).slice(0, 10);
      }
    }

    function episodeMetaLine(ep) {
      var parts = [];
      if (ep.episode != null) parts.push("第 " + ep.episode + " 集");
      var date = formatPubDate(ep.publicationDate);
      if (date) parts.push(date);
      if (ep.duration) parts.push(ep.duration);
      else if (ep.durationSec) parts.push(Core.formatTime(ep.durationSec));
      return parts.join(" · ");
    }

    function setCaptionStatus(msg) {
      if (captionStatus) captionStatus.textContent = msg || "";
    }

    function updateCopyButton() {
      if (!btnCopyTranscript) return;
      btnCopyTranscript.disabled = !cues.length;
      btnCopyTranscript.setAttribute(
        "aria-disabled",
        cues.length ? "false" : "true"
      );
    }

    function buildFullTranscriptText() {
      var title = current
        ? current.title || (show.title ? show.title + " · 分集" : "字幕")
        : show.title || "字幕";
      if (Core.formatFullTranscript) {
        return Core.formatFullTranscript(cues, {
          includeTimestamps: true,
          includeSpeakers: true,
          title: title,
        });
      }
      // Fallback if core not updated
      var lines = [title, ""];
      cues.forEach(function (c) {
        lines.push(
          "[" +
            Core.formatTime(c.start) +
            "] " +
            (Core.formatCueLine ? Core.formatCueLine(c) : c.text || "")
        );
      });
      return lines.join("\n");
    }

    function copyTextToClipboard(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
      }
      return new Promise(function (resolve, reject) {
        try {
          var ta = document.createElement("textarea");
          ta.value = text;
          ta.setAttribute("readonly", "");
          ta.style.position = "fixed";
          ta.style.left = "-9999px";
          document.body.appendChild(ta);
          ta.select();
          var ok = document.execCommand("copy");
          document.body.removeChild(ta);
          if (ok) resolve();
          else reject(new Error("execCommand copy failed"));
        } catch (e) {
          reject(e);
        }
      });
    }

    function flashCopyButton(label) {
      if (!btnCopyTranscript) return;
      var old = btnCopyTranscript.textContent;
      btnCopyTranscript.textContent = label;
      setTimeout(function () {
        btnCopyTranscript.textContent = old;
      }, 1400);
    }

    function copyFullTranscript() {
      if (!cues.length) {
        flashCopyButton("无字幕");
        return;
      }
      var text = buildFullTranscriptText();
      copyTextToClipboard(text)
        .then(function () {
          flashCopyButton("已复制");
          setCaptionStatus("字幕 · " + cues.length + " 条 · 已复制");
          setTimeout(function () {
            if (cues.length) setCaptionStatus("字幕 · " + cues.length + " 条");
          }, 1600);
        })
        .catch(function () {
          // Last resort: select-friendly prompt
          window.prompt("复制失败，请手动全选复制：", text);
          flashCopyButton("请手动复制");
        });
    }

    function applySyncUi() {
      if (btnTranscript) {
        btnTranscript.setAttribute("aria-pressed", syncOn ? "true" : "false");
        btnTranscript.textContent = syncOn ? "字幕 · 开" : "字幕";
        btnTranscript.title = syncOn
          ? "关闭同步字幕"
          : "开启同步字幕";
      }
      // 开关同时控制上方实时字幕与下方全文列表
      if (liveCaption) {
        if (syncOn) liveCaption.removeAttribute("hidden");
        else liveCaption.setAttribute("hidden", "");
      }
      if (transcriptPanel) {
        if (syncOn) transcriptPanel.removeAttribute("hidden");
        else transcriptPanel.setAttribute("hidden", "");
      }
      document.body.classList.toggle("captions-sync-on", !!syncOn);
      if (syncOn) {
        syncCaptionToTime(audio.currentTime || 0, true);
      } else {
        clearLiveCaption();
      }
    }

    function setSync(on) {
      syncOn = !!on;
      saveSyncPref(syncOn);
      applySyncUi();
    }

    function renderList() {
      list.innerHTML = "";
      episodes.forEach(function (ep, idx) {
        var li = document.createElement("li");
        li.className = "ep-item";
        li.dataset.index = String(idx);
        li.tabIndex = 0;
        li.setAttribute("role", "button");
        var num = ep.episode != null ? "EP " + String(ep.episode).padStart(2, "0") : "分集";
        var date = formatPubDate(ep.publicationDate);
        var dur = ep.duration || (ep.durationSec ? Core.formatTime(ep.durationSec) : "");
        li.innerHTML =
          (ep.image
            ? '<img class="ep-thumb" src="' +
              ep.image +
              '" alt="" width="56" height="56" loading="lazy" />'
            : '<div class="ep-thumb placeholder" aria-hidden="true"></div>') +
          '<div class="ep-body">' +
          '<p class="ep-num">' +
          escapeHtml(num) +
          (date ? " · " + escapeHtml(date) : "") +
          "</p>" +
          "<h3>" +
          escapeHtml(ep.title) +
          "</h3>" +
          '<p class="ep-desc">' +
          escapeHtml(truncate(ep.description || "", 110)) +
          "</p>" +
          "</div>" +
          (dur
            ? '<div class="ep-side"><span>' + escapeHtml(dur) + "</span></div>"
            : "");
        li.addEventListener("click", function () {
          selectEpisode(idx, true);
        });
        li.addEventListener("keydown", function (ev) {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            selectEpisode(idx, true);
          }
        });
        list.appendChild(li);
      });
    }

    function highlightList() {
      var items = list.querySelectorAll(".ep-item");
      items.forEach(function (el) {
        var i = parseInt(el.dataset.index, 10);
        el.classList.toggle("active", current && episodes[i] === current);
      });
    }

    function attachCaptionTrack(ep) {
      while (audio.firstChild) audio.removeChild(audio.firstChild);
      if (!ep.transcriptUrl) return;
      var track = document.createElement("track");
      track.kind = "captions";
      track.label = "中文";
      track.srclang = "zh";
      track.src = ep.transcriptUrl;
      track.default = !!syncOn;
      audio.appendChild(track);
    }

    function bindResumeAndAutoplay(autoplay, saved) {
      var onMeta = function () {
        audio.removeEventListener("loadedmetadata", onMeta);
        var dur = audio.duration;
        if (saved != null && dur && saved < dur - 5 && saved > 2) {
          audio.currentTime = Core.clampSeek(saved, dur);
        }
        updateTimeUi();
        if (autoplay) {
          audio.play().catch(function () {});
        }
      };
      if (audio.readyState >= 1) onMeta();
      else audio.addEventListener("loadedmetadata", onMeta);
    }

    function applyAudioSource(src, ep, token, autoplay, saved) {
      if (token !== loadGen) return;
      audio.src = src || "";
      attachCaptionTrack(ep);
      audio.load();
      sourceTokenReady = token;
      bindResumeAndAutoplay(autoplay || playWhenReady, saved);
      playWhenReady = false;
    }

    function localTranscriptFallback(url) {
      // Map Pages absolute URL to relative path for local static server.
      // e.g. .../Podcast/transcripts/ep01.vtt -> ../transcripts/ep01.vtt
      try {
        var u = new URL(url, location.href);
        var m = u.pathname.match(/\/transcripts\/([^/]+\.vtt)$/i);
        if (m) return "../transcripts/" + m[1];
      } catch (e) {}
      return null;
    }

    function fetchText(url) {
      return fetch(url).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      });
    }

    function selectEpisode(index, autoplay) {
      var ep = episodes[index];
      if (!ep) return;
      if (current && audio && !isNaN(audio.currentTime)) {
        saveProgress(showId, current.id, audio.currentTime);
      }
      current = ep;
      lastCueIndex = -1;
      npTitle.textContent = ep.title;
      if (npEp) {
        npEp.textContent =
          ep.episode != null ? "第 " + ep.episode + " 集" : "分集";
      }
      if (npMeta) npMeta.textContent = episodeMetaLine(ep);
      if (npDesc) npDesc.textContent = (ep.description || "").trim();
      if (npCover) {
        if (ep.image) {
          npCover.src = ep.image;
          npCover.hidden = false;
        } else if (show.image) {
          npCover.src = show.image;
          npCover.hidden = false;
        } else {
          npCover.removeAttribute("src");
          npCover.hidden = true;
        }
      }
      // Update document title like a blog post
      try {
        document.title = ep.title + " · " + (show.title || "播客");
      } catch (e) {}
      highlightList();
      cues = [];
      cueList.innerHTML = "";
      clearLiveCaption();
      updateCopyButton();
      if (ep.transcriptUrl) {
        setCaptionStatus("字幕加载中…");
        loadTranscript(ep.transcriptUrl);
      } else {
        setCaptionStatus("本集暂无字幕");
        if (syncOn) {
          setLiveCaption("", "暂无字幕");
        }
      }
      var saved = loadProgress(showId, ep.id);
      var token = ++loadGen;
      var remote = ep.audioUrl || "";
      revokeAudioObjectUrl();
      resolveCachedAudioBlobUrl(remote).then(function (blobUrl) {
        if (token !== loadGen) {
          if (blobUrl) {
            try {
              URL.revokeObjectURL(blobUrl);
            } catch (e) {}
          }
          return;
        }
        if (blobUrl) audioObjectUrl = blobUrl;
        applyAudioSource(blobUrl || remote, ep, token, autoplay, saved);
      });
      updatePlayBtn();
    }

    function loadTranscript(url) {
      var triedLocal = false;
      function ok(text) {
        if (!current || current.transcriptUrl !== url) return;
        cues = Core.parseVtt(text);
        renderCues();
        updateCopyButton();
        setCaptionStatus(
          cues.length ? "字幕 · " + cues.length + " 条" : "暂无字幕"
        );
        syncCaptionToTime(audio.currentTime || 0, true);
      }
      function fail() {
        if (!triedLocal) {
          var local = localTranscriptFallback(url);
          if (local) {
            triedLocal = true;
            fetchText(local).then(ok).catch(function () {
              setCaptionStatus("字幕加载失败");
              console.warn("字幕加载失败", url);
            });
            return;
          }
        }
        setCaptionStatus("字幕加载失败");
        console.warn("字幕加载失败", url);
      }
      fetchText(url).then(ok).catch(fail);
    }

    function renderCues() {
      cueList.innerHTML = "";
      cues.forEach(function (cue, i) {
        var li = document.createElement("li");
        li.className = "cue-item";
        li.dataset.index = String(i);
        li.setAttribute("role", "button");
        li.tabIndex = 0;
        var speakerHtml = cue.speaker
          ? '<span class="cue-speaker">' + escapeHtml(cue.speaker) + "</span>"
          : "";
        li.innerHTML =
          '<span class="cue-time">' +
          Core.formatTime(cue.start) +
          "</span>" +
          '<span class="cue-body">' +
          speakerHtml +
          '<span class="cue-text">' +
          escapeHtml(cue.text || cue.raw || "") +
          "</span></span>";
        function jump() {
          var t = Core.cueSeekTarget(cue);
          var dur = audio.duration || (current && current.durationSec) || 0;
          audio.currentTime = Core.clampSeek(t, dur);
          if (audio.paused) audio.play().catch(function () {});
          updateTimeUi();
        }
        li.addEventListener("click", jump);
        li.addEventListener("keydown", function (ev) {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            jump();
          }
        });
        cueList.appendChild(li);
      });
    }

    function clearLiveCaption() {
      if (liveSpeaker) liveSpeaker.textContent = "";
      if (liveText) liveText.textContent = syncOn ? "…" : "";
      if (liveCaption) liveCaption.classList.remove("has-cue");
    }

    function setLiveCaption(speaker, text) {
      if (!liveCaption) return;
      if (liveSpeaker) {
        liveSpeaker.textContent = speaker || "";
        liveSpeaker.hidden = !speaker;
      }
      if (liveText) liveText.textContent = text || "";
      liveCaption.classList.toggle("has-cue", !!(text && text.trim()));
    }

    function scrollActiveCue(idx) {
      if (!syncOn || userScrollingTranscript || idx < 0) return;
      var el = cueList && cueList.querySelector('.cue-item[data-index="' + idx + '"]');
      if (!el) return;
      var scroller =
        (transcriptPanel && transcriptPanel.querySelector(".transcript-scroll")) ||
        transcriptPanel;
      if (!scroller || (transcriptPanel && transcriptPanel.hasAttribute("hidden"))) return;

      // offsetTop is relative to offsetParent, not the scroll container — use rects.
      var elRect = el.getBoundingClientRect();
      var box = scroller.getBoundingClientRect();
      var elTopInScroll = elRect.top - box.top + scroller.scrollTop;
      var elH = elRect.height;
      var viewH = scroller.clientHeight;
      var maxScroll = Math.max(0, scroller.scrollHeight - viewH);
      var target = elTopInScroll - viewH * 0.35 + elH / 2;
      if (target < 0) target = 0;
      if (target > maxScroll) target = maxScroll;

      // Skip tiny adjustments to avoid jitter
      if (Math.abs(scroller.scrollTop - target) < 8) return;

      scroller.scrollTo({
        top: target,
        behavior: "smooth",
      });
    }

    function syncCaptionToTime(cur, force) {
      var idx = Core.cueIndexAt ? Core.cueIndexAt(cues, cur) : -1;
      if (!force && idx === lastCueIndex) {
        // still update live text only when entering/leaving empty gaps
        if (idx < 0 && syncOn) {
          /* keep last line or clear? clear mid-gap after short silence */
        }
        return;
      }
      lastCueIndex = idx;

      var items = cueList ? cueList.querySelectorAll(".cue-item") : [];
      items.forEach(function (el, i) {
        el.classList.toggle("active", i === idx);
      });

      if (!syncOn) {
        if (liveCaption && !liveCaption.hasAttribute("hidden")) {
          /* sync off: leave panel highlight only if open */
        }
        return;
      }

      if (idx >= 0 && cues[idx]) {
        var cue = cues[idx];
        setLiveCaption(cue.speaker || "", cue.text || cue.raw || "");
        scrollActiveCue(idx);
      } else {
        // Between cues: keep previous text dimmed, or show placeholder
        if (liveCaption) liveCaption.classList.remove("has-cue");
        if (liveText && !liveText.textContent) liveText.textContent = "…";
      }
    }

    function updatePlayBtn() {
      if (!btnPlay) return;
      ensurePlayIcons();
      var playing = !audio.paused;
      var playLayer = btnPlay.querySelector(".icon-play");
      var pauseLayer = btnPlay.querySelector(".icon-pause");
      if (playLayer && pauseLayer) {
        playLayer.classList.toggle("is-visible", !playing);
        playLayer.classList.toggle("is-hidden", playing);
        pauseLayer.classList.toggle("is-visible", playing);
        pauseLayer.classList.toggle("is-hidden", !playing);
      }
      btnPlay.setAttribute("aria-label", playing ? "暂停" : "播放");
      btnPlay.setAttribute("data-playing", playing ? "true" : "false");
    }

    function updateTimeUi() {
      var dur = audio.duration;
      if (!dur || isNaN(dur)) {
        dur = (current && current.durationSec) || 0;
      }
      var cur = audio.currentTime || 0;
      timeCur.textContent = Core.formatTime(cur);
      timeDur.textContent = Core.formatTime(dur);
      if (!seeking && dur > 0) {
        seek.value = String(Math.round((cur / dur) * 1000));
      }
      syncCaptionToTime(cur, false);
    }

    btnPlay.addEventListener("click", function () {
      if (!current) {
        if (episodes.length) selectEpisode(0, true);
        return;
      }
      if (sourceTokenReady !== loadGen) {
        playWhenReady = audio.paused;
        return;
      }
      if (audio.paused) audio.play().catch(function () {});
      else audio.pause();
    });
    btnBack.addEventListener("click", function () {
      var dur = audio.duration || 0;
      audio.currentTime = Core.clampSeek((audio.currentTime || 0) - 15, dur);
      updateTimeUi();
    });
    btnFwd.addEventListener("click", function () {
      var dur = audio.duration || 0;
      audio.currentTime = Core.clampSeek((audio.currentTime || 0) + 30, dur);
      updateTimeUi();
    });
    rateSel.addEventListener("change", function () {
      audio.playbackRate = Core.setPlaybackRate(parseFloat(rateSel.value));
      try {
        localStorage.setItem("podcast:rate", rateSel.value);
      } catch (e) {}
    });
    seek.addEventListener("pointerdown", function () {
      seeking = true;
    });
    seek.addEventListener("pointerup", function () {
      seeking = false;
      applySeek();
    });
    seek.addEventListener("change", applySeek);
    seek.addEventListener("input", function () {
      if (!seeking) return;
      var dur = audio.duration || (current && current.durationSec) || 0;
      var t = (parseInt(seek.value, 10) / 1000) * dur;
      timeCur.textContent = Core.formatTime(t);
      // Preview caption while scrubbing
      syncCaptionToTime(t, true);
    });
    function applySeek() {
      var dur = audio.duration || (current && current.durationSec) || 0;
      var t = (parseInt(seek.value, 10) / 1000) * dur;
      audio.currentTime = Core.clampSeek(t, dur);
      updateTimeUi();
    }

    audio.addEventListener("play", function () {
      updatePlayBtn();
      if (current && current.audioUrl) populateAudioCache(current.audioUrl);
    });
    audio.addEventListener("pause", updatePlayBtn);
    audio.addEventListener("timeupdate", function () {
      updateTimeUi();
      if (current) {
        var now = Date.now();
        if (now - lastSave > 2000) {
          lastSave = now;
          saveProgress(showId, current.id, audio.currentTime || 0);
        }
      }
    });
    audio.addEventListener("seeked", function () {
      syncCaptionToTime(audio.currentTime || 0, true);
    });
    audio.addEventListener("ended", function () {
      if (current) clearProgress(showId, current.id);
      var idx = episodes.indexOf(current);
      if (idx >= 0 && idx < episodes.length - 1) {
        selectEpisode(idx + 1, true);
      } else {
        updatePlayBtn();
      }
    });
    audio.addEventListener("loadedmetadata", updateTimeUi);

    // Toggle: sync captions on/off
    btnTranscript.addEventListener("click", function () {
      setSync(!syncOn);
    });

    if (btnCopyTranscript) {
      btnCopyTranscript.addEventListener("click", function () {
        copyFullTranscript();
      });
    }

    // Pause auto-scroll while user manually scrolls cue list
    var transcriptScroll =
      (transcriptPanel && transcriptPanel.querySelector(".transcript-scroll")) ||
      transcriptPanel;
    if (transcriptScroll) {
      function markUserScroll() {
        userScrollingTranscript = true;
        if (scrollUnlockTimer) clearTimeout(scrollUnlockTimer);
        scrollUnlockTimer = setTimeout(function () {
          userScrollingTranscript = false;
        }, 2500);
      }
      transcriptScroll.addEventListener("wheel", markUserScroll, { passive: true });
      transcriptScroll.addEventListener("touchmove", markUserScroll, { passive: true });
    }

    // Persist rate
    try {
      var savedRate = localStorage.getItem("podcast:rate");
      if (savedRate) {
        var r = Core.setPlaybackRate(parseFloat(savedRate));
        rateSel.value = String(r);
        audio.playbackRate = r;
      }
    } catch (e) {}

    applySyncUi();
    renderList();
    if (hasCacheStorage()) {
      openAudioCache().then(pruneExpiredAudioCache).catch(function () {});
    }
    if (episodes.length) {
      selectEpisode(0, false);
    }

    try {
      var params = new URLSearchParams(location.search);
      var epParam = params.get("ep");
      if (epParam) {
        var n = parseInt(epParam, 10);
        var found = episodes.findIndex(function (e) {
          return String(e.episode) === String(n) || String(e.id) === String(epParam);
        });
        if (found >= 0) selectEpisode(found, false);
      }
      if (params.get("captions") === "1" || params.get("sync") === "1") {
        setSync(true);
      }
    } catch (e) {}
  }

  global.PodcastPlayer = { mount: mount };
})(typeof globalThis !== "undefined" ? globalThis : this);
