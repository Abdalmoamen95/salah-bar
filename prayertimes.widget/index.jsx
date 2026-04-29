// =============================================================================
// Prayer Times Widget for Übersicht
// Multi-city switchable: İzmir / Doha / Cairo
// Method: Diyanet (Turkey) — method=13, Shafi'i (school=0)
// API: https://aladhan.com (no key required)
// =============================================================================

// -------- CONFIG -------------------------------------------------------------
const DEFAULT_CONFIG = {
  default_city: "izmir",
  method: 13,
  school: 0,
  cities: {
    izmir: { label: "İzmir", lat: 38.4192, lon: 27.1287, tz: "Europe/Istanbul" },
    doha: { label: "Doha", lat: 25.2854, lon: 51.5310, tz: "Asia/Qatar" },
    cairo: { label: "Cairo", lat: 30.0444, lon: 31.2357, tz: "Africa/Cairo" }
  }
};

const normalizeConfig = (raw) => {
  const config = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
  if (!raw || typeof raw !== "object") return config;

  if (Number.isInteger(raw.method)) config.method = raw.method;
  if (raw.school === 0 || raw.school === 1) config.school = raw.school;

  if (raw.cities && typeof raw.cities === "object") {
    const normalized = Object.entries(raw.cities).reduce((acc, [key, city]) => {
      if (!city || typeof city !== "object") return acc;
      const lat = Number(city.lat);
      const lon = Number(city.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || !city.label || !city.tz) return acc;
      acc[key] = { label: String(city.label), lat, lon, tz: String(city.tz) };
      return acc;
    }, {});
    if (Object.keys(normalized).length > 0) config.cities = normalized;
  }

  if (raw.default_city && config.cities[raw.default_city]) config.default_city = raw.default_city;
  return config;
};

const getConfig = (output) => {
  const runtimeConfig = typeof window !== "undefined" ? window.__prayertimes_config : null;
  return normalizeConfig((output && output.config) || runtimeConfig || DEFAULT_CONFIG);
};
// -----------------------------------------------------------------------------

// localStorage key for which city is currently displayed
const CITY_KEY = "prayertimes_city";

const DEFAULT_CONFIG_JSON = JSON.stringify(JSON.stringify(DEFAULT_CONFIG));

// Fetch all configured cities every refresh so cycling is instant and setup lives in one file.
export const command = `
  python3 - <<'PY'
import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CONFIG_PATH = os.path.expanduser("~/.config/salah-bar/config.json")
DEFAULT_CONFIG = json.loads(${DEFAULT_CONFIG_JSON})

def normalize_config(raw):
  config = json.loads(json.dumps(DEFAULT_CONFIG))
  if not isinstance(raw, dict):
    return config

  if isinstance(raw.get("method"), int):
    config["method"] = raw["method"]
  if raw.get("school") in (0, 1):
    config["school"] = raw["school"]

  cities = raw.get("cities")
  if isinstance(cities, dict):
    normalized = {}
    for key, city in cities.items():
      if not isinstance(city, dict):
        continue
      try:
        normalized[key] = {
          "label": str(city["label"]),
          "lat": float(city["lat"]),
          "lon": float(city["lon"]),
          "tz": str(city["tz"]),
        }
      except Exception:
        continue
    if normalized:
      config["cities"] = normalized

  default_city = raw.get("default_city")
  if default_city in config["cities"]:
    config["default_city"] = default_city
  return config

try:
  with open(CONFIG_PATH) as f:
    config = normalize_config(json.load(f))
except Exception:
  config = normalize_config({})

timings = {}
for key, city in config["cities"].items():
  date_str = datetime.now(ZoneInfo(city["tz"])).strftime("%d-%m-%Y")
  url = (
    f"https://api.aladhan.com/v1/timings/{date_str}"
    f"?latitude={city['lat']}&longitude={city['lon']}"
    f"&method={config['method']}&school={config['school']}"
  )
  with urllib.request.urlopen(url, timeout=10) as response:
    timings[key] = json.load(response)

print(json.dumps({"config": config, "timings": timings}, ensure_ascii=False))
PY
`;

