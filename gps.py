#!/usr/bin/env python3
import threading
import time
import serial
import config

class USBGPSInterface(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.lat = config.MANUAL_LAT
        self.lon = config.MANUAL_LON
        self.alt = config.MANUAL_ALT
        self.speed_mph = 0.0
        self.course_deg = 0.0
        self.connected = False
        self.has_fix = False
        self.running = False
        self.ser = None

    def connect(self):
        if not config.USE_GPS or not config.GPS_PORT:
            print("[GPS] GPS functionality bypassed via config. Using fallback locations.")
            return False
        try:
            self.ser = serial.Serial(
                port=config.GPS_PORT,
                baudrate=config.GPS_BAUD,
                timeout=1.0
            )
            self.connected = True
            print(f"[GPS] Native connection achieved on {config.GPS_PORT}")
            return True
        except Exception as e:
            print(f"[GPS] Receiver failed to connect on {config.GPS_PORT}: {e}")
            self.connected = False
            return False

    def _checksum_ok(self, line):
        """
        Validates the NMEA checksum (XOR of all chars between '$' and
        '*', compared against the two hex digits after '*'). Serial
        glitches / mid-sentence corruption drop or flip bytes, which
        would otherwise get parsed into a bogus position -- this
        rejects any sentence that doesn't check out.
        """
        if not line.startswith('$') or '*' not in line:
            return False
        body, _, checksum_hex = line[1:].partition('*')
        if len(checksum_hex) < 2:
            return False
        calc = 0
        for ch in body:
            calc ^= ord(ch)
        try:
            return calc == int(checksum_hex[:2], 16)
        except ValueError:
            return False

    def _convert_nmea_to_decimal(self, value, direction):
        """Converts NMEA raw DDMM.MMMMM representation to signed Decimal Degrees."""
        if not value or not direction:
            return 0.0
        try:
            dot_idx = value.find('.')
            degree_digits = dot_idx - 2
            degrees = float(value[:degree_digits])
            minutes = float(value[degree_digits:])
            
            decimal_degrees = degrees + (minutes / 60.0)
            if direction in ['S', 'W']:
                decimal_degrees = -decimal_degrees
            return decimal_degrees
        except Exception:
            return 0.0

    def run(self):
        self.running = True
        if not self.connected and not self.connect():
            return

        raw_buffer = ""
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
                    raw_buffer += chunk
                    
                    while '\r\n' in raw_buffer:
                        line, raw_buffer = raw_buffer.split('\r\n', 1)
                        line = line.strip()

                        if not line or not self._checksum_ok(line):
                            continue

                        # Process Lat/Lon coordinates
                        if line.startswith(('$GPRMC', '$GNRMC')):
                            elements = line.split(',')
                            if len(elements) > 6 and elements[2] == 'A':
                                self.lat = self._convert_nmea_to_decimal(elements[3], elements[4])
                                self.lon = self._convert_nmea_to_decimal(elements[5], elements[6])
                                self.has_fix = True

                                # Field 7: speed over ground in knots, field 8: course in degrees
                                if len(elements) > 7 and elements[7]:
                                    try:
                                        self.speed_mph = float(elements[7]) * 1.15078
                                    except ValueError:
                                        pass
                                if len(elements) > 8 and elements[8]:
                                    try:
                                        self.course_deg = float(elements[8])
                                    except ValueError:
                                        pass
                            elif len(elements) > 2 and elements[2] == 'V':
                                # 'V' = void/no fix -- don't leave stale
                                # LOCKED status showing on the UI
                                self.has_fix = False

                        # Process Altitude coordinates
                        elif line.startswith(('$GPGGA', '$GNGGA')):
                            elements = line.split(',')
                            if len(elements) > 9 and elements[6] in ['1', '2', '4', '5']:
                                self.lat = self._convert_nmea_to_decimal(elements[2], elements[3])
                                self.lon = self._convert_nmea_to_decimal(elements[4], elements[5])
                                self.has_fix = True
                                try:
                                    self.alt = float(elements[9])
                                except ValueError:
                                    pass
                            elif len(elements) > 6 and elements[6] == '0':
                                # fix quality 0 = invalid
                                self.has_fix = False
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"[GPS] Stream processing disruption: {e}")
                time.sleep(1.0)

    def is_moving(self):
        """
        True when GPS-reported speed exceeds the configured movement
        threshold. Used by radar_scanner.py to switch between stationary
        scan mode and forward-locked transit mode.
        """
        return self.speed_mph > config.MOVEMENT_SPEED_THRESHOLD_MPH

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()