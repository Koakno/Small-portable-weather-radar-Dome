# Small Portable Weather Radar

> A self-contained mobile weather radar project built from a $5 salvaged RV satellite dome, a cheap SDR, and open source software. No internet required, no subscription, no NWS data dependency — your own radar returns, updated locally.

**Built in Kokomo, Indiana. I nearly got hit by a tornado that NEXRAD couldn't see coming in time. That's the whole reason this exists.**

---

## Why This Exists

Every storm chaser on the road is looking at NEXRAD data that's 4-6 minutes old, from a radar station that might be 100+ miles away. At close range the NWS beam overshoots low-altitude storm features entirely, because of Earth curvature and beam elevation. When a supercell is 10 km away and moving at 40 mph, 6-minute-old data from a distant station isn't situational awareness. It's history.

I got close enough to a tornado once that NEXRAD flat out didn't have it — not "showed it late," didn't have it at all at the range I needed. That's what started this. This project generates local radar returns from a vehicle-mounted dish, in the 10-30 second range instead of minutes, at whatever range the hardware config supports.

Professional mobile Doppler radar trucks (DOW — Doppler on Wheels) do something similar. They cost $500,000+. This is built from salvage and hobbyist SDR gear.

**Status note:** the active-transmit side of this project is still not something I'd call settled — see [Licensing](#licensing) for where that actually stands right now, including real pushback the reasoning has gotten. Software-side, this now supports two independent radar timing modes (pulsed and FMCW — see [SDR Hardware](#sdr-hardware)), chosen automatically based on connected hardware. **I have not gotten a licensed authority to sign off on either transmit scheme.** Receive-only operation and the simulation mode remain the zero-risk way to run this today.

---

## What It Looks Like Running

Live PPI radar display served as a web page, accessible on any device on your local network. Offline Indiana county and road map overlay. Alert feed with tiered severity and multi-sweep confirmation. GPS position tracking with manual fallback. Transit mode that locks the dish forward while driving and resumes full sweeps when stopped. Multi-sweep storm cell tracking with a projected cone of uncertainty, similar in spirit to how NHC draws a hurricane track cone, but derived live from this radar's own recent heading consistency.