export const refreshFrequency = 60 * 60 * 1000; // refetch API every hour

export const initialState = { output: null, error: null };

export const updateState = ({ output, error }, previousState) => {
  if (error) return { ...previousState, error: String(error) };
  try {
    const parsed = JSON.parse(output);
    return { output: parsed, error: null };
  } catch (e) {
    return { ...previousState, error: "parse failed: " + e.message };
  }
};

// -------- STYLES -------------------------------------------------------------
export const className = `
  top: 40px;
  right: 40px;
  width: 280px;
  pointer-events: all;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif;
  color: rgba(255, 255, 255, 0.95);
  background: rgba(20, 20, 25, 0.55);
  -webkit-backdrop-filter: blur(28px) saturate(1.4);
  backdrop-filter: blur(28px) saturate(1.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  padding: 18px 20px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
  font-size: 13px;
  line-height: 1.4;

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    cursor: grab;
  }
  .header:active { cursor: grabbing; }
  .header .right { display: flex; align-items: center; gap: 8px; }
  .toggle {
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    opacity: 0.55;
    user-select: none;
    padding: 2px 4px;
    border-radius: 4px;
  }
  .toggle:hover { opacity: 1; background: rgba(255,255,255,0.08); }

  [data-collapsed="true"] .header {
    margin-bottom: 8px;
    padding-bottom: 8px;
  }
  [data-collapsed="true"] .next-label,
  [data-collapsed="true"] .prayers,
  [data-collapsed="true"] .footer { display: none; }
  [data-collapsed="true"] .next-block {
    padding: 8px 12px;
    margin-bottom: 0;
  }
  [data-collapsed="true"] .next-name {
    margin-bottom: 4px;
  }
  [data-collapsed="true"] .next-name-en { font-size: 13px; }
  [data-collapsed="true"] .next-name-ar { font-size: 14px; }
  [data-collapsed="true"] .next-countdown {
    margin-top: 0;
    font-size: 18px;
  }
  [data-collapsed="true"] .date { display: none; }
  .city {
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    letter-spacing: 0.2px;
  }
  .city:hover { color: #7dd3fc; }
  .date {
    font-size: 11px;
    opacity: 0.55;
  }

  .next-block {
    background: linear-gradient(135deg, rgba(125, 211, 252, 0.12), rgba(125, 211, 252, 0.04));
    border: 1px solid rgba(125, 211, 252, 0.2);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 14px;
  }
  .next-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    opacity: 0.55;
    margin-bottom: 4px;
  }
  .next-name {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .next-name-en { font-size: 16px; font-weight: 600; }
  .next-name-ar { font-size: 17px; opacity: 0.85; font-family: "SF Arabic", "Geeza Pro", sans-serif; }
  .next-countdown {
    font-size: 22px;
    font-weight: 300;
    font-variant-numeric: tabular-nums;
    margin-top: 6px;
    color: #7dd3fc;
    letter-spacing: 0.5px;
  }

  .prayers { display: flex; flex-direction: column; gap: 6px; }
  .row {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    align-items: center;
    padding: 6px 4px;
    border-radius: 6px;
    transition: background 0.15s;
  }
  .row.active { background: rgba(125, 211, 252, 0.08); }
  .row.passed { opacity: 0.4; }
  .name-en { font-weight: 500; }
  .name-ar { font-family: "SF Arabic", "Geeza Pro", sans-serif; opacity: 0.8; text-align: center; }
  .time { font-variant-numeric: tabular-nums; opacity: 0.85; text-align: right; }

  .footer {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    opacity: 0.45;
  }

  .error { color: #fca5a5; font-size: 11px; padding: 8px 0; }
`;

// -------- HELPERS ------------------------------------------------------------
const PRAYERS = [
  { key: "Fajr",    en: "Fajr",    ar: "الفجر"   },
  { key: "Dhuhr",   en: "Dhuhr",   ar: "الظهر"   },
  { key: "Asr",     en: "Asr",     ar: "العصر"   },
  { key: "Maghrib", en: "Maghrib", ar: "المغرب"  },
  { key: "Isha",    en: "Isha",    ar: "العشاء"  }
];

