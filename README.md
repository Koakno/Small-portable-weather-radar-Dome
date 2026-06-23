================================================================
DIY MOBILE WEATHER RADAR — BUILD REFERENCE
Winegard Carryout Anser GM-5000 + HackRF One
================================================================
A low-cost mobile weather radar for storm chasing and severe
weather detection. No internet required. Fully self-contained.
Built around a salvaged RV satellite dome, a cheap SDR, and
open source software.

Inspired by SaveItForParts (github.com/saveitforparts) whose
Carryout-Radio-Telescope project proved the hardware concept.
This document extends that work toward a functional weather
radar application for storm chasing.

Estimated total cost: $90-165 depending on options
Expected detection range: 3-15 km (reverse drive LNB)
                          15-40 km (with Gunn oscillator TX)

----------------------------------------------------------------
THEORY OF OPERATION
----------------------------------------------------------------

The Winegard Carryout Anser contains a prime focus parabolic
dish with an Eagle Aspen LNB (Low Noise Block downconverter)
at the focal point. The LNB is designed to receive 12.2-12.7
GHz satellite signals and downconvert them to 950-1450 MHz IF
for the coax run to a satellite receiver.

For radar use we reverse-drive the LNB: inject a signal at the
IF frequency (850 MHz) into the coax, which the LNB upconverts
to 10.4 GHz and radiates through the dish as a narrow beam.
Rain, hail, and storm debris reflect a portion of that energy
back to the dish, which the LNB downconverts back to 850 MHz
for the SDR to capture.

The azimuth motor sweeps the dish in a full 360 degree arc,
building a Plan Position Indicator (PPI) radar image from the
signal strength at each bearing.

TX frequency math:
  LNB LO (11250 MHz) - Target (10400 MHz) = 850 MHz injection
  Any signal injected at 850 MHz exits the dish at 10.4 GHz

----------------------------------------------------------------
ANTENNA HARDWARE
----------------------------------------------------------------

Winegard Carryout Anser GM-5000
  Description:   Automatic portable RV satellite dome
  Dish type:     Prime focus parabolic, polished aluminum
  Dish size:     Approximately 18-22 inches diameter
  Gain at 10GHz: ~32-33 dBi
  Beamwidth:     ~4-5 degrees
  Rotation:      Single axis azimuth motor only
  Elevation:     Manual set and lock (no firmware limit)
  Drive:         Belt driven, ~360 degrees in 10 seconds
  Weight:        ~16 lbs
  Wind rating:   35 mph maximum (stow during transit)

LNB: Eagle Aspen 501353
  Type:          Voltage switched DBS dual output
  Input band:    12.2 - 12.7 GHz
  LO frequency:  11250 MHz
  IF output:     950 - 1450 MHz
  Outputs:       MAIN + SEC (both active simultaneously)
  Polarization:  13V = one pol, 18V = other pol
                 (does not matter for radar use)
  Bias power:    Supplied by receiver via coax (NOT internal)
                 External bias tee required

External connectors (on side of dome base):
  MAIN:  F connector, primary LNB output (use for HackRF)
  SEC:   F connector, secondary LNB output (use for RTL-SDR)
  PWR:   2-pin proprietary 12V DC input, ~1A draw

Motor control port:
  Location: Knockout panel on dome base, accessible externally
            Pop out the thin plastic knockout panel to expose
            the RJ-25 jack (intentional service access point)
  Connector: RJ-25 6-pin
  Protocol:  RS-485 serial
  Baud rate: 57600
  Note: Azimuth 0 degrees is approximately North
        MAIN/SEC F connectors sit at approximately 135 degrees

Included accessories:
  25 ft 12V power cable with car adapter
  20 ft RG6 coax cable

----------------------------------------------------------------
HARDWARE TO BUY
----------------------------------------------------------------