[![Live at radar.koakno.com](https://img.shields.io/badge/Live%20Demo-radar.koakno.com-00FFFF?style=flat-square)](https://radar.koakno.com)

### Try It Without Any Hardware

The repo includes `portable_radar_simulator.html` — a fully self-contained, single-file browser demo. No Flask server, no Python, no hardware. It runs the same alert-escalation logic and storm-track/cone-of-uncertainty math as the real backend, driving two synthetic drifting storm cells across the scope so you can see the whole system (INFO → CAUTION → WARNING → DANGER, transit mode, the tracking cone) work end to end. Just open the file in a browser. This is the easiest way to evaluate the project before building any hardware.

The full Python stack does the same thing automatically if it doesn't find an SDR — everything degrades to a live simulation rather than crashing, so you can run and test the whole software stack (alerts, tracking, the web UI) with zero RF hardware at all.

---

## How It Works

### Theory of Operation

The Winegard Carryout Anser GM-5000 is an automatic RV satellite dome — a motorized prime focus parabolic dish in a weatherproof radome, originally designed to find and track TV satellites. The idea is to repurpose it as a scanning X-band radar antenna.

The Eagle Aspen LNB inside operates at 11250 MHz local oscillator frequency. Injecting a signal at **850 MHz** into the LNB's IF port causes it to upconvert and radiate at **10.4 GHz** through the dish — the same X-band frequency range used by weather radar. Rain, hail, and debris reflect a portion of that energy back, and the LNB downconverts the echo back to 850 MHz for the SDR to capture.

```
TX injection frequency math:
  LNB LO (11250 MHz) - Target (10400 MHz) = 850 MHz
  Inject 850 MHz -> dish radiates 10.4 GHz
```

### Two Radar Timing Modes, Chosen Automatically By Your Hardware

This isn't a setting you pick. `sdr.py` tries to connect to a Pluto/AD9363 board first, then a HackRF, and whichever one it finds determines the timing model — because the two boards are physically different in a way that makes one mode correct for each:

- **HackRF (half-duplex)** — one shared RF front end, physically cannot transmit and receive at the same instant. The software uses **pulsed** timing: transmit a short pulse, stop, listen for the return, repeat. This is the only mode that makes sense on this hardware.
- **Pluto/AD9363 (full-duplex)** — independent TX and RX chains, genuinely can transmit and receive simultaneously. The software runs a continuous **FMCW** chirp and dechirps the return in software (`build_fmcw_chirp` / `dechirp_range_profile` in `sdr.py`).

If neither board is found, everything falls back to simulation mode. There's no menu, no config flag to flip — `RadarSDR.connect()` figures out what's plugged in and every other method (`transmit_pulse`, `transmit_morse_id`, `get_range_profile`) branches on `self.backend` from there. One codebase, hardware picks the mode.

### Signal Chain (as designed)

```
SDR TX port (850 MHz)
    -> F-to-SMA adapter
        -> MAIN F port on dome
            -> LNB upconverts to 10.4 GHz
                -> dish radiates into sky
                    -> rain/hail/debris returns echo
                -> dish captures echo
            -> LNB downconverts to 850 MHz
        -> SEC F port (dedicated receive path)
    -> SDR RX port
```

The **MAIN** port handles TX injection. The **SEC** port (second LNB output, active simultaneously) provides a clean dedicated receive path. A bias tee on the SEC coax powers the LNB. No shared TX/RX path on the dish side, no switching, no backfeed concern — that isolation is a property of the LNB's two physical outputs, independent of which SDR/timing mode you're running.

---

## Hardware

### The Dome

**Winegard Carryout Anser GM-5000**

| Spec | Value |
|---|---|
| Dish type | Prime focus parabolic, polished aluminum |
| Dish diameter | ~18-22 inches |
| Gain at 10 GHz | ~32-33 dBi |
| Beamwidth | ~4-5 degrees |
| Azimuth | Belt driven motor |
| Elevation | Manual set and lock |
| Wind rating | 35 mph maximum |
| Weight | ~16 lbs |
| Includes | 25 ft power cable, 20 ft RG6 coax |

**LNB: Eagle Aspen 501353**

| Spec | Value |
|---|---|
| Input band | 12.2-12.7 GHz |
| LO frequency | 11250 MHz |
| IF output | 950-1450 MHz |
| Outputs | MAIN + SEC (simultaneous) |
| LNB bias power | External, supplied via coax |

**Motor Control Port**

The dome has a thin plastic knockout panel on the base housing. Pop it out with a flathead screwdriver — it's factory-designed to be removed, same idea as the score-line insert between a milk jug handle and body. The RJ-25 RS-485 control jack is immediately behind it.

```
RJ-25 pinout (pin side up, cable end toward you):
  Pin 1: GND
  Pin 2: T/R-
  Pin 3: T/R+
  Pin 4: RXD-
  Pin 5: RXD+
  Pin 6: Not connected

Baud rate: 57600, 8N1
```

---

## SDR Hardware

**Both HackRF One and Pluto/AD9363 (Zynq7020, libiio/pyadi-iio) are supported, auto-detected in that order at startup.** See [Two Radar Timing Modes](#two-radar-timing-modes-chosen-automatically-by-your-hardware) above for why each board gets a different timing model rather than a shared one.

- **HackRF One**, via SoapySDR — the more common/cheaper entry point, pulsed mode.
- **Pluto/AD9363**, via libiio — full-duplex, continuous FMCW mode. Also works cleanly from Android/Termux over Ethernet without USB permission headaches. The Pluto backend is newer and less field-tested than the HackRF path — treat it as needing real-hardware verification before you trust it (see the `UNVERIFIED AGAINST REAL HARDWARE` notes in `sdr.py`).

If no SDR is detected at all (or you just want to evaluate the software), everything falls back to simulation mode automatically — synthetic storm cells that drift and behave like the standalone HTML demo above, so the rest of the stack (alerts, tracking, display) is fully testable without any RF hardware.

### HackRF One Port Clarification

The HackRF has two SMA connectors, and people commonly misidentify them:

- **ANT** — the radar RF connection. Handles both TX and RX internally.
- **CLKOUT** — a 10 MHz reference clock output only. Not an RF signal port.

---

## Shopping List

### Essential

| Item | Notes | Price |
|---|---|---|
| Winegard Carryout Anser GM-5000 | Salvage yards, RV surplus, Facebook Marketplace | $5-40 |
| HackRF One **or** Pluto/AD9363 (Zynq7020) | Either is supported and auto-detected; see [SDR Hardware](#sdr-hardware) for which mode you get | ~$300 / varies |
| F-to-SMA adapters (x2) | Female F to Male SMA | ~$10 |
| DTECH RS232-to-RS485 converter | Specifically DTECH brand | ~$12 |
| RJ-25 6-pin phone cord | Must be 6-conductor, NOT standard RJ-11 | ~$5 |
| USB-to-Serial cable | Any brand | ~$10 |
| Torx screwdriver set | T10, T15 for inner dome | ~$8 |

### Recommended

| Item | Notes | Price |
|---|---|---|
| RTL-SDR V4 | Passive RX-only monitoring; built-in bias tee for the LNB | ~$35 |
| 10 dB SMA attenuator | Inline on TX path (once TX is legally sorted), protects SDR from close-range reflections | ~$5 |

### Bias Tee (choose one)

**Option A -- RTL-SDR V4:** Connect to SEC port, enable bias tee in software. Powers the LNB automatically.

**Option B -- Internal build:** Solder a 100uH inductor and 100pF capacitor inline at the LNB coax junction inside the dome. A couple dollars in parts, permanently integrated.

**Option C -- External:** RTL-SDR brand bias tee inline on the SEC coax. ~$12.

---

## Software Stack

### Architecture (what's actually in this repo)

```
portable_radar/
|-- run.py                        Entry point, elevation prompt, launches stack
|-- config.py                     All settings in one place
|-- app.py                        Flask web server, /api/telemetry endpoint
|-- radar_scanner.py              Main scan loop thread, alerts, storm tracking
|-- motor.py                      RS-485 motor control, paced sweep, position verify
|-- sdr.py                        HackRF (pulsed) + Pluto (FMCW) backends, auto-detected, + simulation fallback
|-- gps.py                        NMEA GPS parser (with checksum validation), speed detection, transit mode
|-- simplify_maps.py              One-time GeoJSON optimization (run once before first use)
|-- portable_radar_simulator.html No-hardware standalone browser demo (see above)
|-- static/
|   |-- indiana_counties.geojson
|   `-- indiana_roads.geojson
`-- templates/
    `-- index.html                Live radar PPI display
```

Session recording/replay and a LoRa alert bridge were planned but got sidestepped for now — they're not part of the current stack. This list reflects what's actually here, not a roadmap.

### Installation (Linux/Ubuntu/Debian)

```bash
# System dependencies
sudo apt install python3-pip python3-numpy \
     soapysdr-tools soapysdr-module-hackrf

# Python dependencies
pip install flask pyserial
# If you're running the Pluto/FMCW path, also:
pip install pyadi-iio

# Clone this repo
git clone https://github.com/Koakno/Small-portable-weather-radar-Dome
cd Small-portable-weather-radar-Dome/portable_radar

# Optimize map files (run once before first use)
python3 simplify_maps.py

# Run
python3 run.py
```

### Installation (Termux / Android)

```bash
pkg install python python-numpy
pip install --break-system-packages pyserial flask
python3 run.py
```

Confirmed working in Termux without any hardware attached (SDR/motor/GPS all gracefully fall back to simulation/manual mode). Note: if you're replacing an older copy of the project folder in Termux, make sure it's actually deleted and not just moved to your file manager's recycle bin — Termux can end up still seeing stale files otherwise.

### Configuration

Edit `config.py` before running. These are the real constant names as they exist in the code:

```python
SERIAL_PORT = "/dev/ttyUSB0"   # RS-485 adapter port
GPS_PORT    = "/dev/ttyACM0"   # GPS device port
MANUAL_LAT  = 40.4864          # Fallback if no GPS
MANUAL_LON  = -86.1336

TARGET_SWEEP_SECONDS         = 20.0   # Set to your motor's real full-360 rotation time
MOVEMENT_SPEED_THRESHOLD_MPH = 2.0    # Above this, dish locks forward (transit mode)

PLUTO_URI = "ip:192.168.2.1"          # Only used if a Pluto is what gets detected
```

### Running

```bash
python3 run.py
```

On startup you'll be prompted for the current dish elevation (this dome has no elevation motor, so it's always manual):

```
  Elevation Configuration
  ========================
  Elevation motor: NOT DETECTED (manual mode)

  Enter current dish elevation (degrees):
    5 deg  - shallow, best long range storm detection
   15 deg  - moderate, good general use
   30 deg  - steep, useful close to a storm

  Elevation > 10
  [OK] Fixed elevation: 10 deg
       Azimuth correction: -4.0 deg applied to all returns
```

The software applies an automatic azimuth correction to compensate for the offset dish geometry coupling elevation into azimuth. It will also print which SDR backend it found (Pluto/HackRF/simulation) — that's the only indication of which radar timing mode you're running, there's nothing to configure. Open your browser to `http://localhost:5000`.

---

## Features

### Live Radar Display

- Canvas-based PPI (Plan Position Indicator) radar scope
- Standard NWS-style reflectivity color scale (cyan -> green -> yellow -> orange -> red -> magenta)
- Offline Indiana county boundaries and road overlay (no internet required), culled to the visible viewport by full geometry bounding box, not a single test vertex
- Real-time sweep line animation
- Telemetry polled every 200ms

### Alert System

Tiered alert feed, generated once per full sweep. Every tier except TRACK requires the same alert type to qualify on **2 consecutive sweeps** before it's surfaced, and won't re-fire for **30 seconds** after it last did — this cuts down single-sweep noise spikes from painting the alert feed with flickering false positives.

| Tier | Trigger |
|---|---|
| INFO | Any precipitation detected |
| CAUTION | Storm core in range |
| WARNING | Supercell-scale signature (high density of strong returns) |
| DANGER | Extreme-strength return within 5 km |
| TRACK | Multi-sweep storm heading/speed, with a widening cone of uncertainty (informational, not debounced — this reflects current motion, not a threshold event) |

### Transit Mode

GPS speed is monitored continuously. Above `MOVEMENT_SPEED_THRESHOLD_MPH` (default 2 mph):

- Dish locks to a fixed forward azimuth
- Full sweep suspended
- Forward-looking returns still captured and displayed
- Mode indicator on the web display switches to `TRANSIT`

Below threshold, full azimuth sweeps resume automatically, alternating direction each sweep (0->360, then 360->0) so the dish is scanning continuously instead of idling while it slews back to a fixed start position.

### Storm Track / Cone of Uncertainty

Tracks the centroid of the strongest return cluster across sweeps, derives a heading and speed, and projects it forward 5/10/15/20 minutes as a widening cone drawn directly on the PPI display. The cone width is driven by how consistent the storm's recent heading has actually been — a steady bearing narrows it, a wobbling one widens it — rather than a fixed value.

---

## Detection Range — Set Your Expectations Honestly

`config.MAX_RANGE_KM` is set to a conservative **20 km** default. Earlier project descriptions (and some early coverage) floated 40-60 km figures — those assumed close to ideal free-space propagation to a strong reflector, and don't hold up as well at ground level once you account for Earth curvature and terrain/foliage clutter cutting into the effective radar horizon, the stock Eagle Aspen LNB's noise figure and gain, and how low in the atmosphere the precipitation you actually care about tends to sit versus your beam elevation.

20 km is a deliberately conservative starting point, not a hard physical ceiling in either direction. A higher-gain LNB or an added amplifier stage will genuinely extend real detection range — if you tune your setup and get more (or less), change `MAX_RANGE_KM` to match what you're actually seeing rather than trusting a marketing-style number.

---

## Deployment

### North Alignment

Azimuth 0 on the dome corresponds to approximately North, assuming the dish is mounted facing the front of the vehicle. Align your vehicle to North before deploying using a compass app on your phone — a built-in vehicle compass typically only indicates the nearest 45-degree cardinal direction, which isn't precise enough at this beamwidth.

### Elevation and Azimuth Coupling

The Carryout Anser's offset dish geometry means changing elevation also shifts the effective beam azimuth. The software compensates automatically — enter your current elevation at startup and the azimuth correction is applied to every logged return. Default coupling coefficient is 0.4 degrees of azimuth correction per degree of elevation.

### Vehicle Mounting

The dome mounts to a roof rack via its standard base. Orient so the MAIN/SEC F connectors face rearward — this places the motor's natural 0 degree position toward the front of the vehicle. Set elevation before mounting using the degree markings on the dome base. Stow the dome (lay flat) when driving at highway speed — it's rated for 35 mph maximum wind loading.

### Field Deployment Checklist

1. Park, orient vehicle North using a compass app
2. Set dish elevation using base markings, lock in place
3. Connect power, coax (MAIN and SEC), RS-485 (RJ-25)
4. Run `python3 run.py`, enter elevation when prompted
5. Open a browser to `localhost:5000`
6. Monitor the PPI display and alert feed

---

## Licensing

**Read this section before building the TX side of this project. None of this is legal advice — I'm not an attorney, and this is genuinely unresolved. Verify independently before you transmit.**

Transmitting on the 3 cm amateur band (10.0-10.5 GHz) requires a Technician class amateur radio license at minimum. Holding a license is not the whole story, though — **the emission type matters.**

Per 47 CFR 97.305(c)(6)(ii), the 3 cm band authorizes: MCW, phone, image, RTTY, data, SS (spread spectrum), and test emissions. Plain pulse is not on that list for this band — compare that to the neighboring 5 cm and 1.2 cm bands, which do explicitly authorize pulse. That's the reason the original as-documented pulsed design isn't something to just key up and transmit.

Two directions are on the table right now, and I haven't committed to either one — both need real scrutiny before they're anything more than a hypothesis:

**FMCW / chirp (the `sdr.py` Pluto backend).** A swept-frequency chirp plausibly reads as SS (spread spectrum) or data, both explicitly authorized on this band. This is the more conventional-looking path of the two, and it's what the Pluto backend implements — but "plausibly reads as" isn't the same as confirmed.

**A pulsed transmission where the pulse itself is the Morse-coded station callsign (the HackRF backend's direction).** The idea: §97.3(a)(9) defines a beacon as a station transmitting for the purpose of observation of propagation and reception or other related experimental activities, and §97.203(d) permits automatically-controlled beacon operation on bands shorter than 33 cm, which 10.4 GHz qualifies for. Precipitation backscatter is a propagation phenomenon, so the argument is that framing the transmission as a beacon studying backscatter — rather than as a radiolocation service — is a real category that exists in amateur radio, structurally similar to how meteor-scatter forward-scatter work already operates.

I want to be direct about where this actually stands: when this reasoning has been run past outside technical review, it's gotten real pushback — the counterargument being that wrapping a legally-required Morse ID around a signal whose underlying purpose is still radiolocation doesn't change what the FCC would classify the transmission as. I don't currently know which read is correct, and I'm not going to present the beacon argument as settled just because it's an interesting theory. **I'm not committing to this direction for now.** If you're planning to actually transmit under either scheme, verify your specific waveform and framing with your local club's microwave/EME people, ARRL's Technical/Regulatory staff, or a communications attorney before you key up — don't take my word, or this README's, for it.

Until one of these is actually confirmed:

- **Receive-only operation** (using an RTL-SDR or similar, no TX at all) sidesteps this issue entirely and is a reasonable way to experiment with the signal chain and software today.
- **The simulation mode / standalone HTML demo** requires no transmission and no license at all — it's the safest way to evaluate the software right now.

General ham licensing background, if you're starting from zero:

- 35 question multiple choice exam for Technician class
- ~$15 exam fee
- Study free at [HamStudy.org](https://hamstudy.org)
- Most people pass with 1-2 weeks of casual study
- Also enables APRS position reporting and VHF/UHF voice comms with other chasers

---

## Safety

> This system is for observing severe weather from a safe distance. Never attempt to intercept or approach a tornado. Always maintain a viable escape route. Monitor NWS warnings alongside your own radar data — your radar provides local situational awareness, NWS provides the authoritative forecast and warning.

> The dome is rated to 35 mph wind loading. Stow it when driving at highway speed. Do not operate during hail.

> Do not transmit until you've actually resolved the licensing question above for your specific setup. See [Licensing](#licensing).

---

## Recent Fixes

A round of community testing surfaced several real bugs that are now fixed: azimuth sweep double-sampling the 0°/360° boundary, the DANGER alert threshold not matching its own displayed wording, a motor command reply that could be misread as a failure, a serial read that could stall a full second waiting on a silent controller, GPS fix status that never cleared after a lost fix, missing NMEA checksum validation, a hardcoded range scale baked into five places in the display instead of following `MAX_RANGE_KM`, hardcoded N/W hemisphere labels, map feature culling that tested a single vertex instead of a bounding box, and the SDR connection never being explicitly closed on shutdown. Thanks to everyone who dug into the code and reported these.

---

## Credits

**SaveItForParts** — whose Carryout-Radio-Telescope project reverse engineered the GM-5000 RS-485 motor control protocol and proved the concept of using this dome as an RF imager. This project would not exist without that work.

- [Carryout-Radio-Telescope](https://github.com/saveitforparts/Carryout-Radio-Telescope)
- [Carryout-Rotor](https://github.com/saveitforparts/Carryout-Rotor)
- [YouTube: Winegard Carryout teardown](https://youtu.be/QkvNH-tuAOo)
- [YouTube: Microwave imaging with hacked TV dish](https://youtube.com/watch?v=lVOTZxNCgTM)

---

## Resources

| Resource | Link |
|---|---|
| GNU Radio | gnuradio.org |
| RTL-SDR drivers | rtl-sdr.com |
| HamStudy (license exam) | hamstudy.org |
| NWS Indianapolis SKYWARN | weather.gov/ind/skywarn |
| Spotter Network | spotternetwork.org |
| 47 CFR Part 97 (amateur radio rules) | ecfr.gov, Title 47, Part 97 |

---

*Built in Kokomo, Indiana -- tornado country. If this helps one person get better warning of an incoming storm it was worth building.*

*This project is hands-on and human-designed -- the hardware repurposing, the RF signal chain, the mounting, all of it came out of nearly getting caught by a tornado NEXRAD didn't catch in time. I used AI assistance to help write, debug, and clean up the software side, and to help write this README. It did not design the hardware or the underlying RF approach. I'm flagging that plainly instead of pretending otherwise, same as I'm flagging the licensing issue above -- I'd rather this be accurate than impressive.*