// Build a Date object for today at HH:MM in the given IANA timezone.
const buildPrayerDate = (hhmm, tz) => {
  // Get today's Y-M-D in the target timezone
  const now = new Date();
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit"
  });
  const parts = fmt.formatToParts(now).reduce((acc, p) => {
    acc[p.type] = p.value; return acc;
  }, {});
  const isoLocal = `${parts.year}-${parts.month}-${parts.day}T${hhmm}:00`;
  // Compute the timezone offset for that wall-clock moment in that tz
  // by formatting a known UTC instant in that tz and diffing.
  const probe = new Date(isoLocal + "Z"); // pretend UTC
  const tzString = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  }).format(probe);
  // Parse "MM/DD/YYYY, HH:MM:SS"
  const m = tzString.match(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+):(\d+)/);
  if (!m) return new Date(isoLocal);
  const asUtc = Date.UTC(+m[3], +m[1]-1, +m[2], +m[4], +m[5], +m[6]);
  const offsetMs = asUtc - probe.getTime();
  return new Date(probe.getTime() - offsetMs);
};

const fmtCountdown = (ms) => {
  if (ms < 0) ms = 0;
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
};

const loadCity = () => {
  const config = getConfig(window.__prayertimes_output);
  try {
    const v = localStorage.getItem(CITY_KEY);
    return (v && config.cities[v]) ? v : config.default_city;
  } catch (e) { return config.default_city; }
};

const saveCity = (c) => {
  try { localStorage.setItem(CITY_KEY, c); } catch (e) {}
  // Also write to shared state file so the SwiftBar menu-bar plugin sees it.
  // Best-effort — silently no-ops if Übersicht's run() API isn't available.
  const cmd = `printf %s ${c} > "$HOME/.prayertimes_city"`;
  try {
    if (typeof run === "function") run(cmd);
    else if (typeof window !== "undefined" && typeof window.run === "function") window.run(cmd);
  } catch (e) {}
};

const COLLAPSED_KEY = "prayertimes_collapsed";
const loadCollapsed = () => {
  try { return localStorage.getItem(COLLAPSED_KEY) === "1"; } catch (e) { return false; }
};
const saveCollapsed = (v) => {
  try { localStorage.setItem(COLLAPSED_KEY, v ? "1" : "0"); } catch (e) {}
};
const toggleCollapse = (e) => {
  if (e) e.stopPropagation();
  const inner = document.querySelector("[data-prayer-widget]");
  const w = inner ? findWrapper(inner) : null;
  // Capture right edge BEFORE the size change so we can keep it anchored.
  const oldRight = w ? w.getBoundingClientRect().right : null;
  saveCollapsed(!loadCollapsed());
  rebuildWidget();
  applyCollapsedToWrapper();
  if (w && oldRight !== null) {
    const r = w.getBoundingClientRect();
    const newLeft = Math.max(0, Math.round(oldRight - r.width));
    w.style.left = newLeft + "px";
    w.style.right = "auto";
    savePos(Math.round(r.top), newLeft);
  }
};

const cycleCity = () => {
  const keys = Object.keys(getConfig(window.__prayertimes_output).cities);
  const cur = loadCity();
  const next = keys[(keys.indexOf(cur) + 1) % keys.length];
  saveCity(next);
  // Force the widget to re-render by triggering Übersicht's refresh.
  // No reliable public refresh API exists, so we just kick the ticker
  // which will call applyPosToWrapper + we manually rebuild via the DOM.
  rebuildWidget();
};

// Force a re-render every second for the live countdown.
// We do this by stuffing a timer on window so it survives reloads.
if (typeof window !== "undefined" && !window.__prayertimes_ticker) {
  window.__prayertimes_ticker = setInterval(() => {
    if (typeof rebuildWidget === "function") rebuildWidget();
    if (typeof applyPosToWrapper === "function") applyPosToWrapper();
    if (typeof applyCollapsedToWrapper === "function") applyCollapsedToWrapper();
  }, 1000);
}