CRITICAL (needed to begin):

  [ ] HackRF One clone
        Purpose:   TX/RX SDR, reverse drives the LNB
        Where:     AliExpress, eBay, or Amazon
        Search:    "HackRF One r9" (specify revision)
        Price:     ~$50-80
        Notes:     Avoid listings under $40 (quality issues)
                   Allow 2-3 weeks shipping from AliExpress
                   Nooelec brand on Amazon ~$90, ships fast
                   Has ONE antenna port (ANT) for both TX/RX
                   Second port (CLKOUT) is 10MHz reference only

  [ ] F-to-SMA adapter (buy 2)
        Purpose:   Connects RG6 coax F connectors to HackRF SMA
        Type:      Female F to Male SMA
        Where:     Walmart TV section, Amazon, any electronics
        Price:     ~$5-10 for a pack

  [ ] DTECH RS232-to-RS485 converter
        Purpose:   Motor control serial interface
        Brand:     Specifically DTECH brand recommended
        Where:     Amazon, search "DTECH RS232 RS485"
        Price:     ~$12

  [ ] RJ-25 6-pin phone cord
        Purpose:   Connects RS-485 adapter to dome control port
        Important: Must be 6 conductor RJ-25, NOT standard
                   4-conductor RJ-11 phone cord
        Where:     Walmart phone accessories, Amazon
        Price:     ~$5

  [ ] USB-to-Serial cable
        Purpose:   Connects laptop to DTECH RS485 adapter
        Where:     Amazon, any electronics store
        Price:     ~$10

  [ ] Torx screwdriver set
        Purpose:   Opening dome for internal access if needed
        Sizes:     T10 and T15 for inner dome screws
                   T20 and T25 for outer ring screws
        Where:     Harbor Freight, any hardware store
        Price:     ~$6-8

RECOMMENDED:

  [ ] RTL-SDR V4
        Purpose:   Dedicated receive-only SDR on SEC port
                   Built-in software-switchable bias tee
                   Powers LNB via SEC coax (no external bias tee
                   needed on that port)
        Where:     rtl-sdr.com or Amazon
        Price:     ~$35

  [ ] 10 dB SMA attenuator
        Purpose:   Protects HackRF ANT port from strong
                   reflections at close range
        Where:     Amazon, search "SMA 10dB attenuator"
        Price:     ~$5

BIAS TEE (choose one option):

  Option A - Use RTL-SDR V4 bias tee (recommended):
        Connect RTL-SDR V4 to SEC port, enable bias tee in
        software. Powers LNB automatically. No components needed.

  Option B - Build internal bias tee:
        [ ] 100uH inductor (through-hole)  ~$1
        [ ] 100pF ceramic capacitor        ~$1
        Solder inline at red wire/coax junction inside dome.
        Blocks RF from 12V supply, blocks DC from HackRF.
        Eliminates need for any external bias tee hardware.

  Option C - External bias tee:
        [ ] RTL-SDR brand bias tee         ~$10-15
        Inline between MAIN port and HackRF ANT port.

FUTURE UPGRADE (significantly extends range):

  [ ] 10 GHz Gunn oscillator
        Purpose:   Dedicated TX source, replaces reverse-drive
                   method. Dramatically improves detection range.
        Where:     eBay, search "10 GHz Gunn oscillator" or
                   "10GHz beacon transmitter"
        Price:     ~$20-60 used
        Notes:     Needs 8-12V DC at ~300mA
                   Requires 10 GHz circulator to share antenna
                   Or use second dish as dedicated TX antenna

----------------------------------------------------------------
MOTOR CONTROL WIRING
----------------------------------------------------------------

The RJ-25 control port is accessible externally on the dome
base. Look for a thin plastic knockout panel on the side of
the dome housing. Pop it out with a flathead screwdriver --
it is intentionally designed to be removed (thin score lines
in the molding). The RJ-25 jack is immediately behind it.

Connection chain:
  Laptop USB
    -> USB-to-Serial cable
      -> DTECH RS232-to-RS485 converter
        -> RJ-25 6-pin cable
          -> Dome control port

RJ-25 pinout (viewing pin side of connector, cable end up):
  Pin 1: GND
  Pin 2: T/R-  (RS-485 transmit/receive negative)
  Pin 3: T/R+  (RS-485 transmit/receive positive)
  Pin 4: RXD-  (RS-485 receive negative)
  Pin 5: RXD+  (RS-485 receive positive)
  Pin 6: Not connected

Serial parameters:
  Baud rate:  57600
  Data bits:  8
  Stop bits:  1
  Parity:     None
  Flow ctrl:  None

Quick test (Linux):
  screen /dev/ttyUSB0 57600

Azimuth coordinate system:
  0 degrees   = approximately North
  135 degrees = approximately where MAIN/SEC F connectors face
  Motor does full 360 degree rotation with limit switches
  Mark your dome for field orientation reference

----------------------------------------------------------------
SIGNAL CHAIN
----------------------------------------------------------------

