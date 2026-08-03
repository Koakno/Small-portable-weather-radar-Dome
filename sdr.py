#!/usr/bin/env python3
import numpy as np
import math
import time
import config

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_TX, SOAPY_SDR_RX, SOAPY_SDR_CF32
    HACKRF_AVAILABLE = True
except ImportError:
    HACKRF_AVAILABLE = False

try:
    import adi   # pyadi-iio -- Analog Devices' library for Pluto/AD936x boards
    PLUTO_AVAILABLE = True
except ImportError:
    PLUTO_AVAILABLE = False

C = 3e8  # speed of light, m/s

MORSE_CODE = {
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',   'E': '.',
    'F': '..-.',  'G': '--.',   'H': '....',  'I': '..',    'J': '.---',
    'K': '-.-',   'L': '.-..',  'M': '--',    'N': '-.',    'O': '---',
    'P': '.--.',  'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',  'Y': '-.--',
    'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    '/': '-..-.'
}


def morse_timing_ms(callsign, wpm=18):
    """
    Encodes a call sign into CW keying timing using standard PARIS-word
    timing (1 dit = 1200/wpm ms). Returns a list of (key_on, key_off) ms
    pairs in transmission order -- caller keys the carrier on for
    key_on, off for key_off, repeated through the list.
    """
    dit = 1200.0 / wpm
    dah = dit * 3
    intra_char_gap = dit       # gap between dits/dahs in one character
    inter_char_gap = dit * 3   # gap between characters
    word_gap = dit * 7         # gap between words (not used, callsigns are one token)

    timing = []
    callsign = callsign.upper().strip()
    for i, ch in enumerate(callsign):
        code = MORSE_CODE.get(ch)
        if not code:
            continue
        for j, symbol in enumerate(code):
            key_on = dit if symbol == '.' else dah
            # gap after this element: intra-char, unless it's the last
            # element of the character, in which case the inter-char gap
            # gets added after the loop below
            is_last_symbol = (j == len(code) - 1)
            key_off = inter_char_gap if is_last_symbol else intra_char_gap
            timing.append((key_on, key_off))
    return timing


def build_fmcw_chirp(bandwidth_hz, duration_s, sample_rate_hz):
    """
    Linear FM chirp, baseband complex IQ, sweeping -bw/2 to +bw/2 over
    duration_s. Returns (iq_samples, chirp_rate_hz_per_s).
    Verified against synthetic delayed echoes at known ranges before
    this ever touches real hardware -- see the design notes.
    """
    n = int(sample_rate_hz * duration_s)
    t = np.arange(n) / sample_rate_hz
    chirp_rate = bandwidth_hz / duration_s   # Hz/s
    phase = 2 * np.pi * (-bandwidth_hz / 2 * t + 0.5 * chirp_rate * t**2)
    return np.exp(1j * phase).astype(np.complex64), chirp_rate


def dechirp_range_profile(tx_chirp, rx_samples, chirp_rate_hz_per_s, sample_rate_hz, max_range_km):
    """
    Software stretch processing (deramping): mix RX against the complex
    conjugate of the known TX reference, then FFT. Each FFT bin maps
    directly to a range. This is the software equivalent of the analog
    mixer a hardware FMCW radar would normally use for this step.

    NOTE on sign: for an up-chirp (frequency rising from -bw/2 to +bw/2)
    a positive round-trip delay produces a NEGATIVE beat frequency, not
    positive -- this tripped up the first version of this function.
    """
    n = min(len(tx_chirp), len(rx_samples))
    mixed = rx_samples[:n] * np.conj(tx_chirp[:n])

    spectrum = np.fft.fft(mixed)
    freqs = np.fft.fftfreq(n, d=1 / sample_rate_hz)

    ranges_m = -freqs * C / (2 * chirp_rate_hz_per_s)

    valid = (ranges_m >= 0) & (ranges_m <= max_range_km * 1000)
    return ranges_m[valid] / 1000.0, np.abs(spectrum[valid])   # (range_km array, strength array)


