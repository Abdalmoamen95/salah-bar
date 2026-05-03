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
  language: "en",
  flash_warning: {
    enabled: true,
    minutes: 5
  },
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
  if (raw.language && ["en", "tr"].includes(raw.language)) config.language = raw.language;

  if (raw.flash_warning && typeof raw.flash_warning === "object") {
    if (typeof raw.flash_warning.enabled === "boolean") {
      config.flash_warning.enabled = raw.flash_warning.enabled;
    }
    if (Number.isInteger(raw.flash_warning.minutes) && raw.flash_warning.minutes > 0) {
      config.flash_warning.minutes = raw.flash_warning.minutes;
    }
  }

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
CACHE_DIR = os.path.expanduser("~/Library/Caches/prayertimes")
DEFAULT_CONFIG = json.loads(${DEFAULT_CONFIG_JSON})
os.makedirs(CACHE_DIR, exist_ok=True)

def normalize_config(raw):
  config = json.loads(json.dumps(DEFAULT_CONFIG))
  if not isinstance(raw, dict):
    return config

  if isinstance(raw.get("method"), int):
    config["method"] = raw["method"]
  if raw.get("school") in (0, 1):
    config["school"] = raw["school"]
  if raw.get("language") in ("en", "tr"):
    config["language"] = raw["language"]

  flash_warning = raw.get("flash_warning")
  if isinstance(flash_warning, dict):
    if isinstance(flash_warning.get("enabled"), bool):
      config["flash_warning"]["enabled"] = flash_warning["enabled"]
    minutes = flash_warning.get("minutes")
    if isinstance(minutes, int) and minutes > 0:
      config["flash_warning"]["minutes"] = minutes

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
  cache_file = os.path.join(CACHE_DIR, f"{key}_{date_str}.json")
  if not os.path.exists(cache_file) or os.path.getsize(cache_file) < 100:
    url = (
      f"https://api.aladhan.com/v1/timings/{date_str}"
      f"?latitude={city['lat']}&longitude={city['lon']}"
      f"&method={config['method']}&school={config['school']}"
    )
    with urllib.request.urlopen(url, timeout=10) as response:
      payload = response.read()
    with open(cache_file, "wb") as f:
      f.write(payload)
  with open(cache_file) as f:
    timings[key] = json.load(f)

print(json.dumps({"config": config, "timings": timings}, ensure_ascii=False))
PY
`;

export const refreshFrequency = 30 * 1000; // reload config every 30s; timings are cached per city/day

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
  background: rgba(20, 20, 25, 0.88);
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
    opacity: 1;
  }

  .next-block {
    background: linear-gradient(135deg, rgba(125, 211, 252, 0.12), rgba(125, 211, 252, 0.04));
    border: 1px solid rgba(125, 211, 252, 0.2);
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 14px;
  }
  .next-block.five-min-alert {
    border-color: rgba(74, 222, 128, 0.9);
    box-shadow: 0 0 0 1px rgba(74, 222, 128, 0.35), 0 0 18px rgba(74, 222, 128, 0.25);
    animation: pulse-green 1s ease-in-out infinite;
  }
  @keyframes pulse-green {
    0%, 100% {
      background: linear-gradient(135deg, rgba(74, 222, 128, 0.16), rgba(74, 222, 128, 0.06));
    }
    50% {
      background: linear-gradient(135deg, rgba(74, 222, 128, 0.32), rgba(74, 222, 128, 0.12));
    }
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
  .ayah {
    margin-bottom: 8px;
    text-align: center;
    font-size: 21px;
    line-height: 1.6;
    font-family: "SF Arabic", "Geeza Pro", sans-serif;
    color: #e2f3ff;
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
    flex-direction: column;
    gap: 7px;
    font-size: 10px;
    opacity: 0.45;
  }
  .footer-meta { display: flex; justify-content: space-between; }
  .footer-quote {
    font-size: 13px;
    line-height: 1.7;
    opacity: 0.9;
    text-align: center;
    font-family: "SF Arabic", "Geeza Pro", sans-serif;
    direction: rtl;
  }
  .footer-quote-en {
    font-size: 10px;
    line-height: 1.5;
    opacity: 0.75;
    text-align: center;
    font-style: italic;
    margin-top: 3px;
  }
  .footer-quote-ref {
    font-size: 9.5px;
    text-align: center;
    opacity: 0.55;
    margin-top: 2px;
  }

  .error { color: #fca5a5; font-size: 11px; padding: 8px 0; }
`;

