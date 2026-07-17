# Small Portable Weather Radar

> A self-contained mobile weather radar system built from a $5 salvaged RV satellite dome, a cheap SDR, and open source software. No internet required. No subscription. No NWS data dependency. Your own radar returns, updated every 10-30 seconds, mounted on your vehicle.

**Built in Kokomo, Indiana. Motivated by real severe weather — including tornadoes that came within a few miles of home.**

---

## Why This Exists

Every storm chaser on the road is looking at NEXRAD data that is 4-6 minutes old, from a radar station that may be 100+ miles away. At close range the NWS beam overshoots low-altitude storm features entirely due to Earth curvature and beam elevation. When a supercell is 10 km away and moving at 40 mph, 6-minute-old data from a distant station is not situational awareness — it is history.

This project generates local radar returns from a vehicle-mounted dish. Updates every 10-30 seconds. Range 3-40 km depending on configuration. Detects rain cores, hail shafts, and tornado debris balls. Costs under $200 to build.

Professional mobile Doppler radar trucks (DOW — Doppler on Wheels) do the same thing. They cost $500,000+. This costs less than a tank of gas.

---

## What It Looks Like Running

Live PPI radar display served as a web page, accessible on any device on your local network or remotely via Cloudflare tunnel. Offline Indiana county and road map overlay. Four-tier auditory alert system. GPS position tracking. Session recording with standalone HTML replay. Transit mode that locks the dish forward while driving and resumes full sweeps when stopped.

