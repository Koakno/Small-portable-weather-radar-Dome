#!/usr/bin/env python3
# main scan loop thread. takes elevation config from run.py and applies
# the azimuth correction for the offset dish geometry to every return.

import time
import math
import threading
from collections import deque
import config
from motor import CarryoutMotor
from sdr import RadarSDR
from gps import USBGPSInterface

EARTH_RADIUS_KM = 6371.0
COMPASS_POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                   "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def bearing_distance_km(lat1, lon1, lat2, lon2):
    # great-circle bearing + distance, point1 -> point2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = EARTH_RADIUS_KM * c

    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing_deg = (math.degrees(math.atan2(y, x)) + 360) % 360

    return bearing_deg, distance_km


def project_latlon(lat, lon, bearing_deg, distance_km):
    # dest lat/lon given start point + bearing + distance
    phi1 = math.radians(lat)
    lambda1 = math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_km / EARTH_RADIUS_KM

    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2)
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540) % 360 - 180


def bearing_to_compass(deg):
    idx = int((deg + 11.25) // 22.5) % 16
    return COMPASS_POINTS[idx]


class RadarScanner(threading.Thread):
    def __init__(self, elevation=None, az_correction=0.0, elevation_motor=False):
        super().__init__()
        self.daemon = True
        self.motor = CarryoutMotor(config.SERIAL_PORT, config.SERIAL_BAUD)
        self.sdr   = RadarSDR()
        self.gps   = USBGPSInterface()

        # from run.py's startup prompt
        self.elevation        = elevation         # float degrees or "auto"
        self.az_correction    = az_correction     # degrees subtracted from raw azimuth
        self.elevation_motor  = elevation_motor   # True if elevation motor detected

        self.state = {
            "current_azimuth":       0,
            "sweep_count":           0,
            "returns":               [],
            "system": {
                "sdr":         False,
                "sdr_backend": None,   # "pluto", "hackrf", or None
                "motor":       False,
                "gps":         False
            },
            "location": {
                "lat": config.MANUAL_LAT,
                "lon": config.MANUAL_LON,
                "alt": config.MANUAL_ALT
            },
            "alerts":                [],
            "unconfirmed_positions": 0,
            "speed_mph":             0.0,
            "scan_mode":             "scan",    # "scan" or "transit"

            # storm cell tracking / cone of uncertainty across sweeps
            "storm_track": {
                "heading_deg":        None,
                "compass":            None,
                "speed_kmh":          None,
                "speed_mph":          None,
                "cone_half_angle_deg": None,
                "projection":         []   # [{minutes, az, range, cone_half_angle}, ...]
            },

            "elevation_deg":    elevation if elevation != "auto" else "auto",
            "elevation_mode":   "auto" if elevation == "auto" else "fixed",
            "az_correction":    az_correction,
        }
        self.running = False

        # 1 = ascending (0->360), -1 = descending (360->0), flips after
        # every sweep so it keeps scanning on the way back instead of
        # idling while it re-homes to 0
        self.sweep_direction = 1

        # last 6 storm centroid fixes (timestamp, lat, lon)
        self.cell_history = deque(maxlen=6)

        # required station ID (47 CFR 97.119) -- fires at startup, then
        # every config.STATION_ID_INTERVAL_SEC while actively transmitting
        self.last_id_time = 0.0

    def apply_az_correction(self, raw_azimuth):
        # offset dish geometry couples elevation into azimuth --
        # this backs that out so logged returns are true compass bearing
        if self.az_correction == 0.0:
            return raw_azimuth
        corrected = (raw_azimuth - self.az_correction) % 360
        return round(corrected, 1)

    def normalize_signal(self, raw_power):
        if raw_power <= config.NOISE_FLOOR:
            return 0.0
        norm = (raw_power - config.NOISE_FLOOR) / \
               (config.MAX_EXPECTED_POWER - config.NOISE_FLOOR)
        return min(1.0, max(0.0, norm))

    def update_storm_track(self, strong_returns):
        # tracks the strongest return cluster's centroid across sweeps,
        # derives heading/speed, projects forward 5/10/15/20 min as a
        # cone that widens with how much the heading's been wobbling
        site_lat = self.state["location"]["lat"]
        site_lon = self.state["location"]["lon"]
        if site_lat is None or site_lon is None:
            return

        if len(strong_returns) < 5:
            return  # not enough points to trust a centroid this sweep

        avg_az    = sum(r[0] for r in strong_returns) / len(strong_returns)
        avg_range = sum(r[1] for r in strong_returns) / len(strong_returns)

        # avg_az/avg_range is already bearing+distance from the site
        cell_lat, cell_lon = project_latlon(site_lat, site_lon, avg_az, avg_range)
        self.cell_history.append((time.time(), cell_lat, cell_lon))

        if len(self.cell_history) < 2:
            return

        # oldest-to-newest fix, not just the last two -- one sweep is only
        # ~9s, and dividing a noisy centroid shift by that short a window
        # blows up into bogus speeds (saw 265mph once). spanning the whole
        # history (up to 6 sweeps) averages the noise out
        (t0, lat0, lon0) = self.cell_history[0]
        (t1, lat1, lon1) = self.cell_history[-1]
        dt_hr = (t1 - t0) / 3600.0

        # also don't trust it until at least 30s has actually elapsed
        MIN_TRACK_BASELINE_SEC = 30.0
        if dt_hr <= 0 or (t1 - t0) < MIN_TRACK_BASELINE_SEC:
            return

        heading_deg, leg_distance_km = bearing_distance_km(lat0, lon0, lat1, lon1)
        speed_kmh = leg_distance_km / dt_hr

        # steady heading = tight cone, wobbly heading = wide cone
        hist = list(self.cell_history)
        bearings = [
            bearing_distance_km(hist[i - 1][1], hist[i - 1][2], hist[i][1], hist[i][2])[0]
            for i in range(1, len(hist))
        ]
        if len(bearings) >= 2:
            diffs = [abs((bearings[i] - bearings[i - 1] + 180) % 360 - 180)
                     for i in range(1, len(bearings))]
            heading_wobble = sum(diffs) / len(diffs)
        else:
            heading_wobble = 15.0  # not enough legs yet, assume moderate spread

        base_half_angle = 6.0   # floor, even for a dead-steady heading
        cone_half_angle = min(45.0, base_half_angle + heading_wobble * 1.5)

        projection = []
        for minutes in (5, 10, 15, 20):
            proj_km = speed_kmh * (minutes / 60.0)
            p_lat, p_lon = project_latlon(lat1, lon1, heading_deg, proj_km)
            # back to az/range from the current site so the frontend can
            # plot it straight onto the PPI canvas
            p_az, p_range = bearing_distance_km(site_lat, site_lon, p_lat, p_lon)
            projection.append({
                "minutes":         minutes,
                "az":              round(p_az, 1),
                "range":           round(p_range, 2),
                "cone_half_angle": round(cone_half_angle * (minutes / 20.0), 1)
            })

        self.state["storm_track"] = {
            "heading_deg":         round(heading_deg, 1),
            "compass":             bearing_to_compass(heading_deg),
            "speed_kmh":           round(speed_kmh, 1),
            "speed_mph":           round(speed_kmh * 0.621371, 1),
            "cone_half_angle_deg": round(cone_half_angle, 1),
            "projection":          projection
        }

    def process_alerts(self, returns):
        alerts = []
        strong_returns  = [r for r in returns if r[2] > 0.5]
        extreme_returns = [r for r in returns if r[2] > 0.75]

        # update the track first so the TRACK alert below is current
        self.update_storm_track(strong_returns)
        track = self.state["storm_track"]

        if len(returns) > 10:
            closest = min(returns, key=lambda x: x[1])
            alerts.append({
                "type":  "INFO",
                "msg":   "Precipitation detected",
                "range": f"{closest[1]:.1f} km",
                "az":    f"{closest[0]}°"
            })

        if strong_returns:
            max_r = max(strong_returns, key=lambda x: x[2])
            alerts.append({
                "type":  "CAUTION",
                "msg":   "Storm core in range",
                "range": f"{max_r[1]:.1f} km",
                "az":    f"{max_r[0]}°"
            })

        if len(strong_returns) > 40:
            avg_az    = sum(r[0] for r in strong_returns) / len(strong_returns)
            avg_range = sum(r[1] for r in strong_returns) / len(strong_returns)
            alerts.append({
                "type":  "WARNING",
                "msg":   "Supercell signatures identified",
                "range": f"{avg_range:.1f} km",
                "az":    f"{avg_az:.0f}°"
            })

        if extreme_returns:
            max_ex = max(extreme_returns, key=lambda x: x[2])
            if max_ex[1] < 6.0:
                alerts.append({
                    "type":  "DANGER",
                    "msg":   "Severe cell / Core within 5km zone",
                    "range": f"{max_ex[1]:.1f} km",
                    "az":    f"{max_ex[0]}°"
                })

        if track["heading_deg"] is not None:
            alerts.append({
                "type":  "TRACK",
                "msg":   f"Storm tracking {track['compass']} at {track['speed_mph']} mph "
                         f"(±{track['cone_half_angle_deg']}° cone)",
                "range": f"{track['speed_mph']} mph",
                "az":    f"{track['heading_deg']}°"
            })

        self.state["alerts"] = alerts[::-1]

    def maybe_transmit_id(self):
        # only actually required while transmitting -- skip if hardware
        # isn't connected (nothing radiating) or before first pulse ever
        if not self.state["system"]["sdr"]:
            return
        now = time.time()
        if self.last_id_time == 0.0:
            self.last_id_time = now  # first pulse just went out, start the clock
            return
        if now - self.last_id_time >= config.STATION_ID_INTERVAL_SEC:
            self.sdr.transmit_morse_id(config.CALLSIGN, config.STATION_ID_WPM)
            self.last_id_time = now

    def run(self):
        self.running = True
        self.state["system"]["motor"] = self.motor.connect()
        self.state["system"]["sdr"] = self.sdr.connect()
        self.state["system"]["sdr_backend"] = self.sdr.backend

        gps_connected = self.gps.connect()
        self.state["system"]["gps"] = gps_connected
        if gps_connected:
            self.gps.start()

        if self.state["system"]["motor"]:
            self.motor.home()

        history_buffer = deque(maxlen=360 // config.AZIMUTH_STEP)

        while self.running:
            self.state["location"] = {
                "lat": self.gps.lat,
                "lon": self.gps.lon,
                "alt": self.gps.alt
            }
            self.state["system"]["gps"] = self.gps.connected and self.gps.has_fix
            self.state["speed_mph"] = self.gps.speed_mph

            self.maybe_transmit_id()

            # transit mode -- lock dish forward while moving
            if self.gps.is_moving():
                self.state["scan_mode"] = "transit"

                if self.state["system"]["motor"]:
                    self.motor.move_to_azimuth(
                        config.TRANSIT_MODE_AZIMUTH, verify=True
                    )
                self.state["current_azimuth"] = config.TRANSIT_MODE_AZIMUTH

                self.sdr.transmit_pulse()
                profile = self.sdr.get_range_profile(config.TRANSIT_MODE_AZIMUTH)
                forward_returns = []
                for range_km, raw_power in profile:
                    strength = self.normalize_signal(raw_power)
                    if strength >= config.SIGNAL_THRESHOLD:
                        corrected_az = self.apply_az_correction(
                            config.TRANSIT_MODE_AZIMUTH
                        )
                        forward_returns.append([
                            corrected_az,
                            round(range_km, 2),
                            round(strength, 2)
                        ])
                self.state["returns"] = forward_returns
                self.process_alerts(forward_returns)
                time.sleep(1.0)
                continue

            # scan mode -- full azimuth sweep
            self.state["scan_mode"] = "scan"
            unconfirmed_count = 0

            # alternate direction each sweep so it's always scanning,
            # never idling on a return slew
            if self.sweep_direction == 1:
                sweep_start, sweep_end, step = config.SCAN_START_DEG, config.SCAN_END_DEG, config.AZIMUTH_STEP
            else:
                sweep_start, sweep_end, step = config.SCAN_END_DEG, config.SCAN_START_DEG, -config.AZIMUTH_STEP

            if self.state["system"]["motor"]:
                sweep_iter = self.motor.paced_sweep(
                    sweep_start,
                    sweep_end,
                    step
                )
            else:
                def _simulated_sweep():
                    az = sweep_start
                    going_up = step > 0
                    while (going_up and az <= sweep_end) or (not going_up and az >= sweep_end):
                        time.sleep(config.DWELL_TIME)
                        yield (az, True)
                        az += step
                sweep_iter = _simulated_sweep()

            for azimuth, confirmed in sweep_iter:
                if not self.running:
                    break

                if self.gps.is_moving():
                    break

                # true compass bearing, not raw motor position
                corrected_az = self.apply_az_correction(azimuth)
                self.state["current_azimuth"] = corrected_az

                if not confirmed:
                    unconfirmed_count += 1

                self.sdr.transmit_pulse()
                profile = self.sdr.get_range_profile(azimuth)

                history_buffer = deque(
                    [r for r in history_buffer if r[0] != corrected_az]
                )

                for range_km, raw_power in profile:
                    strength = self.normalize_signal(raw_power)
                    if strength >= config.SIGNAL_THRESHOLD:
                        history_buffer.append([
                            corrected_az,
                            round(range_km, 2),
                            round(strength, 2)
                        ])

                self.state["returns"] = list(history_buffer)

            self.state["sweep_count"] += 1
            self.sweep_direction *= -1
            self.state["unconfirmed_positions"] = unconfirmed_count
            if unconfirmed_count > 0:
                print(f"[Scanner] Sweep {self.state['sweep_count']}: "
                      f"{unconfirmed_count} position(s) did not confirm -- "
                      f"dish may not be keeping pace with the sweep, try "
                      f"raising TARGET_SWEEP_SECONDS in config.py or "
                      f"loosening confirm_timeout in motor.py's paced_sweep()")
            self.process_alerts(self.state["returns"])

        self.gps.stop()
        self.motor.disconnect()
