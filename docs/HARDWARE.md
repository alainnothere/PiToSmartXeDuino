# Hardware Setup Guide

This guide covers the physical assembly required to connect a Raspberry Pi Zero 2W to a SMART Response XE using the adapter board.

## What You Need

### Components

**Smart Response XE:**
- SMART Response XE unit
- 4×AA batteries (optional)

**Raspberry Pi:**
- Raspberry Pi Zero 2W (or compatible 40-pin GPIO device)
- MicroSD card with OS
- USB power supply for Pi

**Adapter Board:**
- Custom adapter PCB (files in `/SmartXeShieldForRaspberryPiZero2w` directory)

**Connection Hardware:**
- Pogo pin connectors ([example](https://www.amazon.com/gp/product/B07SMN8GMJ/)) to connect the adapter board to the SMART XE pins.
- Female headers to connect the adapter board to the PI ([example](https://www.amazon.com/2-54MM-Breakaway-Connector-Arduino-Prototype/dp/B08DVGCTKT))

**Tools:**
- Soldering iron and solder
- Screwdriver for XE battery cover

---

## The Adapter Board

The adapter board replaces the XE's battery compartment cover and routes signals from the XE's JTAG header to the Pi's GPIO pins.

**Three rows of connections:**
1. **Pogo pins/wire pads** - Connect to XE JTAG header
2. **19-pin header** - For bottom-mount Pi configuration (notice 1 pin is missing so the board can fit in the space for the battery cover)
3. **2×4 + 1×3 headers** - For top-mount/shield configuration

**Note:** The adapter board is purely passive - no active components, voltage regulators, or complex circuitry.

---

## Mounting Configurations

### Bottom Mount (Compact)
- XE below the pi
- You need to connect the bottom part of the pins on the pi to the adapter board, in this case the pi will go down from the screw that holds the battery/adapter board in place.
- **Use top two rows** of pins on adapter board
- Most compact
- Allows adding shields/HATs on top of Pi
- Better for expansion

### Top Mount (Shield Style)
- Adapter board connected to the pi like a shield, and the XE on top of that, in this case, you see the bottom of the pi on the back of the XE.
- **Use bottom two rows** of pins on adapter board
- easiest way
- 
---

## Assembly

### Step 1: Choose Mounting Style

**For Bottom Mount:**
- Use stacking headers ([example](https://www.amazon.com/gp/product/B09LH5SBPS/)) soldered to both adapter and Pi

**For Top Mount (Shield):**
- Solder the female headers to the adapter board
- Pi plugs down into sockets from above

### Step 2: Install Pogo Pins or Wires

**Pogo Pins (Recommended):**
- Spring-loaded pogo pins press against XE JTAG pads
- Removable connection
- No soldering to XE required

**Wires:**
- Solder wires from adapter pads to XE JTAG header
- Permanent connection

**Required Connections:**
| Signal | Function |
|--------|----------|
| TDO | Signal/Ready handshake |
| TMS | Soft Serial RX |
| TCK | Soft Serial TX |
| GND | Ground |
| VCC | 3.3V Power |

**Optional:**
| Signal | Function |
|--------|----------|
| RST | Arduino Reset (enables programming from Pi) |
| TDI | Used for programming via SPI, unused once the communication between the pi and the duino is going on |
| MOSI/MISO/SCK | SPI (for programming) |

### Step 3: Connect to XE

1. Remove XE battery cover (no need to open case)
2. make the pogo pins go through the holes in the back of the XE, the pins will naturally align as the board fits very tightly in the space of the battery cover.
3. Screw adapter board to XE battery compartment this will ensure pogo pins connect

---

## Pin Mapping

### XE JTAG to Adapter Pads

| XE JTAG Pad | Adapter Pad | Function                                  |
|-------------|-------------|-------------------------------------------|
| GND | GND | Ground                                    |
| VCC | VCC | 3.3V Power                                |
| TDI | TDI | SPI programming, unused during normal use |
| TDO | TDO | Signal/Ready                              |
| TMS | TMS | Soft Serial RX                            |
| TCK | TCK | Soft Serial TX                            |
| RESET | RST | Arduino Reset                             |

---

## Power Configuration

### Current Configuration

**Pi Powers XE:**
- USB power to Pi
- Pi's 3.3V output powers XE through VCC connection
- This is the only currently supported configuration

**What Does NOT Work:**
- XE batteries cannot power Pi (Pi requires 5V, XE only provides 3.3V)

### Future Enhancement

Planned board extension to:
- Tap XE battery + and - terminals
- Add 5V boost regulator to adapter board
- Allow both Pi and XE to run from AA batteries
- True portable operation

**Status:** Not yet implemented

---

## Communication Details

### Soft Serial Protocol

The system uses software serial at 19,200 baud on the XE's JTAG pins:

**From config.py:**
```python
BAUD_RATE_SOFT_SERIAL = 19200
USING_SOFT_SERIAL = True
SIGNAL_PIN_NUMBER_ON_GPIO_NUMBERING = 27  # BCM numbering
```

**Serial Device:**
```python
serial_port = "/dev/ttyAMA0"  # GPIO 14/15 on Pi
```

**Signal Routing:**
- Pi GPIO 14 (TXD) → XE TMS (RX)
- Pi GPIO 15 (RXD) ← XE TCK (TX)
- Pi GPIO 27 (config) or GPIO 12 (board) ← XE TDO (Signal/Ready)

**Why JTAG pins?** The XE's hardware UART is shared with the keyboard matrix. Using JTAG pins with software serial avoids electrical interference.

---

## Arduino Programming

The Pi can program the XE's ATmega128RFA1 directly using avrdude.

**Required:**
- avrdude installed on Pi

The Pi serves as a complete development environment - you can write code, program the Arduino, and test it all from the same device.

See INSTALLATION.md for avrdude setup details.

---

## Signal Reference

### Complete XE to Pi Mapping

| XE JTAG | Adapter | Pi Physical | Pi BCM | Current Use                                                                 |
|---------|---------|-------------|--------|-----------------------------------------------------------------------------|
| GND | GND     | 6,14,20,30 | GND | Ground                                                                      |
| VCC | VCC     | 1,17 | 3.3V | Power (from Pi)                                                             |
| TDI | TDI     | 37 | GPIO 26 | Used for programming the duino using avrdude, unused under the "normal" use |
| TDO | TDO     | 32 | GPIO 12 | Signal/Ready                                                                |
| TMS | TMS     | 8 | GPIO 14 | Soft Serial RX                                                              |
| TCK | TCK     | 10 | GPIO 15 | Soft Serial TX                                                              |
| RESET | RST     | 22 | GPIO 25 | Programming                                                                 |
| MOSI | MOSI    | 19 | GPIO 10 | Programming                                                                 |
| MISO | MISO    | 21 | GPIO 9 | Programming                                                                 |
| SCK | SCK     | 23 | GPIO 11 | Programming                                                                 |

---

## Notes

- No case opening required - only remove battery cover
- Board has provisions for CC1101 wireless module (CSN_C1101 net) but not implemented yet
- Pins 39 and 40 on Pi are not connected (board geometry constraint)