Normal operation (HackRF on MAIN, RTL-SDR on SEC):

  TRANSMIT:
  HackRF ANT port
    -> [10dB attenuator optional]
      -> F-to-SMA adapter
        -> MAIN F port
          -> internal coax (red wire)
            -> LNB MAIN output
              -> LNB mixer (upconverts 850MHz to 10.4GHz)
                -> LNB waveguide/feed horn
                  -> dish reflector
                    -> 10.4 GHz beam into sky

  RECEIVE (HackRF switches TX/RX internally, ~1-2 microseconds):
  Echo returns from rain/hail/debris
    -> dish reflector
      -> feed horn/waveguide
        -> LNB mixer (downconverts 10.4GHz echo to 850MHz)
          -> MAIN F port
            -> F-to-SMA adapter
              -> HackRF ANT port

  OPTIONAL DEDICATED RECEIVE:
  Same echo path via LNB SEC output
    -> SEC F port
      -> F-to-SMA adapter
        -> RTL-SDR V4 ANT port
          (RTL-SDR bias tee powers LNB simultaneously)

HackRF port clarification:
  ANT port   = your radar RF connection (TX and RX)
  CLKOUT port = 10MHz reference clock output only, NOT for RF

TX/RX timing (why switching speed is not a problem):
  HackRF TX/RX switch time:  ~1-2 microseconds
  Round trip at 3km:         ~20 microseconds
  Round trip at 5km:         ~33 microseconds
  Round trip at 10km:        ~67 microseconds
  Round trip at 20km:        ~133 microseconds
  Echo always arrives well after switch completes.

----------------------------------------------------------------
KEY FREQUENCIES
----------------------------------------------------------------

LNB local oscillator frequency:    11250 MHz
Target radar TX frequency:         10400 MHz
HackRF injection frequency:          850 MHz
  (11250 - 10400 = 850 MHz IF injection)
LNB IF output passband:         950-1450 MHz
Echo return frequency at SDR:        850 MHz

LNB input band (designed):    12200-12700 MHz
Radar frequency vs design:    10400 MHz (below designed band)
  Note: LNB operates outside its optimized band at 10.4GHz.
  Efficiency is reduced but sufficient for proof of concept.
  A dedicated 10GHz LNB improves performance if desired.

----------------------------------------------------------------
EXPECTED DETECTION PERFORMANCE
----------------------------------------------------------------

Reverse-drive LNB only (~1-5mW effective TX power):
  Heavy downpour (>25mm/hr):      3-8 km
  Supercell hail core:            8-15 km
  Tornado debris ball:            10-20 km
  Moderate rain (5mm/hr):         1-3 km
  Light rain/drizzle:             unlikely

With 4W Gunn oscillator TX (future upgrade):
  Heavy rain detection:           15-40 km
  Supercell core:                 30-60 km
  Tornado debris ball:            20-40 km

Scan performance:
  Full 360 degree sweep:          ~10 seconds
  180 degree hemisphere:          ~5 seconds
  90 degree sector scan:          ~2.5 seconds
  Angular resolution:             1-2 degrees recommended

Storm chasing notes:
  - Supercells are ideal targets: large, high reflectivity,
    hail dramatically increases radar return strength
  - Tornado debris ball detectable even at low power levels
  - Sector scanning toward storm gives near real-time updates
  - NEXRAD updates every 4-6 minutes; this system updates
    every 2-10 seconds depending on scan sector size

----------------------------------------------------------------
SOFTWARE TO INSTALL (Linux/Ubuntu/Debian)
----------------------------------------------------------------

1. GNU Radio (signal processing engine)
     sudo apt install gnuradio

2. HackRF drivers
     sudo apt install soapysdr-tools
     sudo apt install soapysdr-module-hackrf

3. RTL-SDR drivers
     sudo apt install rtl-sdr

4. GQRX (graphical SDR for initial testing)
     sudo apt install gqrx-sdr

5. Inspectrum (offline signal file analysis)
     sudo apt install inspectrum

6. Hamlib / rotctld (standard rotor control daemon)
     sudo apt install hamlib-utils

7. Python dependencies
     pip install pyserial numpy matplotlib scipy

8. SaveItForParts motor control repository
     git clone https://github.com/saveitforparts/Carryout-Radio-Telescope
     git clone https://github.com/saveitforparts/Carryout-Rotor

   Key file to study: carryout_scan.py
   This handles RS-485 motor commands and RTL-SDR signal
   capture. Adapt the signal capture portion for HackRF
   while keeping the motor control logic intact.

----------------------------------------------------------------
BRING-UP PROCEDURE (first time setup)
----------------------------------------------------------------