[![Live at radar.koakno.com](https://img.shields.io/badge/Live%20Demo-radar.koakno.com-00FFFF?style=flat-square)](https://radar.koakno.com)

---

## How It Works

### Theory of Operation

The Winegard Carryout Anser GM-5000 is an automatic RV satellite dome — a motorized prime focus parabolic dish in a weatherproof radome. It was designed to find and track TV satellites. We repurpose it as a scanning X-band radar antenna.

The Eagle Aspen LNB inside operates at 11250 MHz local oscillator frequency. Injecting a signal at **850 MHz** into the LNB's IF port causes it to upconvert and radiate at **10.4 GHz** through the dish — the same X-band frequency used by weather radar. Rain, hail, and debris reflect a portion of that energy back. The LNB downconverts the echo back to 850 MHz for the SDR to capture.

```
TX injection frequency math:
  LNB LO (11250 MHz) - Target (10400 MHz) = 850 MHz
  Inject 850 MHz → dish radiates 10.4 GHz
```

The azimuth motor sweeps the dish continuously, building a Plan Position Indicator (PPI) image from signal strength at each bearing.

### Signal Chain

```
SDR TX port (850 MHz)
    → F-to-SMA adapter
        → MAIN F port on dome
            → LNB upconverts to 10.4 GHz
                → dish radiates into sky
                    → rain/hail/debris returns echo
                → dish captures echo
            → LNB downconverts to 850 MHz
        → SEC F port (dedicated receive path)
    → SDR RX port
```

The **MAIN** port handles TX injection. The **SEC** port (second LNB output, active simultaneously) provides a clean dedicated receive path. A bias tee on the SEC coax powers the LNB. No shared TX/RX path, no switching, no backfeed concern.

---

## Hardware

### The Dome

**Winegard Carryout Anser GM-5000**

| Spec | Value |
|---|---|
| Dish type | Prime focus parabolic, polished aluminum |
| Dish diameter | ~18-22 inches |
| Gain at 10 GHz | ~32-33 dBi |
| Beamwidth | ~4-5° |
| Azimuth | Belt driven motor, ~360° in 10 seconds |
| Elevation | Manual set and lock |
| Wind rating | 35 mph maximum |
| Weight | ~16 lbs |
| Includes | 25 ft power cable, 20 ft RG6 coax |

**LNB: Eagle Aspen 501353**

| Spec | Value |
|---|---|
| Input band | 12.2–12.7 GHz |
| LO frequency | 11250 MHz |
| IF output | 950–1450 MHz |
| Outputs | MAIN + SEC (simultaneous) |
| LNB bias power | External — supplied via coax |

**Motor Control Port**

The dome has a thin plastic knockout panel on the base housing. Pop it out with a flathead screwdriver — it is factory-designed to be removed (thin score lines in the plastic, identical to the insert between a milk jug handle and body). The RJ-25 RS-485 control jack is immediately behind it.

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

## Supported SDR Hardware

The software supports multiple SDR backends selectable via `config.py`:

| SDR | Type | Config value | Notes |
|---|---|---|---|
| Zynq7020 + AD9363 | 2TX 2RX full duplex | `"pluto"` | **Recommended** — separate TX1/RX1 ports, libiio compatible, boots Pluto firmware from SD card |
| ADALM PlutoSDR | Full duplex | `"pluto"` | Official Pluto, same libiio backend |
| HackRF One | Half duplex | `"hackrf"` | Single ANT port handles TX and RX, switches ~1-2µs |
| RTL-SDR V4 | **Receive only** | `"rtlsdr"` | No TX capability — passive monitoring only. Built-in bias tee powers LNB via coax. |
| None | Simulation | `"simulate"` | Full software simulation, no hardware required |

### Zynq7020 + AD9363 Wiring (Recommended)

```
TX1 port → F-to-SMA → MAIN F port (TX injection, no bias tee)
RX1 port → F-to-SMA → SEC F port  (receive, bias tee here powers LNB)
```

Connect the Zynq board's physical Ethernet port to your router. The SDR is accessed via libiio over the network — no USB SDR driver issues, works from any platform including Android.

### HackRF One Port Clarification

The HackRF has two SMA connectors. Many people misidentify them:

- **ANT** — your radar RF connection. Handles both TX and RX internally.
- **CLKOUT** — 10 MHz reference clock output only. Not an RF signal port.

---

## Shopping List

### Essential

| Item | Notes | Price |
|---|---|---|
| Winegard Carryout Anser GM-5000 | Salvage yards, RV surplus, Facebook Marketplace | $5–40 |
| Zynq7020+AD9363 SDR board | eBay, search "Zynq7020 AD9363 SDR", libiio/Pluto compatible | ~$145 |
| F-to-SMA adapters (×2) | Female F to Male SMA | ~$10 |
| DTECH RS232-to-RS485 converter | Specifically DTECH brand | ~$12 |
| RJ-25 6-pin phone cord | Must be 6-conductor, NOT standard RJ-11 | ~$5 |
| USB-to-Serial cable | Any brand | ~$10 |
| Torx screwdriver set | T10, T15 for inner dome | ~$8 |

### Recommended

| Item | Notes | Price |
|---|---|---|
| RTL-SDR V4 | Built-in bias tee powers LNB via SEC port | ~$35 |
| 10 dB SMA attenuator | Inline on TX path, protects SDR from close-range reflections | ~$5 |

### Future Upgrade

| Item | Notes | Price |
|---|---|---|
| 10 GHz Gunn oscillator | eBay "10GHz Gunn oscillator" — replaces reverse-drive method, dramatically extends range | ~$20–60 |

### Bias Tee (choose one)

**Option A — RTL-SDR V4 (recommended):** Connect to SEC port, enable bias tee in software. Powers LNB automatically.

**Option B — Internal build:** Solder a 100µH inductor and 100pF capacitor inline at the LNB coax junction inside the dome. ~$2 in parts, permanently integrated.

**Option C — External:** RTL-SDR brand bias tee inline on the SEC coax. ~$12.

---

## Software Stack

### Architecture

```
portable_radar/
├── run.py              Entry point, elevation prompt, launches stack
├── config.py           All settings in one place
├── app.py              Flask web server, /api/telemetry endpoint
├── radar_scanner.py    Main scan loop thread
├── motor.py            RS-485 motor control, paced sweep, position verify
├── sdr.py              SDR hardware abstraction (HackRF/Pluto/RTL-SDR/Sim)
├── gps.py              NMEA GPS parser, speed detection, transit mode
├── recorder.py         Session recording (run alongside main stack)
├── replay.py           Generates standalone HTML replay from session file
├── simplify_maps.py    One-time GeoJSON optimization (run once before first use)
├── lora_bridge.py      LoRa alert uplink via Heltec V4 (optional)
├── static/
│   ├── indiana_counties.geojson
│   └── indiana_roads.geojson
└── templates/
    └── index.html      Live radar PPI display
```

### Installation (Linux/Ubuntu/Debian)

```bash
# System dependencies
sudo apt install python3-pip python3-numpy rtl-sdr \
     soapysdr-tools soapysdr-module-hackrf gnuradio \
     gqrx-sdr hamlib-utils

# Python dependencies
pip install flask pyserial gpsd-py3

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

# If python3 and numpy version mismatch:
python3.14 run.py  # use whichever version numpy installed for
```

Tested on Samsung Galaxy S10+ via Termux. Knox limits direct USB SDR access — use the Zynq board's physical Ethernet port via WiFi router instead.

### Configuration

Edit `config.py` before running:

```python
SDR_TYPE    = "pluto"         # hackrf / pluto / rtlsdr / simulate
SERIAL_PORT = "/dev/ttyUSB0"  # RS-485 adapter port
GPS_PORT    = "/dev/ttyACM0"  # GPS device port
MANUAL_LAT  = 40.4864         # Fallback if no GPS
MANUAL_LON  = -86.1336

TARGET_SWEEP_SECONDS   = 18   # Full 360° sweep duration (slower = more accurate)
TRANSIT_MODE_SPEED_MPH = 5.0  # Above this, dish locks forward while driving
```

### Running

```bash
python3 run.py
```

On startup you will be prompted for the current dish elevation:

```
  Elevation Configuration
  ========================
  Elevation motor: NOT DETECTED (manual mode)

  Enter current dish elevation (degrees):
    5°  — shallow, best long range storm detection
   15°  — moderate, good general use
   30°  — steep, useful close to a storm

  Elevation > 10
  [OK] Fixed elevation: 10°
       Azimuth correction: -4.0° applied to all returns
```

The software applies an automatic azimuth correction to compensate for the offset dish geometry coupling elevation into azimuth. Open your browser to `http://localhost:5000` or access remotely via your Cloudflare tunnel.

---

## Features

### Live Radar Display

- Canvas-based PPI (Plan Position Indicator) radar scope
- Standard NWS reflectivity color scale (cyan → green → yellow → orange → red → magenta)
- Offline Indiana county boundaries and road overlay (no internet required)
- Real-time sweep line animation at 60fps
- Auto-refresh telemetry every 200ms
- Accessible on any device via local WiFi or Cloudflare tunnel

### Alert System

Four-tier auditory and visual alert system:

| Tier | Name | Trigger | Audio |
|---|---|---|---|
| 1 | INFO | Any precipitation detected | Single chime |
| 2 | CAUTION | Storm core in range | Double chime |
| 3 | WARNING | Supercell characteristics | Triple beep |
| 4 | DANGER | Debris ball / return within 5 km | Rapid alarm |

Alerts require 2 consecutive sweep confirmations before triggering (reduces false positives). 30-second cooldown between repeated same-tier alerts.

### Transit Mode

GPS speed is monitored continuously. Above `TRANSIT_MODE_SPEED_MPH` (default 5 mph):

- Dish locks to azimuth 0 (forward, toward storm while driving)
- Full sweep suspended
- Forward-looking returns still captured and displayed
- Mode indicator on web display changes to orange `TRANSIT`

Below threshold, full azimuth sweeps resume automatically.

### Session Recording and Replay

```bash
# Record a chase session (run in second terminal alongside main stack)
python3 recorder.py

# Generate standalone replay (no server needed)
python3 replay.py sessions/session_2026-06-29_143210.json
```

The replay generates a single self-contained HTML file with all session data embedded. VCR-style controls: play/pause, step, scrub, speed selector (0.5x–5x). Opens automatically in your browser. A CSV export is generated alongside the JSON for sharing with NWS/NOAA or other researchers.

### Heltec V4 GPS + LoRa Bridge (Optional)

The `heltec_gps_lora_bridge.ino` sketch turns a Heltec WiFi LoRa 32 V4 into a bidirectional bridge:

- **GPS uplink:** streams NMEA sentences from an attached GPS module over USB — laptop sees it as a standard USB GPS receiver, no special drivers
- **LoRa downlink:** receives `ALERT:<tier>:<message>` commands from the laptop over the same USB serial line and transmits them over LoRa 915 MHz to any receiver in range
- **OLED display:** shows live coordinates, fix status, satellite count, speed, and transit mode indicator

The V3 board is also supported (different GPIO pins, no dedicated GNSS connector — wire a GPS module to GPIO33/34 instead).

---

## Deployment

### North Alignment

**Important:** Azimuth 0 on the dome corresponds to approximately North, assuming the dish is mounted facing the front of the vehicle. Align your vehicle to North before deploying using a compass app on your phone. Built-in vehicle compasses typically only indicate the nearest 45° cardinal direction — a phone compass app gives actual degree readings and is sufficient for alignment at this beamwidth.

### Elevation and Azimuth Coupling

The Carryout Anser's offset dish geometry means changing elevation also shifts the effective beam azimuth. The software compensates automatically — enter your current elevation at startup and the azimuth correction is applied to every logged return. Default coupling coefficient is 0.4°/degree of elevation (empirically adjustable in `run.py`).

### Vehicle Mounting

The dome mounts to a roof rack via its standard base. Orient so the MAIN/SEC F connectors face rearward — this places the motor's natural 0° position toward the front of the vehicle. Set elevation before mounting (check degree markings on dome base). Stow the dome (lay flat) when driving at highway speed — rated 35 mph maximum wind loading.

### Field Deployment Checklist

1. Park, orient vehicle North using compass app
2. Set dish elevation using base markings, lock in place
3. Connect power (2-pin connector), coax (MAIN and SEC), RS-485 (RJ-25)
4. Run `python3 run.py`, enter elevation when prompted
5. Open browser to `localhost:5000` or `radar.koakno.com`
6. Monitor PPI display — alerts will sound if storm signatures detected

---

## Expected Performance

### Detection Range

| Target | Reverse-drive LNB (~1-5mW) | With Gunn oscillator TX (~4W) |
|---|---|---|
| Heavy downpour | 3–8 km | 15–40 km |
| Supercell hail core | 8–15 km | 30–60 km |
| Tornado debris ball | 10–20 km | 20–40 km |
| Moderate rain | 1–3 km | 5–15 km |

### Scan Performance

| Mode | Time |
|---|---|
| Full 360° sweep | ~18 seconds (paced for accuracy) |
| 90° sector scan | ~4.5 seconds |
| NEXRAD comparison | Updates every 4–6 minutes |

Sweep timing is deliberately paced slower than the motor's mechanical maximum (~10 seconds) to allow position verification at each step, ensuring logged returns correspond to confirmed dish positions rather than commanded positions.

---

## Licensing

Transmitting at 10.4 GHz requires a minimum **Technician class amateur radio license** in the US. The 3cm band (10.0–10.5 GHz) is an amateur allocation.

- 35 question multiple choice exam
- ~$15 exam fee
- Study free at [HamStudy.org](https://hamstudy.org)
- Most people pass with 1–2 weeks of casual study
- Also enables APRS position reporting and VHF/UHF voice comms with other chasers

---

## Safety

> ⚠️ This system is for observing severe weather from a safe distance. Never attempt to intercept or approach a tornado. Always maintain a viable escape route. Monitor NWS warnings alongside your own radar data. Your radar provides local situational awareness — NWS provides the authoritative forecast and warning.

> ⚠️ The dome is rated to 35 mph wind loading. Stow it when driving at highway speed. Do not operate during hail.

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

---

## Version History

| Version | Date | Notes |
|---|---|---|
| v1.0 | 2026-06-22 | Initial hardware confirmation and signal chain documentation |
| v2.0 | 2026-07-05 | Full modular software stack, Flask web interface, offline Indiana map, alert system, GPS integration, session recording, replay system, LoRa bridge, transit mode, elevation correction, Termux compatibility confirmed |

---

*Built in Kokomo, Indiana — tornado country. If this helps one person get better warning of an incoming storm it was worth building.*