// -------- DRAG-TO-MOVE -------------------------------------------------------
const POS_KEY = "prayertimes_pos";

const loadPos = () => {
  try {
    const raw = localStorage.getItem(POS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
};

const savePos = (top, left) => {
  try { localStorage.setItem(POS_KEY, JSON.stringify({ top, left })); } catch (e) {}
};

const positionStyle = () => {
  const p = loadPos();
  if (!p) return {};
  return { top: p.top + "px", left: p.left + "px", right: "auto", bottom: "auto" };
};

// Walk up from the inner div to Übersicht's positioned wrapper element.
const findWrapper = (inner) => {
  let el = inner;
  while (el && el !== document.body) {
    const cs = getComputedStyle(el);
    if (cs.position === "absolute" || cs.position === "fixed") return el;
    el = el.parentElement;
  }
  return null;
};

const applyCollapsedToWrapper = () => {
  const inner = document.querySelector("[data-prayer-widget]");
  if (!inner) return;
  const w = findWrapper(inner);
  if (!w) return;
  if (loadCollapsed()) {
    w.style.width = "auto";
    w.style.minWidth = "180px";
    w.style.padding = "12px 16px";
  } else {
    w.style.width = "";
    w.style.minWidth = "";
    w.style.padding = "";
  }
};

const applyPosToWrapper = () => {
  const inner = document.querySelector("[data-prayer-widget]");
  if (!inner) return;
  const w = findWrapper(inner);
  if (!w) return;
  const p = loadPos();
  if (!p) return;
  w.style.top = p.top + "px";
  w.style.left = p.left + "px";
  w.style.right = "auto";
  w.style.bottom = "auto";
};

const startDrag = (e) => {
  // Let clicks on city/toggle work normally (no drag).
  if (e.target.closest(".city") || e.target.closest(".toggle")) return;
  e.preventDefault();
  const inner = e.currentTarget.closest("[data-prayer-widget]");
  if (!inner) return;
  const widgetEl = findWrapper(inner);
  if (!widgetEl) return;
  const rect = widgetEl.getBoundingClientRect();
  const offsetX = e.clientX - rect.left;
  const offsetY = e.clientY - rect.top;

  const onMove = (ev) => {
    const left = Math.max(0, ev.clientX - offsetX);
    const top  = Math.max(0, ev.clientY - offsetY);
    widgetEl.style.left = left + "px";
    widgetEl.style.top = top + "px";
    widgetEl.style.right = "auto";
    widgetEl.style.bottom = "auto";
  };
  const onUp = () => {
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    const r = widgetEl.getBoundingClientRect();
    savePos(Math.round(r.top), Math.round(r.left));
  };
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
};

// -------- VIEW COMPUTATION ---------------------------------------------------
const cleanTime = (t) => (t || "").split(" ")[0];

const computeView = (city, output) => {
  const config = getConfig(output);
  const cityConfig = config.cities[city];
  const cityData = output && output.timings && output.timings[city];
  if (!cityData || !cityData.data) return null;
  const tz = cityConfig.tz;
  const timings = cityData.data.timings;
  const hijri = cityData.data.date && cityData.data.date.hijri;
  const cityLabel = cityConfig.label;

  const now = new Date();
  const schedule = PRAYERS.map(p => ({
    ...p,
    timeStr: cleanTime(timings[p.key]),
    date: buildPrayerDate(cleanTime(timings[p.key]), tz)
  }));

  let next = schedule.find(p => p.date > now);
  if (!next) {
    next = { ...schedule[0], date: new Date(schedule[0].date.getTime() + 24*3600*1000) };
  }

  const countdownMs = next.date - now;
  const hijriLabel = hijri ? `${hijri.day} ${hijri.month.en} ${hijri.year} AH` : "";

  return { cityLabel, hijriLabel, schedule, next, countdownMs };
};

// Imperatively update the widget's DOM from current localStorage city + cached output.
const rebuildWidget = () => {
  const root = document.querySelector("[data-prayer-widget]");
  const out = window.__prayertimes_output;
  if (!root || !out) return;
  const city = loadCity();
  const collapsed = loadCollapsed();
  root.setAttribute("data-collapsed", collapsed ? "true" : "false");
  const toggleEl = root.querySelector(".toggle");
  if (toggleEl) toggleEl.textContent = collapsed ? "▸" : "▾";
  const v = computeView(city, out);
  if (!v) return;

  const setText = (sel, text) => { const el = root.querySelector(sel); if (el) el.textContent = text; };
  setText(".city", v.cityLabel + " ⇄");
  setText(".date", v.hijriLabel);
  setText(".next-name-en", v.next.en);
  setText(".next-name-ar", v.next.ar);
  setText(".next-countdown", fmtCountdown(v.countdownMs));

  const rows = root.querySelectorAll(".prayers .row");
  v.schedule.forEach((p, i) => {
    const row = rows[i];
    if (!row) return;
    const isNext = p.key === v.next.key && v.next.date.getTime() === p.date.getTime();
    const passed = p.date < new Date() && !isNext;
    row.className = `row ${isNext ? "active" : ""} ${passed ? "passed" : ""}`.trim();
    const setInRow = (sel, text) => { const el = row.querySelector(sel); if (el) el.textContent = text; };
    setInRow(".name-en", p.en);
    setInRow(".name-ar", p.ar);
    setInRow(".time", p.timeStr);
  });
};

// -------- RENDER -------------------------------------------------------------
export const render = ({ output, error }) => {
  const posStyle = positionStyle();

  if (error) {
    return <div data-prayer-widget style={posStyle}><div className="error">⚠ {error}</div></div>;
  }
  if (!output) {
    return <div data-prayer-widget style={posStyle}><div className="error">Loading prayer times…</div></div>;
  }

  // Stash output for rebuildWidget + ticker.
  if (typeof window !== "undefined") {
    window.__prayertimes_output = output;
    window.__prayertimes_config = getConfig(output);
  }

  const city = loadCity();
  const v = computeView(city, output);
  if (!v) {
    return <div data-prayer-widget style={posStyle}><div className="error">Loading prayer times…</div></div>;
  }
  const { cityLabel, hijriLabel, schedule, next, countdownMs } = v;
  const now = new Date();

  const collapsed = loadCollapsed();

  return (
    <div data-prayer-widget data-collapsed={collapsed ? "true" : "false"} style={posStyle}>
      <div className="header" onMouseDown={startDrag}>
        <div className="city" onClick={cycleCity}>
          {cityLabel} ⇄
        </div>
        <div className="right">
          <div className="date">{hijriLabel}</div>
          <div className="toggle" onClick={toggleCollapse}>{collapsed ? "▸" : "▾"}</div>
        </div>
      </div>

      <div className="next-block">
        <div className="next-label">Next Prayer</div>
        <div className="next-name">
          <span className="next-name-en">{next.en}</span>
          <span className="next-name-ar">{next.ar}</span>
        </div>
        <div className="next-countdown">{fmtCountdown(countdownMs)}</div>
      </div>

      <div className="prayers">
        {schedule.map(p => {
          const isNext = p.key === next.key && next.date.getTime() === p.date.getTime();
          const passed = p.date < now && !isNext;
          return (
            <div key={p.key} className={`row ${isNext ? "active" : ""} ${passed ? "passed" : ""}`}>
              <span className="name-en">{p.en}</span>
              <span className="name-ar">{p.ar}</span>
              <span className="time">{p.timeStr}</span>
            </div>
          );
        })}
      </div>

      <div className="footer">
        <span>{`Method ${getConfig(output).method} · ${getConfig(output).school === 1 ? "Hanafi" : "Shafi'i"}`}</span>
        <span>aladhan.com</span>
      </div>
    </div>
  );
};
