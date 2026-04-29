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

### Easiest (non-technical)

1. Download this repository as ZIP from GitHub.
2. Unzip it.
3. Double-click `setup.command`.
4. Follow prompts in Terminal.

The installer can install Homebrew for you if it is missing.

### Developer install

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
5. Create `~/.config/salah-bar/config.json` if you don't already have one.
6. Launch both apps.

After install, you can configure cities from the menu bar:

- `Configure -> Choose default city`
- `Configure -> Add preset city (Turkey/Egypt/Qatar)`
- `Configure -> Add custom city`
- `Configure -> Open config file`

## Components

```
.
├── prayertimes.widget/           # Übersicht widget
│   ├── index.jsx
│   └── README.md
├── menubar/
│   └── prayertimes.30s.py        # SwiftBar plugin (refreshes every 30s)
├── config.example.json           # Default user config copied on install
├── preset-cities.json            # Bundled city presets for Turkey, Egypt, Qatar
├── install.sh
├── setup.command                 # Double-click installer launcher
└── README.md
```

The two surfaces share state via `~/.prayertimes_city` and share configuration
via `~/.config/salah-bar/config.json`. Cycling the city in either place updates
the state file; the other side picks it up on its next refresh.

## Configuration

After install, edit:

```json
~/.config/salah-bar/config.json
```

You only need to edit one file. Both the widget and the menu bar read from it.

If you do not want to edit JSON manually, use the menu bar UI instead:

- Open `salah-bar` from the menu bar
- Choose `Configure`
- Pick `Add preset city` for Turkey, Egypt, or Qatar
- Pick `Add custom city` for everywhere else

Preset city chooser:

- Includes bundled populated-place presets for Turkey, Egypt, and Qatar
- Lets the user search, then choose a matching city from a filtered list
- Saves the selected city into the shared config automatically

Preset city data is bundled from GeoNames country dumps.

Example:

```json
{
  "default_city": "istanbul",
  "method": 13,
  "school": 0,
  "cities": {
    "istanbul": {
      "label": "Istanbul",
      "lat": 41.0082,
      "lon": 28.9784,
      "tz": "Europe/Istanbul"
    },
    "doha": {
      "label": "Doha",
      "lat": 25.2854,
      "lon": 51.5310,
      "tz": "Asia/Qatar"
    }
  }
}
```

Each city needs:

- `label`: name shown in the UI
- `lat`: latitude
- `lon`: longitude
- `tz`: IANA timezone, for example `Europe/Istanbul` or `America/Toronto`

Set `default_city` to one of the keys inside `cities`.

### Calculation method

Change `method` in `~/.config/salah-bar/config.json` to match your country or preferred authority:

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

Change `school` in `~/.config/salah-bar/config.json`:

| Value | School | Asr shadow ratio |
|-------|--------|-----------------|
| `0` | Shafi'i *(default)* | 1× object length |
| `1` | Hanafi | 2× object length |

## Widget controls

- **Drag** the header bar to reposition.
- **Click the city name** (top-left) to cycle through your configured cities.
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
preference and that your city's timezone is correct in `~/.config/salah-bar/config.json`.

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
