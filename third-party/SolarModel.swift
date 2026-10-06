// SolarModel.swift: a Swift port of the PrayTimes.js astronomical algorithm.
// Copyright (c) 2007-2011 PrayTimes.org; Swift port (c) 2026 Mumin Muhammedoglu.
// This file is licensed under the GNU Lesser General Public License v3.0
// (https://www.gnu.org/licenses/lgpl-3.0.html), unlike the rest of Salah Bar.
// See THIRD_PARTY_NOTICES.md.

import Foundation

/// Low-precision solar position and prayer-time geometry.
///
/// This is the algorithm of PrayTimes.js (praytimes.org), which Aladhan's
/// PHP library ports. Two evaluation modes cover the two references we
/// test against:
///
/// - `.perPrayer`: the sun's position is evaluated near each prayer's
///   approximate time (one iteration), as PrayTimes and Aladhan do.
/// - `.dailyAtMidnightUT`: the sun's position is evaluated once, at 0h UT
///   of the date, for every prayer. This matches the official Diyanet
///   tables (namazvakitleri.diyanet.gov.tr) far better than `.perPrayer`:
///   ~95% exact vs ~35% for Maghrib and Isha over 396 days × 7 cities.
///
/// All results are fractional hours after 0h UT of the civil date.
struct SolarModel {
    enum Evaluation: Sendable {
        case perPrayer
        case dailyAtMidnightUT
    }

    /// Sun altitude at sunrise/sunset: refraction plus the sun's semi-diameter.
    static let riseSetAngle = 0.833

    let latitude: Double
    let longitude: Double
    let evaluation: Evaluation
    /// Julian date of 0h UT on the civil date.
    let julianDay: Double

    init(year: Int, month: Int, day: Int, latitude: Double, longitude: Double, evaluation: Evaluation) {
        self.latitude = latitude
        self.longitude = longitude
        self.evaluation = evaluation
        self.julianDay = Self.julian(year: year, month: month, day: day)
    }

    struct RawTimes {
        var fajr: Double
        var sunrise: Double
        var dhuhr: Double
        var asr: Double
        var sunset: Double
        var maghrib: Double
        var isha: Double
    }

    /// Times in hours after 0h UT. `nil` angles (Maghrib) mean sunset;
    /// a nil Isha angle means the caller derives Isha from an interval.
    func times(fajrAngle: Double, maghribAngle: Double?, ishaAngle: Double?, asrShadowFactor: Double,
               angleBasedHighLatitude: Bool) -> RawTimes {
        // PrayTimes' initial guesses, as fractions of a day (local mean time).
        let fajr = sunAngleTime(fajrAngle, at: 5, counterClockwise: true)
        let sunrise = sunAngleTime(Self.riseSetAngle, at: 6, counterClockwise: true)
        let dhuhr = midDay(at: 12)
        let asr = asrTime(factor: asrShadowFactor, at: 13)
        let sunset = sunAngleTime(Self.riseSetAngle, at: 18, counterClockwise: false)
        let maghrib = maghribAngle.map { sunAngleTime($0, at: 18, counterClockwise: false) } ?? sunset
        let isha = ishaAngle.map { sunAngleTime($0, at: 18, counterClockwise: false) } ?? .nan

        // Local mean time → UT.
        let shift = -longitude / 15
        var raw = RawTimes(fajr: fajr + shift, sunrise: sunrise + shift, dhuhr: dhuhr + shift, asr: asr + shift,
                           sunset: sunset + shift, maghrib: maghrib + shift, isha: isha + shift)

        if angleBasedHighLatitude {
            // PrayTimes "AngleBased": cap Fajr/Isha at angle/60 of the night.
            let night = Self.timeDifference(raw.sunset, raw.sunrise)
            raw.fajr = adjustHighLatitude(raw.fajr, base: raw.sunrise, angle: fajrAngle, night: night, counterClockwise: true)
            if let ishaAngle {
                raw.isha = adjustHighLatitude(raw.isha, base: raw.sunset, angle: ishaAngle, night: night, counterClockwise: false)
            }
            if let maghribAngle {
                raw.maghrib = adjustHighLatitude(raw.maghrib, base: raw.sunset, angle: maghribAngle, night: night, counterClockwise: false)
            }
        }
        return raw
    }

