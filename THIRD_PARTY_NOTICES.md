# Third-party notices

Salah Bar is "all rights reserved" (see [LICENSE](LICENSE)), except for the
components below, which keep their own licenses and owners.

## Sparkle (auto-updates)
Copyright (c) 2006–2013 Andy Matuschak and the Sparkle Project contributors.
MIT License: https://github.com/sparkle-project/Sparkle/blob/2.x/LICENSE

## Prayer-time calculation
Since 2.8.0 Salah Bar computes the sun's position with its own code, written
from the U.S. Naval Observatory's public-domain "Approximate Solar
Coordinates" (https://aa.usno.navy.mil/faq/sun_approx).

Versions 2.0.0 to 2.7.3 instead used `SolarModel.swift`, a Swift port of the
astronomical algorithm of **PrayTimes.js**, Copyright (c) 2007–2011
PrayTimes.org (Hamid Zarrabi-Zadeh). As a derived work it is licensed under
the **GNU Lesser General Public License v3.0**
(https://www.gnu.org/licenses/lgpl-3.0.html), and its source stays published in
[`third-party/SolarModel-2.0-2.7.3.swift`](third-party/SolarModel-2.0-2.7.3.swift)
for those versions.

## The Quran text
The Arabic of the Quranic quotes added in Salah Bar is from the **Tanzil Quran Text** (quran-simple),
Copyright (c) 2007–2026 Tanzil Project, https://tanzil.net, used verbatim
under its terms of use.

## Translations
English quotes use **Sahih International**; Turkish quotes use the
**Diyanet İşleri Başkanlığı** translation. These belong to their publishers.

## Quran recitations
The Quran player streams (and, on request, downloads) recitations from
**mp3quran.net**, https://mp3quran.net, using its public API. The reciters
list bundled with the app comes from the same API. mp3quran.net's policy
(https://www.mp3quran.net/eng/privacy, "Copyrights") states: "All rights are
available to everyone, and we allow any visitor or developer to copy any
material or use any link on the websites". The recordings belong to their
reciters and producers and are not covered by Salah Bar's license.

## Adhan recordings
These bundled recordings are used under open licences (Salah Bar trims them,
evens out their volume and converts them; the CC BY-SA ones stay under CC BY-SA):

- "Call to prayer from the Prophet's Mosque" by ejaz215, CC BY 3.0
  (https://creativecommons.org/licenses/by/3.0/), via Wikimedia Commons:
  https://commons.wikimedia.org/wiki/File:33937_ejaz215_call-to-prayer-from-the-prophet-s-mo.ogg
- "AZAAN in Makkah" by Seyfula Islam, CC BY 3.0, via Wikimedia Commons:
  https://commons.wikimedia.org/wiki/File:Adhan,_Great_Mosque_of_Mecca_-_Jan_21,_2013.webm
- "Eid al-Fitr Fajr azan at Malmö Mosque" (muezzin Besim Azemi) by Islamic
  Center Malmö, CC BY 3.0, via Wikimedia Commons:
  https://commons.wikimedia.org/wiki/File:Eid_al-Fitr_Fajr_azan_at_Malmö_Mosque_-_19_August_2012.webm
- "Adhan in Shalqar mosque" by Esetok, CC BY-SA 4.0
  (https://creativecommons.org/licenses/by-sa/4.0/), via Wikimedia Commons:
  https://commons.wikimedia.org/wiki/File:Adhan_in_Shalqar_mosque.webm
- "Islamic Call to Prayer (Dhuhr Adhan Audiophile Field Recording from
  Hamtramck, MI)" by RJStefanski, CC BY 3.0, via Freesound:
  https://freesound.org/people/RJStefanski/sounds/255231/
- "adzan-forest" by bagustris (Bagus Tris Atmaja), CC0, via Freesound:
  https://freesound.org/people/bagustris/sounds/508441/

The other adhan recordings, bundled and in the online library, belong to
their reciters and producers and are not covered by Salah Bar's license.

## Official prayer-time data
Salah Bar's accuracy-test data comes from
Diyanet İşleri Başkanlığı (namazvakitleri.diyanet.gov.tr) and Aladhan
(aladhan.com), and is used only to test accuracy.
