#!/usr/bin/env python3
import time
import struct
import threading
import serial
import config

class CarryoutMotor:
    CMD_MOVE_AZ   = 0x50
    CMD_STOP      = 0x51
    CMD_GET_POS   = 0x52
    CMD_HOME      = 0x53

    def __init__(self, port=None, baud=None):
        self.port = port or config.SERIAL_PORT
        self.baud = baud or config.SERIAL_BAUD
        self.ser = None
        self.current_azimuth = 0.0
        self.connected = False
        self._lock = threading.Lock()

    def connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port, baudrate=self.baud,
                bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, timeout=1.0
            )
            self.connected = True
            print(f"[Motor] Serial connection established on {self.port}")
            return True
        except Exception as e:
            print(f"[Motor] Failed to connect on {self.port}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.stop()
            self.ser.close()
        self.connected = False

    def _send_command(self, cmd, data=None, reply_timeout=0.05):
        """
        Returns the raw reply bytes on a successful write (which may be
        b'' if the controller acked with zero payload -- that is NOT a
        failure), or None only if the write itself failed / we aren't
        connected. Callers must check `is None`, not truthiness, to
        tell a real failure from an empty-but-valid reply.

        Polls for up to reply_timeout instead of blocking on
        ser.read()'s full connection-level timeout, so a controller
        that never answers only stalls this step by ~reply_timeout
        (default 50ms) instead of the full 1s serial timeout.
        """
        if not self.connected or not self.ser:
            return None
        with self._lock:
            try:
                packet = bytearray([0xFF, 0xFF, cmd])
                if data:
                    packet.extend(data)
                checksum = sum(packet[2:]) & 0xFF
                packet.append(checksum)
                self.ser.write(packet)

                deadline = time.time() + reply_timeout
                while time.time() < deadline and self.ser.in_waiting == 0:
                    time.sleep(0.005)

                if self.ser.in_waiting:
                    return self.ser.read(self.ser.in_waiting)
                return b''
            except Exception as e:
                print(f"[Motor] Serial transmission failure: {e}")
                return None

    def get_position(self):
        """
        Query the controller's actual azimuth position via CMD_GET_POS.
        Returns degrees (float) or None if the read failed/was too short
        to contain a position.
        """
        response = self._send_command(self.CMD_GET_POS)
        if not response or len(response) < 4:
            return None
        try:
            raw_pos = struct.unpack(">H", response[2:4])[0]
            return raw_pos / 10.0
        except struct.error:
            return None

    def move_to_azimuth(self, degrees, verify=False, confirm_tolerance_deg=1.5, confirm_timeout=0.5):
        degrees = degrees % 360
        position = int(degrees * 10)
        data = struct.pack(">H", position)
        if self._send_command(self.CMD_MOVE_AZ, data) is None:
            return False

        self.current_azimuth = degrees
        if not verify:
            return True

        # Block until CMD_GET_POS confirms the dish actually reached the
        # target (within tolerance) or confirm_timeout runs out -- lets
        # callers know if a single move genuinely happened vs. was just sent
        deadline = time.time() + confirm_timeout
        while time.time() < deadline:
            actual = self.get_position()
            if actual is not None and abs(((actual - degrees + 180) % 360) - 180) <= confirm_tolerance_deg:
                return True
            time.sleep(0.01)
        return False

    def paced_sweep(self, start_deg, end_deg, step_deg, confirm_tolerance_deg=1.5, confirm_timeout=0.5):
        """
        Generator that sweeps the dish from start_deg to end_deg in
        step_deg increments (step_deg's sign sets direction -- positive
        for ascending, negative for descending), yielding
        (azimuth, confirmed) for each commanded position.

        'confirmed' is True only if CMD_GET_POS reports the dish actually
        reached the target within confirm_tolerance_deg before
        confirm_timeout elapses. This is what lets radar_scanner.py detect
        if the sweep pace is outrunning the dish's real mechanical speed
        (see the "unconfirmed position(s)" warning in run()).

        Callers alternate direction between sweeps (start_deg/end_deg
        swapped, step_deg sign flipped) so the dish scans continuously
        on both the outbound and return leg instead of idling while it
        slews back to a fixed start position.
        """
        az = start_deg
        going_up = step_deg > 0

        # A full 360 sweep has start_deg/end_deg 360 apart (e.g. 0->360),
        # but 0 and 360 are the same physical bearing. Sampling both
        # double-counts one azimuth per revolution, so on a full-circle
        # sweep we stop one step short of end_deg instead of landing on
        # the duplicate.
        full_circle = abs(end_deg - start_deg) >= 360

        while (going_up and az <= end_deg) or (not going_up and az >= end_deg):
            if full_circle and az == end_deg:
                break
            self.move_to_azimuth(az)

            confirmed = False
            deadline = time.time() + confirm_timeout
            while time.time() < deadline:
                actual = self.get_position()
                if actual is not None and abs(((actual - az + 180) % 360) - 180) <= confirm_tolerance_deg:
                    confirmed = True
                    break
                time.sleep(0.01)

            yield (az % 360, confirmed)
            az += step_deg

    def stop(self):
        self._send_command(self.CMD_STOP)

    def home(self):
        print("[Motor] Calibrating dish to home index marker...")
        if self._send_command(self.CMD_HOME) is not None:
            self.current_azimuth = 0.0
            time.sleep(4)
            return True
        return False