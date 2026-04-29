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

Add coordinates for your city, then optionally change `DEFAULT_CITY`. To use a
different calculation method, change `METHOD` (and `SCHOOL` for Hanafi vs.
Shafi'i Asr). See the [Aladhan API docs](https://aladhan.com/prayer-times-api).

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