// -------- HELPERS ------------------------------------------------------------
const PRAYER_NAMES = {
  en: ["Fajr",  "Dhuhr",  "Asr",     "Maghrib", "Isha"],
  tr: ["Sabah", "Öğle",   "İkindi",  "Akşam",   "Yatsı"],
};

// Returns a moon-phase emoji for a Hijri day (1-30).
const moonEmoji = (day) => {
  if (day <= 1)  return "🌑"; // new moon
  if (day <= 3)  return "🌒";
  if (day <= 6)  return "🌓";
  if (day <= 9)  return "🌔"; // first quarter
  if (day <= 12) return "🌕";
  if (day <= 14) return "🌕"; // full moon
  if (day <= 17) return "🌖";
  if (day <= 20) return "🌗"; // last quarter
  if (day <= 24) return "🌘";
  return "🌑"; // waning to new
};

const UI_STRINGS = {
  en: {
    nextPrayer: "Next Prayer",
    ah: "AH",
    hanafi: "Hanafi",
    shafii: "Shafi'i",
  },
  tr: {
    nextPrayer: "Sonraki Namaz",
    ah: "H",
    hanafi: "Hanefi",
    shafii: "Şafii",
  },
};

const FOOTER_QUOTES = [
  {
    ar: "إِنَّ الصَّلَاةَ كَانَتْ عَلَى الْمُؤْمِنِينَ كِتَابًا مَّوْقُوتًا",
    en: "Indeed, prayer has been decreed upon the believers a decree of specified times.",
    ref: "Quran 4:103",
  },
  {
    ar: "وَاسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ ۚ وَإِنَّهَا لَكَبِيرَةٌ إِلَّا عَلَى الْخَاشِعِينَ",
    en: "Seek help through patience and prayer; it is difficult except for the humbly submissive.",
    ref: "Quran 2:45",
  },
  {
    ar: "إِنَّ الصَّلَاةَ تَنْهَىٰ عَنِ الْفَحْشَاءِ وَالْمُنكَرِ",
    en: "Indeed, prayer prohibits immorality and wrongdoing.",
    ref: "Quran 29:45",
  },
  {
    ar: "وَهُوَ مَعَكُمْ أَيْنَ مَا كُنتُمْ ۚ وَاللَّهُ بِمَا تَعْمَلُونَ بَصِيرٌ",
    en: "He is with you wherever you are, and Allah of what you do is Seeing.",
    ref: "Quran 57:4",
  },
  {
    ar: "لَا يُكَلِّفُ اللَّهُ نَفْسًا إِلَّا وُسْعَهَا",
    en: "Allah does not burden a soul beyond that it can bear.",
    ref: "Quran 2:286",
  },
  {
    ar: "وَمَن يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ",
    en: "Whoever relies upon Allah — then He is sufficient for him.",
    ref: "Quran 65:3",
  },
  {
    ar: "فَاذْكُرُونِي أَذْكُرْكُمْ وَاشْكُرُوا لِي وَلَا تَكْفُرُونِ",
    en: "Remember Me; I will remember you. Be grateful to Me and do not deny Me.",
    ref: "Quran 2:152",
  },
  {
    ar: "إِنَّ مَعَ الْعُسْرِ يُسْرًا",
    en: "Verily, with hardship comes ease.",
    ref: "Quran 94:6",
  },
  {
    ar: "وَلَذِكْرُ اللَّهِ أَكْبَرُ",
    en: "And the remembrance of Allah is greater.",
    ref: "Quran 29:45",
  },
  {
    ar: "أَحَبُّ الْأَعْمَالِ إِلَى اللَّهِ أَدْوَمُهَا وَإِنْ قَلَّ",
    en: "The most beloved deeds to Allah are those done consistently, even if small.",
    ref: "Sahih Bukhari & Muslim",
  },
  {
    ar: "لَا يُؤْمِنُ أَحَدُكُمْ حَتَّىٰ يُحِبَّ لِأَخِيهِ مَا يُحِبُّ لِنَفْسِهِ",
    en: "None of you truly believes until he loves for his brother what he loves for himself.",
    ref: "Sahih Bukhari & Muslim",
  },
  {
    ar: "الْكَلِمَةُ الطَّيِّبَةُ صَدَقَةٌ",
    en: "A kind word is a form of charity.",
    ref: "Sahih Bukhari",
  },
  {
    ar: "لَيْسَ الشَّدِيدُ بِالصُّرَعَةِ ۖ إِنَّمَا الشَّدِيدُ الَّذِي يَمْلِكُ نَفْسَهُ عِنْدَ الْغَضَبِ",
    en: "The strong person is not the wrestler; it is the one who controls himself when angry.",
    ref: "Sahih Bukhari & Muslim",
  },
  {
    ar: "يَسِّرُوا وَلَا تُعَسِّرُوا، وَبَشِّرُوا وَلَا تُنَفِّرُوا",
    en: "Make things easy, do not make them difficult. Give glad tidings and do not drive people away.",
    ref: "Sahih Bukhari & Muslim",
  },
  {
    ar: "مَنْ كَانَ يُؤْمِنُ بِاللَّهِ وَالْيَوْمِ الْآخِرِ فَلْيَقُلْ خَيْرًا أَوْ لِيَصْمُتْ",
    en: "Whoever believes in Allah and the Last Day, let him speak good or remain silent.",
    ref: "Sahih Bukhari & Muslim",
  },
  {
    ar: "الدُّنْيَا سِجْنُ الْمُؤْمِنِ وَجَنَّةُ الْكَافِرِ",
    en: "The world is a prison for the believer and a paradise for the disbeliever.",
    ref: "Sahih Muslim",
  },
  {
    ar: "إِنَّ اللَّهَ جَمِيلٌ يُحِبُّ الْجَمَالَ",
    en: "Allah is beautiful and He loves beauty.",
    ref: "Sahih Muslim",
  },
  {
    ar: "الطَّهُورُ شَطْرُ الْإِيمَانِ",
    en: "Purity is half of faith.",
    ref: "Sahih Muslim",
  },
];