Step 1 - Verify motor control
  - Connect RS-485 chain to RJ-25 port
  - Power dome via 2-pin power connector
  - Run carryout_scan.py from SaveItForParts repo
  - Confirm dome responds to azimuth commands
  - Note azimuth 0 position relative to compass heading

Step 2 - Verify LNB power
  - Connect RTL-SDR V4 to SEC port
  - Enable bias tee in RTL-SDR software
  - Confirm LNB is powered (dome should behave normally)

Step 3 - Verify receive chain
  - Open GQRX, tune to 850 MHz
  - Point dish at a known signal source if available
  - Verify signal appears at 850 MHz in GQRX waterfall

Step 4 - First TX test (bench)
  - Connect HackRF ANT port to MAIN F port via adapter
  - Set HackRF to transmit at 850 MHz, low power
  - Point dish at a metal object (pot, bowl, car hood)
  - Watch for echo return at 850 MHz in receive window
  - Move metal object, confirm signal changes

Step 5 - Outdoor test
  - Set elevation manually to ~10-15 degrees
  - Run azimuth sweep while transmitting
  - Log signal strength vs azimuth position
  - Plot basic PPI display from logged data

Step 6 - Storm deployment
  - Mount on vehicle roof rack
  - Orient azimuth 0 to North using compass
  - Set elevation to 5-10 degrees for storm scanning
  - Run sector scan toward storm bearing
  - Monitor PPI display for echo returns

----------------------------------------------------------------
LICENSING
----------------------------------------------------------------

Transmitting at 10.4 GHz (3cm amateur band) legally requires
a minimum Technician class amateur radio license in the US.

  Exam:      35 multiple choice questions
  Fee:       ~$15
  Study:     HamStudy.org (free practice tests)
  Prep time: 1-2 weeks for most people
  Benefits:  Also enables APRS storm chaser position reporting
             and VHF/UHF communication with other chasers

The Technician license covers all amateur frequencies above
50 MHz including the full microwave spectrum.

----------------------------------------------------------------
RESOURCES
----------------------------------------------------------------

SaveItForParts GitHub repositories:
  github.com/saveitforparts/Carryout-Radio-Telescope
  github.com/saveitforparts/Carryout-Rotor

SaveItForParts YouTube videos:
  Carryout Anser teardown and motor control:
    youtu.be/QkvNH-tuAOo
  Microwave imaging with hacked TV dish:
    youtube.com/watch?v=lVOTZxNCgTM
  Hacking a Winegard Travler RV dish:
    youtube.com/watch?v=sn-Ayr4j6Ac

Software:
  GNU Radio:         gnuradio.org
  RTL-SDR drivers:   rtl-sdr.com
  GQRX:             gqrx.dk
  HamStudy (license): hamstudy.org

Weather / storm chasing:
  NWS Indianapolis SKYWARN: weather.gov/ind/skywarn
  Spotter Network:           spotternetwork.org

Hardware sources:
  HackRF One clone:  AliExpress, eBay, nooelec.com
  RTL-SDR V4:        rtl-sdr.com, Amazon
  Gunn oscillator:   eBay search "10 GHz Gunn oscillator"

----------------------------------------------------------------
ESTIMATED TOTAL COST
----------------------------------------------------------------

  Winegard Carryout Anser GM-5000 (salvage):   $5-40
  HackRF One clone:                           $50-80
  RTL-SDR V4:                                    $35
  Torx screwdriver set:                         $6-8
  F-to-SMA adapters (x2):                      $5-10
  DTECH RS232-to-RS485 converter:               $12
  RJ-25 6-pin cable:                             $5
  USB-to-Serial cable:                           $10
  10 dB SMA attenuator:                          $5
  Bias tee components (if building internal):    $2
                                           ---------
  TOTAL (Carryout from salvage at $5):    ~$135-167
  TOTAL (Carryout purchased new ~$40):    ~$170-202

Future upgrade - Gunn oscillator TX:         $20-60
  Adds significant range improvement

================================================================
DOCUMENT VERSION HISTORY
================================================================

v1.0 - 2026-06-22 - Initial build reference
  Hardware confirmed: Winegard Carryout Anser GM-5000
  LNB confirmed: Eagle Aspen 501353
  Motor control port confirmed: external RJ-25 knockout panel
  Baud rate confirmed: 57600 (from SaveItForParts repo)
  Video reference confirmed: youtu.be/QkvNH-tuAOo

================================================================
END OF DOCUMENT
================================================================