class RadarSDR:
    def __init__(self):
        self.sdr = None
        self.tx_stream = None
        self.rx_stream = None
        self.connected = False
        self.sample_rate = 2e6  
        self.pulse = None
        self.backend = None   # "pluto", "hackrf", or None (simulation)

        # FMCW state, only used when backend == "pluto"
        self._tx_chirp = None
        self._chirp_rate = None

        # fake storm cells for when there's no real SDR -- tracked as
        # x/y km around the radar so they can drift instead of just
        # painting the same ring every azimuth
        self._sim_cells = self._make_sim_cells()
        self._sim_last_update = time.time()

    def _make_sim_cells(self):
        def cell(bearing_deg, distance_km, heading_deg, speed_kmh, radius_km, core_strength):
            return {
                "x": distance_km * math.sin(math.radians(bearing_deg)),
                "y": distance_km * math.cos(math.radians(bearing_deg)),
                "heading_deg": heading_deg,
                "speed_kmh": speed_kmh,
                "radius_km": radius_km,
                "core_strength": core_strength
            }
        return [
            cell(bearing_deg=250, distance_km=16, heading_deg=70, speed_kmh=45, radius_km=2.5, core_strength=0.9),
            cell(bearing_deg=230, distance_km=10, heading_deg=75, speed_kmh=40, radius_km=3.0, core_strength=0.55)
        ]

    def _advance_sim_cells(self):
        # moves each cell based on real elapsed time + some heading wobble,
        # respawns anything that's drifted too far out
        now = time.time()
        dt_hr = (now - self._sim_last_update) / 3600.0
        self._sim_last_update = now

        for c in self._sim_cells:
            c["heading_deg"] = (c["heading_deg"] + np.random.uniform(-3, 3)) % 360
            dist_km = c["speed_kmh"] * dt_hr
            c["x"] += dist_km * math.sin(math.radians(c["heading_deg"]))
            c["y"] += dist_km * math.cos(math.radians(c["heading_deg"]))

            rng = math.hypot(c["x"], c["y"])
            if rng > config.MAX_RANGE_KM * 1.8:
                new_bearing = np.random.uniform(0, 360)
                new_dist = np.random.uniform(config.MAX_RANGE_KM * 1.1, config.MAX_RANGE_KM * 1.5)
                c["x"] = new_dist * math.sin(math.radians(new_bearing))
                c["y"] = new_dist * math.cos(math.radians(new_bearing))
                # generally head back toward the site, not straight back out
                c["heading_deg"] = (new_bearing + 180 + np.random.uniform(-30, 30)) % 360

    def connect(self):
        if self._connect_pluto():
            return True
        if self._connect_hackrf():
            return True
        print("[SDR] No SDR found (Pluto or HackRF). Running in simulation mode.")
        return False

    def _connect_pluto(self):
        # UNVERIFIED AGAINST REAL HARDWARE -- pyadi-iio's exact attribute
        # names/behavior can vary by library version. Treat this as a
        # starting point to debug against the real board, not a known-good path.
        if not PLUTO_AVAILABLE:
            return False
        try:
            self.sdr = adi.Pluto(uri=config.PLUTO_URI)

            self.sample_rate = config.FMCW_SAMPLE_RATE_HZ
            self.sdr.sample_rate = int(self.sample_rate)
            self.sdr.tx_rf_bandwidth = int(config.FMCW_CHIRP_BANDWIDTH_HZ)
            self.sdr.rx_rf_bandwidth = int(config.FMCW_CHIRP_BANDWIDTH_HZ)
            self.sdr.tx_lo = int(config.FMCW_TX_INJECT_HZ)
            self.sdr.rx_lo = int(config.FMCW_TX_INJECT_HZ)

            self._tx_chirp, self._chirp_rate = build_fmcw_chirp(
                config.FMCW_CHIRP_BANDWIDTH_HZ,
                config.FMCW_CHIRP_DURATION_S,
                self.sample_rate
            )

            # scale unit-amplitude IQ to the board's expected sample range
            # and start the chirp transmitting continuously in a loop --
            # this replaces pulse-then-listen entirely, TX just runs the
            # whole time the radar is operating
            tx_samples = (self._tx_chirp * 2**14).astype(np.complex64)
            self.sdr.tx_cyclic_buffer = True
            self.sdr.tx(tx_samples)

            self.sdr.rx_buffer_size = len(self._tx_chirp)

            self.connected = True
            self.backend = "pluto"
            print("[SDR] Pluto/AD9363 connected, FMCW chirp transmitting continuously.")
            return True
        except Exception as e:
            print(f"[SDR] Pluto connection failed: {e}")
            self.sdr = None
            return False

    def _connect_hackrf(self):
        if not HACKRF_AVAILABLE:
            return False
        try:
            results = SoapySDR.Device.enumerate("driver=hackrf")
            if not results:
                return False

            self.sample_rate = 2e6
            self.sdr = SoapySDR.Device({"driver": "hackrf"})
            self.sdr.setSampleRate(SOAPY_SDR_TX, 0, self.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_TX, 0, config.TX_FREQUENCY)
            self.sdr.setGain(SOAPY_SDR_TX, 0, config.TX_GAIN)

            self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_RX, 0, config.TX_FREQUENCY)
            self.sdr.setGain(SOAPY_SDR_RX, 0, config.RX_GAIN)

            self.tx_stream = self.sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32)
            self.rx_stream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)

            num_samples = int(self.sample_rate * config.PULSE_DURATION)
            self.pulse = np.ones(num_samples, dtype=np.complex64)
            self.connected = True
            self.backend = "hackrf"
            print("[SDR] HackRF Transceiver cleanly initialized.")
            return True
        except Exception as e:
            print(f"[SDR] HackRF initialization failure: {e}")
            return False

    def transmit_pulse(self):
        # only meaningful for the hackrf pulse-then-listen path -- pluto's
        # chirp is already transmitting continuously from connect() onward,
        # there's no discrete "pulse" step in FMCW
        if self.backend != "hackrf" or not self.connected:
            return
        try:
            self.sdr.activateStream(self.tx_stream)
            self.sdr.writeStream(self.tx_stream, [self.pulse], len(self.pulse))
            self.sdr.deactivateStream(self.tx_stream)
        except Exception:
            pass

    def transmit_morse_id(self, callsign, wpm=18):
        """
        Keys the carrier on/off to CW-transmit the station call sign,
        required by 47 CFR 97.119 at least every 10 min while operating.
        No-op in simulation mode -- just logs what would have gone out.
        """
        timing = morse_timing_ms(callsign, wpm)
        if not timing:
            return

        if not self.connected:
            print(f"[SDR-SIM] Would transmit station ID: {callsign} ({wpm} WPM)")
            return

        if self.backend == "pluto":
            self._transmit_morse_id_pluto(timing, callsign)
        elif self.backend == "hackrf":
            self._transmit_morse_id_hackrf(timing, callsign)

    def _transmit_morse_id_hackrf(self, timing, callsign):
        try:
            self.sdr.activateStream(self.tx_stream)
            for key_on_ms, key_off_ms in timing:
                on_samples = int(self.sample_rate * (key_on_ms / 1000.0))
                carrier = np.ones(on_samples, dtype=np.complex64)
                self.sdr.writeStream(self.tx_stream, [carrier], on_samples)
                time.sleep(key_off_ms / 1000.0)
            self.sdr.deactivateStream(self.tx_stream)
            print(f"[SDR] Station ID transmitted: {callsign}")
        except Exception as e:
            print(f"[SDR] Station ID transmission failed: {e}")

    def _transmit_morse_id_pluto(self, timing, callsign):
        # UNVERIFIED AGAINST REAL HARDWARE. Stops the continuous chirp
        # buffer, keys a plain carrier on/off for the ID, then restarts
        # the chirp. The dish briefly stops ranging during the ID --
        # a few seconds every 10 minutes, an acceptable tradeoff for
        # staying legal.
        try:
            self.sdr.tx_destroy_buffer()
            for key_on_ms, key_off_ms in timing:
                on_samples = int(self.sample_rate * (key_on_ms / 1000.0))
                carrier = (np.ones(on_samples, dtype=np.complex64) * 2**14).astype(np.complex64)
                self.sdr.tx_cyclic_buffer = False
                self.sdr.tx(carrier)
                time.sleep(key_off_ms / 1000.0)

            # resume continuous chirp transmission
            tx_samples = (self._tx_chirp * 2**14).astype(np.complex64)
            self.sdr.tx_cyclic_buffer = True
            self.sdr.tx(tx_samples)
            print(f"[SDR] Station ID transmitted: {callsign}")
        except Exception as e:
            print(f"[SDR] Station ID transmission failed: {e}")

    def get_range_profile(self, azimuth=0.0):
        # Simulation Fallback Matrix
        if not self.connected:
            self._advance_sim_cells()
            ranges = []
            for i in range(config.MAX_RANGE_KM):
                r_km = float(i)
                strength = np.random.random() * 0.04   # background clear-air noise

                for c in self._sim_cells:
                    bearing = math.degrees(math.atan2(c["x"], c["y"])) % 360
                    dist_km = math.hypot(c["x"], c["y"])

                    ang_diff = abs(((azimuth - bearing + 180) % 360) - 180)
                    angular_radius_deg = max(3.0, math.degrees(math.atan2(c["radius_km"], max(dist_km, 0.3))))
                    if ang_diff > angular_radius_deg * 1.4:
                        continue  # this cell isn't in the beam at this azimuth

                    range_diff = abs(r_km - dist_km)
                    if range_diff > c["radius_km"] * 1.3:
                        continue  # this cell isn't at this range bin

                    coverage = 1 - (ang_diff / (angular_radius_deg * 1.4))
                    falloff = max(0.0, 1 - range_diff / (c["radius_km"] * 1.3))
                    contribution = c["core_strength"] * falloff * (0.6 + 0.4 * coverage)
                    strength = max(strength, contribution * (0.85 + np.random.random() * 0.3))

                ranges.append((r_km, min(1.0, strength)))
            return ranges

        if self.backend == "pluto":
            return self._get_range_profile_pluto()
        elif self.backend == "hackrf":
            return self._get_range_profile_hackrf()
        return []

    def _get_range_profile_pluto(self):
        # UNVERIFIED AGAINST REAL HARDWARE -- confirm sdr.rx() actually
        # returns rx_buffer_size samples synced reasonably to the TX
        # chirp cycle on your real board before trusting this output.
        try:
            rx_samples = self.sdr.rx()
            rx_samples = np.asarray(rx_samples, dtype=np.complex64) / 2**14  # undo TX-side scaling

            ranges_km, strength = dechirp_range_profile(
                self._tx_chirp, rx_samples, self._chirp_rate,
                self.sample_rate, config.MAX_RANGE_KM
            )

            # normalize strength to roughly 0-1 like the other backends,
            # scale factor is a guess -- tune once real return levels are known
            norm_strength = np.clip(strength / (np.max(strength) + 1e-9), 0, 1)
            return list(zip(ranges_km.tolist(), norm_strength.tolist()))
        except Exception as e:
            print(f"[SDR] Pluto capture failed: {e}")
            return []

    def _get_range_profile_hackrf(self):
        try:
            max_range_time = (config.MAX_RANGE_KM * 2000) / 3e8
            num_samples = int(self.sample_rate * max_range_time)

            self.sdr.activateStream(self.rx_stream)
            buffer = np.zeros(num_samples, dtype=np.complex64)
            sr = self.sdr.readStream(self.rx_stream, [buffer], num_samples, timeoutUs=1_000_000)
            self.sdr.deactivateStream(self.rx_stream)

            if sr.ret <= 0: return []

            km_per_sample = 3e8 / (2 * self.sample_rate * 1000)
            ranges = []
            bin_size = max(1, int(1.0 / km_per_sample))

            for i in range(0, sr.ret, bin_size):
                bin_samples = buffer[i:i + bin_size]
                if len(bin_samples) == 0: break
                power = float(np.mean(np.abs(bin_samples) ** 2))
                range_km = (i / self.sample_rate) * 3e8 / 2000
                if range_km <= config.MAX_RANGE_KM:
                    ranges.append((range_km, power))
            return ranges
        except Exception:
            return []