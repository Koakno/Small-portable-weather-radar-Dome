#!/usr/bin/env python3
"""
run.py — Entry point for the Portable Weather Radar stack
Portable Weather Radar — github.com/Koakno/Small-portable-weather-radar-Dome

Startup sequence:
  1. Print banner
  2. Detect elevation motor availability
  3. Prompt user for elevation configuration
  4. Pass elevation into RadarScanner
  5. Start scanner thread
  6. Start Flask web server
  7. Auto-open browser
"""

import sys
import os
import time
import webbrowser
from radar_scanner import RadarScanner
from app import init_web_server
import config


# ============================================================
# ELEVATION COUPLING COEFFICIENT
# ============================================================
# How many degrees of azimuth shift per degree of elevation
# change on the Carryout Anser's offset dish geometry.
# Calibrate once by pointing at a known landmark at two
# different elevations and measuring the apparent azimuth
# shift between them, then divide by the elevation difference.
# Default 0.4 is a reasonable starting estimate for a typical
# offset dish — tune empirically on first field deployment.
ELEVATION_COUPLING_COEFFICIENT = 0.4


def azimuth_correction_for_elevation(elevation_deg):
    """
    Returns the azimuth offset in degrees to subtract from every
    raw motor position reading to account for the dish's offset
    geometry coupling elevation into azimuth.
    Returns 0.0 if elevation is 0 or AUTO mode.
    """
    if elevation_deg is None or elevation_deg == "auto":
        return 0.0
    return float(elevation_deg) * ELEVATION_COUPLING_COEFFICIENT


def detect_elevation_motor():
    """
    Check whether an elevation motor is available by attempting
    to query the motor controller. Returns True if the controller
    responds with elevation axis capability, False otherwise.
    Currently returns False on all GM-5000 units since that model
    is documented as manual elevation only — update this function
    if opening the dome reveals an elevation motor is present.
    """
    # TODO: update this once dome internals are confirmed.
    # If elevation motor found, query it here and return True.
    return False


def get_elevation_config(has_elevation_motor):
    """
    Interactive startup prompt for elevation configuration.
    Blocks until valid input is received.

    Returns:
        float  — fixed elevation in degrees (manual set mode)
        "auto" — software elevation control (motor mode)
    """
    print("\n" + "=" * 54)
    print("  Elevation Configuration")
    print("=" * 54)

    if has_elevation_motor:
        print("  Elevation motor:  DETECTED")
        print()
        print("  Enter the current dish elevation in degrees,")
        print("  or type AUTO to enable software elevation control.")
        print()
        print("  Note: The Carryout Anser's offset dish geometry")
        print("  couples elevation into azimuth. Entering your")
        print("  current elevation allows the software to correct")
        print("  for this automatically on every radar return.")
    else:
        print("  Elevation motor:  NOT DETECTED (manual mode)")
        print()
        print("  Check the angle markings on the dome base and")
        print("  enter the elevation your dish is currently set to.")
        print()
        print("  The software will apply an azimuth correction")
        print(f"  of {ELEVATION_COUPLING_COEFFICIENT}° per degree of elevation to")
        print("  compensate for the offset dish geometry.")
        print()
        print("  Typical values:")
        print("    5°  — shallow scan, best long range storm detection")
        print("   15°  — moderate elevation, good general use")
        print("   30°  — steep, useful when very close to a storm")

    print()

    while True:
        try:
            response = input("  Elevation > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  [!] No input received — defaulting to 5 degrees")
            return 5.0

        if response == "AUTO":
            if has_elevation_motor:
                print()
                print("  [OK] Software elevation control enabled")
                print("       Elevation motor will be commanded by software")
                return "auto"
            else:
                print("  [!] No elevation motor detected")
                print("      Enter a numeric elevation value instead")
                continue

        try:
            elevation = float(response)
            if 0.0 <= elevation <= 90.0:
                correction = azimuth_correction_for_elevation(elevation)
                print()
                print(f"  [OK] Fixed elevation: {elevation}°")
                if correction > 0:
                    print(f"       Azimuth correction: -{correction:.1f}° applied to all returns")
                return elevation
            else:
                print("  [!] Enter a value between 0 and 90 degrees")
        except ValueError:
            if response:
                print(f"  [!] '{response}' is not a valid elevation")
                if not has_elevation_motor:
                    print("      Enter a number between 0 and 90")


def print_banner():
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║        PORTABLE WEATHER RADAR SYSTEM                ║")
    print("  ║        Winegard Carryout Anser GM-5000              ║")
    print("  ║        github.com/Koakno/Small-portable-weather-    ║")
    print("  ║        radar-Dome                                   ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()


def main():
    print_banner()

    # Detect elevation motor before prompting user
    has_elevation_motor = detect_elevation_motor()

    # Get elevation configuration from user
    elevation = get_elevation_config(has_elevation_motor)

    # Calculate azimuth correction for this elevation
    az_correction = azimuth_correction_for_elevation(elevation)

    print()
    print("  Starting radar stack...")
    print()

    # Pass elevation config into scanner
    scanner = RadarScanner(
        elevation=elevation,
        az_correction=az_correction,
        elevation_motor=has_elevation_motor
    )
    scanner.start()

    # Initialize web server
    app = init_web_server(scanner)

    # Auto-open browser (skip if no display available, e.g. Pi headless)
    time.sleep(1.0)
    try:
        webbrowser.open(f"http://localhost:{config.WEB_PORT}")
    except Exception:
        pass

    print(f"  [Web] Radar display: http://localhost:{config.WEB_PORT}")
    print(f"  [Web] Remote access: https://radar.koakno.com")
    print()
    print("  Press Ctrl+C to shut down")
    print()

    try:
        app.run(
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            debug=False,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n  [Core] Shutdown requested by user...")
    finally:
        print("  [Core] Stopping scanner and closing hardware connections...")
        scanner.running = False
        scanner.join(timeout=2.0)
        print("  [Core] System shut down cleanly.")
        print()


if __name__ == "__main__":
    main()
