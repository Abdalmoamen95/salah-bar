# Prayer Times Widget for Übersicht

A floating macOS desktop widget showing prayer times for **İzmir, Doha, and Cairo**, with a live countdown to the next prayer.

- **Calculation**: Diyanet İşleri Başkanlığı, Turkey (method 13)
- **Madhhab**: Shafi'i (school 0)
- **Languages**: Arabic + English
- **API**: [Aladhan](https://aladhan.com) (free, no key)

---

## Install

### 1. Install Übersicht (one-time)

```bash
brew install --cask ubersicht
open -a Übersicht
```

Grant the permissions it asks for (Accessibility / Screen Recording — needed to render on the desktop).

### 2. Install the widget

Copy the `prayertimes.widget` folder into Übersicht's widgets directory:

```bash
cp -r prayertimes.widget ~/Library/Application\ Support/Übersicht/widgets/
```

That's it. The widget appears in the top-right corner. If you don't see it, click the Übersicht menu bar icon → Open Widgets Folder → make sure `prayertimes.widget` is there, then click "Refresh All".

---

## Use

- **Switch city**: click the city name (top-left of the widget). It cycles İzmir → Doha → Cairo → İzmir.
- **Countdown** updates every second.
- **Prayer times** refetch from the API every hour (timing data doesn't change within a day, so this is plenty).

---

## Customize

Open `~/Library/Application Support/Übersicht/widgets/prayertimes.widget/index.jsx` and edit the top of the file:

| Setting | Where | Notes |
|---|---|---|
| Default city | `DEFAULT_CITY = "izmir"` | `"izmir"`, `"doha"`, or `"cairo"` |
| Calculation method | `METHOD = 13` | 5 = Egypt, 10 = Qatar, 4 = Umm al-Qura, etc. ([full list](https://aladhan.com/calculation-methods)) |
| Madhhab | `SCHOOL = 0` | 0 = Shafi'i, 1 = Hanafi |
| Position | `top: 40px; right: 40px;` in `className` | Standard CSS — change to `left`, `bottom`, etc. |
| Width | `width: 280px;` | Resize as you like |
| Add a city | `CITIES = { ... }` object | Add `{ label, lat, lon, tz }` and a matching `case` in the shell command |

After any edit, Übersicht auto-reloads the widget (or click the menu bar icon → Refresh All).

---

## How it works

1. A shell command (`curl`) hits the Aladhan API once per hour with the current city's coordinates.
2. The response (today's 5 prayer times + Hijri date) is parsed into the widget state.
3. A 1-second ticker re-renders the countdown so it stays live.
4. The selected city is persisted in `/tmp/ubersicht_prayertimes_city` so it survives refreshes within a session.

---

## Troubleshooting

- **"Loading prayer times…" forever**: check your internet, then click Übersicht menu bar → Refresh All.
- **Times look wrong by a few minutes**: Diyanet's official Turkish times sometimes differ from Aladhan's approximation by 1–3 min. To match Diyanet exactly, you can add a `tune` parameter — let me know and I'll wire it in.
- **Want auto-detect location instead of city switcher**: also doable — say the word.