// Pick a quote based on 30-min slots so it changes every 30 minutes.
const currentQuote = () => {
  const now = new Date();
  const slot = Math.floor((now.getHours() * 60 + now.getMinutes()) / 30);
  return FOOTER_QUOTES[slot % FOOTER_QUOTES.length];
};

const PRAYERS = [
  { key: "Fajr",    ar: "الفجر"   },
  { key: "Dhuhr",   ar: "الظهر"   },
  { key: "Asr",     ar: "العصر"   },
  { key: "Maghrib", ar: "المغرب"  },
  { key: "Isha",    ar: "العشاء"  }
];

const PRAYER_AYAH = "وَعَجِلْتُ إِلَيْكَ رَبِّ لِتَرْضَىٰ";
const AYAH_WINDOW_MS = 2 * 60 * 1000;
const FORCE_AYAH_TEST = true;
const FORCE_FIVE_MIN_ALERT_TEST = false;
const COUNTDOWN_TICK_MS = 1000;

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

const isFlashAlertActive = (countdownMs, output) => {
  const cfg = getConfig(output);
  const flash = cfg.flash_warning || { enabled: true, minutes: 5 };
  if (!flash.enabled) return false;
  const windowMs = flash.minutes * 60 * 1000;
  return countdownMs > 0 && countdownMs <= windowMs;
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

// Update countdown every second without rebuilding the whole widget.
if (typeof window !== "undefined") {
  // Clear any legacy full-rebuild ticker from older widget versions.
  if (window.__prayertimes_ticker) {
    clearInterval(window.__prayertimes_ticker);
    window.__prayertimes_ticker = null;
  }

  // Ensure exactly one countdown ticker is active after widget reloads.
  // Optimization: Only update DOM when minutes change, not every second
  if (window.__prayertimes_countdown_ticker) {
    clearInterval(window.__prayertimes_countdown_ticker);
  }
  let lastMinute = -1;
  window.__prayertimes_countdown_ticker = setInterval(() => {
    if (typeof document !== "undefined" && document.hidden) return;
    
    const now = new Date();
    const currentMinute = now.getMinutes();
    
    // Only call updateLiveCountdown if minute changed
    if (currentMinute !== lastMinute || lastMinute === -1) {
      lastMinute = currentMinute;
      if (typeof updateLiveCountdown === "function") updateLiveCountdown();
    }
  }, COUNTDOWN_TICK_MS);
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
  const lang = config.language || "en";
  const ui = UI_STRINGS[lang] || UI_STRINGS.en;
  const names = PRAYER_NAMES[lang] || PRAYER_NAMES.en;
  const schedule = PRAYERS.map((p, i) => ({
    ...p,
    localName: names[i],
    timeStr: cleanTime(timings[p.key]),
    date: buildPrayerDate(cleanTime(timings[p.key]), tz)
  }));

  let next = schedule.find(p => p.date > now);
  if (!next) {
    next = { ...schedule[0], date: new Date(schedule[0].date.getTime() + 24*3600*1000) };
  }

  const currentPrayer = schedule.find(p => {
    const diff = now - p.date;
    return diff >= 0 && diff < AYAH_WINDOW_MS;
  }) || null;
  const showAyah = FORCE_AYAH_TEST || !!currentPrayer;

  const countdownMs = next.date - now;
  const hijriDay = hijri ? parseInt(hijri.day, 10) : 0;
  const moonPhase = moonEmoji(hijriDay);
  const hijriLabel = hijri ? `${moonPhase} ${hijri.day} ${hijri.month.en} ${hijri.year} ${ui.ah}` : "";

  return { cityLabel, hijriLabel, schedule, next, countdownMs, currentPrayer, showAyah, ui };
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
  setText(".next-label", v.ui.nextPrayer);
  const nextBlock = root.querySelector(".next-block");
  const ayah = root.querySelector(".ayah");
  const fiveMinAlert = FORCE_FIVE_MIN_ALERT_TEST || isFlashAlertActive(v.countdownMs, out);
  if (nextBlock) nextBlock.classList.toggle("five-min-alert", fiveMinAlert);
  if (ayah) ayah.style.display = v.showAyah ? "block" : "none";
  setText(".next-name-en", `${v.next.localName} / ${v.next.ar}`);
  setText(".next-name-ar", "");
  setText(".next-countdown", fmtCountdown(v.countdownMs));

  const rows = root.querySelectorAll(".prayers .row");
  v.schedule.forEach((p, i) => {
    const row = rows[i];
    if (!row) return;
    const isActive = v.showAyah
      ? !!v.currentPrayer && p.key === v.currentPrayer.key && v.currentPrayer.date.getTime() === p.date.getTime()
      : p.key === v.next.key && v.next.date.getTime() === p.date.getTime();
    const passed = p.date < new Date() && !isActive;
    row.className = `row ${isActive ? "active" : ""} ${passed ? "passed" : ""}`.trim();
    const setInRow = (sel, text) => { const el = row.querySelector(sel); if (el) el.textContent = text; };
    setInRow(".name-en", `${p.localName} / ${p.ar}`);
    setInRow(".name-ar", "");
    setInRow(".time", p.timeStr);
  });

  const footerSchool = root.querySelector(".footer-meta span");
  if (footerSchool) {
    const cfg = window.__prayertimes_config || {};
    footerSchool.textContent = `Method ${cfg.method} · ${cfg.school === 1 ? v.ui.hanafi : v.ui.shafii}`;
  }
  const q = currentQuote();
  const footerQuote = root.querySelector(".footer-quote");
  const footerRef = root.querySelector(".footer-quote-ref");
  if (footerQuote) footerQuote.textContent = q.ar;
  const footerEn = root.querySelector(".footer-quote-en");
  if (footerEn) footerEn.textContent = q.en;
  if (footerRef) footerRef.textContent = q.ref;
};

const updateLiveCountdown = () => {
  const root = document.querySelector("[data-prayer-widget]");
  const out = window.__prayertimes_output;
  if (!root || !out) return;

  const city = loadCity();
  const v = computeView(city, out);
  if (!v) return;

  const currentPrayerSig = v.currentPrayer ? `${v.currentPrayer.key}:${v.currentPrayer.date.getTime()}` : "-";
  const viewSig = `${city}|${v.next.key}:${v.next.date.getTime()}|${currentPrayerSig}|${v.showAyah ? 1 : 0}`;
  if (window.__prayertimes_view_sig !== viewSig) {
    window.__prayertimes_view_sig = viewSig;
    rebuildWidget();
    return;
  }

  const countdownEl = root.querySelector(".next-countdown");
  if (countdownEl) countdownEl.textContent = fmtCountdown(v.countdownMs);

  const nextBlock = root.querySelector(".next-block");
  const fiveMinAlert = FORCE_FIVE_MIN_ALERT_TEST || isFlashAlertActive(v.countdownMs, out);
  if (nextBlock) nextBlock.classList.toggle("five-min-alert", fiveMinAlert);
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
  const { cityLabel, hijriLabel, schedule, next, countdownMs, currentPrayer, showAyah, ui } = v;
  const now = new Date();
  const fiveMinAlert = FORCE_FIVE_MIN_ALERT_TEST || isFlashAlertActive(countdownMs, output);
  const currentPrayerSig = currentPrayer ? `${currentPrayer.key}:${currentPrayer.date.getTime()}` : "-";
  const viewSig = `${city}|${next.key}:${next.date.getTime()}|${currentPrayerSig}|${showAyah ? 1 : 0}`;

  const collapsed = loadCollapsed();

  if (typeof window !== "undefined") {
    window.__prayertimes_view_sig = viewSig;
  }

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

      <div className={`next-block ${fiveMinAlert ? "five-min-alert" : ""}`.trim()}>
        <div className="ayah" style={{ display: showAyah ? "block" : "none" }}>{PRAYER_AYAH}</div>
        <div className="next-label">{ui.nextPrayer}</div>
        <div className="next-info">
          <div className="next-name">
            <span className="next-name-en">{next.localName} / {next.ar}</span>
            <span className="next-name-ar"></span>
          </div>
          <div className="next-countdown">{fmtCountdown(countdownMs)}</div>
        </div>
      </div>

      <div className="prayers">
        {schedule.map(p => {
          const isActive = showAyah
            ? !!currentPrayer && p.key === currentPrayer.key && currentPrayer.date.getTime() === p.date.getTime()
            : p.key === next.key && next.date.getTime() === p.date.getTime();
          const passed = p.date < now && !isActive;
          return (
            <div key={p.key} className={`row ${isActive ? "active" : ""} ${passed ? "passed" : ""}`}>
              <span className="name-en">{p.localName} / {p.ar}</span>
              <span className="name-ar"></span>
              <span className="time">{p.timeStr}</span>
            </div>
          );
        })}
      </div>

      <div className="footer">
        <div className="footer-meta">
          <span>{`Method ${getConfig(output).method} · ${getConfig(output).school === 1 ? ui.hanafi : ui.shafii}`}</span>
        </div>
        <div className="footer-quote">{currentQuote().ar}</div>
        <div className="footer-quote-en">{currentQuote().en}</div>
        <div className="footer-quote-ref">{currentQuote().ref}</div>
      </div>
    </div>
  );
};