    // MARK: - Geometry

    private func adjustHighLatitude(_ time: Double, base: Double, angle: Double, night: Double,
                                    counterClockwise: Bool) -> Double {
        let portion = angle / 60 * night
        let difference = counterClockwise ? Self.timeDifference(time, base) : Self.timeDifference(base, time)
        if time.isNaN || difference > portion {
            return base + (counterClockwise ? -portion : portion)
        }
        return time
    }

    /// Sun position for an approximate local time in hours.
    private func sun(at hours: Double) -> (declination: Double, equation: Double) {
        switch evaluation {
        case .perPrayer:
            // PrayTimes: jDate = julian − lng/(15·24), then + time/24.
            return Self.sunPosition(julianDay - longitude / (15 * 24) + hours / 24)
        case .dailyAtMidnightUT:
            return Self.sunPosition(julianDay)
        }
    }

    private func midDay(at hours: Double) -> Double {
        Self.fixHour(12 - sun(at: hours).equation)
    }

    private func sunAngleTime(_ angle: Double, at hours: Double, counterClockwise: Bool) -> Double {
        let declination = sun(at: hours).declination
        let noon = midDay(at: hours)
        let cosine = (-dsin(angle) - dsin(declination) * dsin(latitude)) / (dcos(declination) * dcos(latitude))
        guard (-1...1).contains(cosine) else { return .nan }
        let t = darccos(cosine) / 15
        return noon + (counterClockwise ? -t : t)
    }

    private func asrTime(factor: Double, at hours: Double) -> Double {
        let declination = sun(at: hours).declination
        let angle = -darccot(factor + dtan(abs(latitude - declination)))
        return sunAngleTime(angle, at: hours, counterClockwise: false)
    }

    // MARK: - Astronomy (PrayTimes.js)

    static func julian(year: Int, month: Int, day: Int) -> Double {
        var y = Double(year), m = Double(month)
        if m <= 2 {
            y -= 1
            m += 12
        }
        let a = (y / 100).rounded(.down)
        let b = 2 - a + (a / 4).rounded(.down)
        return (365.25 * (y + 4716)).rounded(.down) + (30.6001 * (m + 1)).rounded(.down) + Double(day) + b - 1524.5
    }

    static func sunPosition(_ jd: Double) -> (declination: Double, equation: Double) {
        let d = jd - 2451545.0
        let g = fixAngle(357.529 + 0.98560028 * d)
        let q = fixAngle(280.459 + 0.98564736 * d)
        let l = fixAngle(q + 1.915 * dsin(g) + 0.020 * dsin(2 * g))
        let e = 23.439 - 0.00000036 * d
        let ra = darctan2(dcos(e) * dsin(l), dcos(l)) / 15
        let equation = q / 15 - fixHour(ra)
        let declination = darcsin(dsin(e) * dsin(l))
        return (declination, equation)
    }

    static func timeDifference(_ from: Double, _ to: Double) -> Double {
        fixHour(to - from)
    }

    static func fixAngle(_ a: Double) -> Double { fix(a, 360) }
    static func fixHour(_ h: Double) -> Double { fix(h, 24) }

    private static func fix(_ a: Double, _ b: Double) -> Double {
        let r = a - b * (a / b).rounded(.down)
        return r < 0 ? r + b : r
    }
}

private func dsin(_ d: Double) -> Double { sin(d * .pi / 180) }
private func dcos(_ d: Double) -> Double { cos(d * .pi / 180) }
private func dtan(_ d: Double) -> Double { tan(d * .pi / 180) }
private func darcsin(_ x: Double) -> Double { asin(x) * 180 / .pi }
private func darccos(_ x: Double) -> Double { acos(x) * 180 / .pi }
private func darctan2(_ y: Double, _ x: Double) -> Double { atan2(y, x) * 180 / .pi }
private func darccot(_ x: Double) -> Double { atan(1 / x) * 180 / .pi }
