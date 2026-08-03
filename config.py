#!/usr/bin/env python3
import os

# Motor
SERIAL_PORT = "/dev/ttyUSB0"    # RS-485 adapter, adjust if it enumerates elsewhere
SERIAL_BAUD = 57600

# GPS
GPS_PORT = "/dev/ttyACM0"
GPS_BAUD = 9600
USE_GPS = True                  # False = skip GPS, use manual lat/lon below

# SDR
TX_FREQUENCY = 850_000_000
TX_GAIN = 20
RX_GAIN = 30

# Scan
AZIMUTH_STEP = 2

# time for one full 360 rotation, measured with a stopwatch off the real
# motor -- this drives the sim-mode pacing when no motor is connected
TARGET_SWEEP_SECONDS = 20.0
DWELL_TIME = TARGET_SWEEP_SECONDS / (360 / AZIMUTH_STEP)

PULSE_DURATION = 0.000009       # 9us
MAX_RANGE_KM = 20
SCAN_START_DEG = 0
SCAN_END_DEG = 360

# Thresholds
SIGNAL_THRESHOLD = 0.15
NOISE_FLOOR = 0.001
MAX_EXPECTED_POWER = 1.0

# Manual location fallback if GPS is off / no fix
MANUAL_LAT = 40.4864
MANUAL_LON = -86.1336
MANUAL_ALT = 248

# mph threshold before it counts as "moving" -> transit mode.
# above idle GPS jitter so it doesn't flip modes while parked
MOVEMENT_SPEED_THRESHOLD_MPH = 2.0

# azimuth the dish locks to in transit mode -- depends on how it's
# actually mounted on the vehicle, 0 = facing straight forward
TRANSIT_MODE_AZIMUTH = 0

# Station identification (47 CFR 97.119 -- required while transmitting)
CALLSIGN = "N0CALL"             # set to your actual assigned call sign
STATION_ID_INTERVAL_SEC = 600   # max 10 min between IDs while transmitting
STATION_ID_WPM = 18             # CW speed, must not exceed 20 WPM (97.119(b)(1))

# FMCW (Pluto/AD9363 full-duplex mode -- alternative to the pulsed HackRF path)
LNB_LO_HZ = 11_250_000_000       # LNB local oscillator, fixed by the hardware
FMCW_TARGET_FREQ_HZ = 10_250_000_000   # radiated center freq, mid-band of the legal 10.0-10.5GHz allocation
FMCW_TX_INJECT_HZ = LNB_LO_HZ - FMCW_TARGET_FREQ_HZ   # what actually gets sent into the LNB

FMCW_CHIRP_BANDWIDTH_HZ = 10_000_000   # <= ~20MHz, the AD9363's real RF bandwidth ceiling
FMCW_SAMPLE_RATE_HZ     = 15_000_000   # must exceed bandwidth; verify actual sustained rate on real hardware
FMCW_CHIRP_DURATION_S   = 0.001        # 1ms, ~7.5x margin over the 133us round trip to MAX_RANGE_KM
FMCW_CHIRPS_PER_BURST   = 32           # for Doppler processing later, unused by range-only mode
PLUTO_URI = "ip:192.168.2.1"           # default Pluto/Zynq network address, change to match your setup

# Web server
WEB_HOST = "0.0.0.0"            # needed for cloudflare tunnel / LAN access
WEB_PORT = 5000
