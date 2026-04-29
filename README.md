# salah-bar — Islamic Prayer Times for macOS

Live Islamic prayer times for **İzmir / Doha / Cairo** with a real-time countdown
to the next prayer. Two surfaces, kept in sync:

- 🖥  **Desktop widget** (Übersicht) — glassy panel with full schedule, drag-to-move,
  click-to-cycle city, click-to-collapse to a compact pill.
- 🕌  **Menu bar** (SwiftBar) — `🕌 Dhuhr 02:34` countdown (HH:MM), click to expand
  the day's full schedule, switch city from a submenu.

Times come from [aladhan.com](https://aladhan.com) (no key needed), method =
**Diyanet İşleri Başkanlığı** (Turkey, method 13), school = **Shafi'i**.

## Quick install

Requires [Homebrew](https://brew.sh).

```bash
git clone https://github.com/Abdalmoamen95/salah-bar.git
cd salah-bar
./install.sh
```

The installer will:

1. Install [Übersicht](https://tracesof.net/uebersicht/) if you don't have it.
2. Symlink `prayertimes.widget/` into Übersicht's widgets folder.
3. Install [SwiftBar](https://swiftbar.app) if you don't have it.
4. Point SwiftBar at this repo's `menubar/` folder for plugins.
5. Launch both apps.

## Components

```
.
├── prayertimes.widget/           # Übersicht widget
│   ├── index.jsx
│   └── README.md
├── menubar/
│   └── prayertimes.30s.py        # SwiftBar plugin (refreshes every 30s)
├── install.sh
└── README.md
```

The two surfaces share state via `~/.prayertimes_city`. Cycling the city in
either place updates the file; the other side picks it up on its next refresh.

## Configuration

Edit the `CITIES` map at the top of either:

- [`prayertimes.widget/index.jsx`](prayertimes.widget/index.jsx) for the widget
- [`menubar/prayertimes.30s.py`](menubar/prayertimes.30s.py) for the menu bar

Add your city's coordinates (from [Google Maps](https://maps.google.com) or `maps.apple.com`),
its IANA timezone, and a display label. Then set it as `DEFAULT_CITY`.

### Calculation method

Change `METHOD` to match your country or preferred authority:

| Method | Authority | Used in |
|--------|-----------|---------|
| 1  | University of Islamic Sciences, Karachi | Pakistan, Bangladesh, India |
| 2  | Islamic Society of North America (ISNA) | USA, Canada |
| 3  | Muslim World League (MWL) | Europe, Far East |
| 4  | Umm Al-Qura University, Makkah | Saudi Arabia |
| 5  | Egyptian General Authority of Survey | Egypt |
| 7  | Institute of Geophysics, University of Tehran | Iran |
| 8  | Gulf Region | Gulf states |
| 9  | Kuwait | Kuwait |
| 10 | Qatar | Qatar |
| 11 | Majlis Ugama Islam Singapura (MUIS) | Singapore |
| 12 | Union Organization Islamic de France | France |
| 13 | Diyanet İşleri Başkanlığı *(default)* | Turkey |
| 14 | Spiritual Administration of Muslims of Russia | Russia |
| 15 | Moonsighting Committee Worldwide | UK & worldwide |

### School (Asr time)

Change `SCHOOL` in both files:

| Value | School | Asr shadow ratio |
|-------|--------|-----------------|
| `0` | Shafi'i *(default)* | 1× object length |
| `1` | Hanafi | 2× object length |

## Widget controls

- **Drag** the header bar to reposition.
- **Click the city name** (top-left) to cycle İzmir → Doha → Cairo.
- **Click the ▾ / ▸** to collapse to a small pill or expand to full schedule.

## Menu bar controls

- **Click** `🕌 …` to open the dropdown with the day's full schedule.
- **Switch city** submenu writes to the shared state file.
- **Refresh** forces a re-fetch.

## Troubleshooting

**Widget doesn't appear.** Make sure Übersicht has been launched once and is
running:

```bash
pgrep -fl Übersicht
```

If clicks pass through to the desktop, check **System Settings → Desktop & Dock
→ Click wallpaper to reveal desktop**, set it to *Only in Stage Manager* (or
*Never*).

**Menu bar plugin not visible.** Confirm SwiftBar is pointed at the right
folder:

```bash
defaults read com.ameba.SwiftBar PluginDirectory
```

Should match `<repo>/menubar`. Then restart SwiftBar:

```bash
osascript -e 'tell application "SwiftBar" to quit'; open -a SwiftBar
```

**Times look wrong.** Verify the calculation method matches your local
preference and that your city's timezone is correct in the `CITIES` map.

## Uninstall

```bash
rm "$HOME/Library/Application Support/Übersicht/widgets/prayertimes.widget"
# Remove the SwiftBar plugin reference (or just point SwiftBar elsewhere)
defaults delete com.ameba.SwiftBar PluginDirectory
rm -f "$HOME/.prayertimes_city"
rm -rf "$HOME/Library/Caches/prayertimes"
```

## License

MIT.
