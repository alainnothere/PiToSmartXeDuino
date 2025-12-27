# Installation Guide

This guide covers software installation and configuration for the Raspberry Pi Zero 2W.

## Prerequisites

- Raspberry Pi Zero 2W with Raspberry Pi OS installed
- Internet connection (for package installation)
- Smart XE hardware assembled (see HARDWARE.md)
- Arduino sketch compiled to .hex file

---

## Quick Start

For experienced users:

```bash
# 1. Run setup script
./setup_pi.sh

# 2. Logout and login (or run: newgrp dialout && newgrp gpio && newgrp spi)

# 3. Copy project files
cp *.py ~/piToDuino/
cp pd ~/piToDuino/
chmod +x ~/piToDuino/pd

# 4. Copy Arduino hex file
cp sketch_jul16a.ino.hex ~/

# 5. Flash Arduino and run
./run.sh
```

---

## Detailed Installation

### Step 1: Prepare Raspberry Pi

**Update system:**
```bash
sudo apt update
sudo apt upgrade
```

**Run setup script:**
```bash
chmod +x setup_pi.sh
./setup_pi.sh
```

The setup script will:
- Install required packages (Python libraries, avrdude, pigpio, etc.)
- Add your user to required groups (dialout, gpio, spi)
- Enable pigpiod daemon
- Disable serial console (but keep UART hardware enabled)
- Configure SPI interface
- Create project directory at `~/piToDuino/`

**IMPORTANT:** After setup completes, you must logout and login again for group changes to take effect.

Alternatively, run:
```bash
newgrp dialout && newgrp gpio && newgrp spi
```

### Step 2: Copy Project Files

**Copy Python source files:**
```bash
# From the RaspberryPiZero2wSide directory
cp *.py ~/piToDuino/
```

**Copy pd utility:**
```bash
cp pd ~/piToDuino/
chmod +x ~/piToDuino/pd
```

**Verify files:**
```bash
ls -la ~/piToDuino/
```

You should see:
- `piToDuinoMain.py` - Main program
- `config.py` - Configuration
- `serialCommunicationsToArduino.py` - Serial communication
- `serial_connection.py` - Low-level serial
- `screen_controller.py` - Screen management
- `protocol.py` - Packet parser
- `keyboard_handler.py` - Keyboard handling
- `SubprocessTerminal.py` - Terminal backend
- `PyteAndPtyProcessTerminal.py` - Alternative terminal backend
- `utilities.py` - Helper functions
- `pd` - Date utility script

### Step 3: Compile Arduino Sketch

On your development machine (or the Pi):

**Using Arduino IDE:**
1. Open `ArduinoSide/DuinoToPiTerminal/DuinoToPiTerminal.ino`
2. Select Board: "Arduino" → "Arduino" → Custom (ATmega128RFA1)
3. Sketch → Export Compiled Binary
4. Locate the `.hex` file in the sketch directory

**Using arduino-cli:**
```bash
arduino-cli compile --fqbn arduino:avr:atmega128rfa1 DuinoToPiTerminal
```

**Copy hex file to Pi:**
```bash
# Rename to expected filename
cp DuinoToPiTerminal.ino.hex sketch_jul16a.ino.hex

# Copy to Pi home directory
scp sketch_jul16a.ino.hex pi@raspberrypi:~/
```

### Step 4: Flash Arduino Firmware

**Make flash script executable:**
```bash
chmod +x flash_arduino.sh
```

**Run flash script:**
```bash
./flash_arduino.sh
```

The flash script will:
1. Configure GPIO pins for SPI programming
2. Read current fuse values from Arduino
3. Display current configuration and what it means
4. Prompt to update fuses if needed (critical: JTAG must be disabled)
5. Flash firmware if hex file has changed
6. Restore GPIO pins to safe state

**Expected output:**
```
========================================
Smart XE Arduino Programming Script
========================================

User: pi
Home: /home/pi

Arduino hex file: /home/pi/sketch_jul16a.ino.hex

Configuring GPIO pins for SPI programming...
  ✓ GPIO pins configured

Reading current fuse values...

Current Fuse Values:
  Low Fuse (0xff):
    ✓ Clock: External Crystal/Resonator
    ✓ Startup: Fast (16K CK + 65ms)
    ✓ Clock Divide: Disabled (full speed)
  High Fuse (0xd9):
    ✓ JTAG: Disabled (allows using JTAG pins for I/O)
    ✓ SPI Programming: Enabled
    ...

✓ All fuses are correctly configured

Programming Arduino firmware...
  ...
  ✓ Firmware flashed successfully

========================================
Programming Complete!
========================================
```

**If fuses need updating:**

The script will show what needs to change and ask for confirmation:
```
⚠ High fuse needs update: 0x99 → 0xd9

  CRITICAL: JTAG is currently enabled!
  This prevents using TMS/TCK/TDO pins for serial communication.
  Fuses MUST be updated for the project to work.

Update fuses? [y/N]
```

Type `y` and press Enter to update fuses.

**Fuse restoration:**

If you need to restore fuses to previous values, the script displays the exact command:
```
To restore to current values if needed, use:
  sudo avrdude -p atmega128rfa1 -c linuxspi -P /dev/spidev0.0:/dev/gpiochip0:25 \
    -U lfuse:w:0x99:m \
    -U hfuse:w:0x99:m \
    -U efuse:w:0xf5:m
```

### Step 5: Test the Installation

**Run the terminal:**
```bash
python3 ~/piToDuino/piToDuinoMain.py /dev/ttyAMA0
```

**Or use the convenience script:**
```bash
chmod +x run.sh
./run.sh
```

**Expected behavior:**
1. Pi starts, connects to XE via serial
2. XE screen clears
3. Command prompt appears: `CMD> `
4. You can type commands on XE keyboard

**Test commands:**
```
CMD> ls
CMD> pwd
CMD> echo "Hello World"
```

**Change font:**
- Press `Shift+0` for Font 0 (normal)
- Press `Shift+1` for Font 1 (small)
- Press `Shift+2` for Font 2 (medium)
- Press `Shift+3` for Font 3 (large)

**Exit:**
- Press `Ctrl+C` on Pi's keyboard (if connected)
- Or: `sudo pkill python3` from SSH

---

## Configuration Files

### /boot/config.txt (or /boot/firmware/config.txt)

The setup script modifies `/boot/config.txt` to enable required interfaces:

```bash
# Enable SPI for Arduino programming
dtparam=spi=on

# Enable UART for serial communication
enable_uart=1
```

**Manual configuration:**
```bash
sudo raspi-config
# Select: Interface Options → SPI → Enable
# Select: Interface Options → Serial → Disable login shell, Enable serial hardware
```

### /boot/cmdline.txt (or /boot/firmware/cmdline.txt)

Serial console must be disabled. The setup script removes:
```
console=serial0,115200 console=ttyAMA0,115200
```

**Verify:**
```bash
cat /boot/cmdline.txt
# Should NOT contain "console=serial0" or "console=ttyAMA0"
```

### Serial Port

The project uses `/dev/ttyAMA0` which maps to GPIO 14/15:
- GPIO 14 (physical pin 8): TX
- GPIO 15 (physical pin 10): RX

**Verify serial port exists:**
```bash
ls -l /dev/ttyAMA*
# Should show: /dev/ttyAMA0
```

**Check permissions:**
```bash
groups
# Should include: dialout gpio spi
```

---

## Installed Packages

### System Packages

**Python and libraries:**
- `python3-pip` - Python package installer
- `python3-serial` - PySerial for serial communication
- `python3-pyte` - Terminal emulator (for future PTY support)
- `python3-ptyprocess` - PTY process management
- `python3-pil` - Python Imaging Library
- `python3-numpy` - Numerical computing

**Hardware interface:**
- `pigpio` - GPIO library
- `python3-pigpio` - Python bindings for pigpio
- `raspi-gpio` - GPIO utility

**Arduino programming:**
- `avrdude` - AVR device programmer
- `gcc-avr` - GCC for AVR
- `avr-libc` - AVR C library

**For pd utility:**
- `python3-tz` - Timezone definitions
- `python3-ephem` - Astronomical calculations
- `python3-psutil` - System utilities

### Services

**pigpiod daemon:**
```bash
# Check status
sudo systemctl status pigpiod

# Start manually
sudo systemctl start pigpiod

# Enable at boot
sudo systemctl enable pigpiod
```

---

## The pd Utility

The `pd` script is an example of extending the terminal with custom commands.

**Purpose:** Display date with astronomical calculations (sunrise, sunset, moon phase, etc.)

**Usage:**
```bash
CMD> pd
```

**How it works:**

1. **Internal command detection** in `utilities.py`:
```python
def is_internal_command(command: str) -> bool:
    if command == "pd":
        return True
    return False

def execute_internal_command(command: str) -> list[str]:
    if command == "pd":
        return utility_pydate.Utility_pydate.get_pydate()
    return []
```

2. **Main loop** in `piToDuinoMain.py`:
```python
if Utilities.is_internal_command(cmd):
    serial_to_duino.send_new_screen_lines_to_arduino(
        Utilities.execute_internal_command(cmd),
        current_font)
```

3. **pd script** (`utility_pydate.py`) generates output lines that are displayed on the XE screen.

**Adding your own commands:**

Create a new function in `utilities.py`:
```python
def execute_internal_command(command: str) -> list[str]:
    if command == "pd":
        return utility_pydate.Utility_pydate.get_pydate()
    
    if command == "mycommand":
        return ["Output line 1", "Output line 2", "Output line 3"]
    
    return []
```

Update `is_internal_command()`:
```python
def is_internal_command(command: str) -> bool:
    if command in ["pd", "mycommand"]:
        return True
    return False
```

---

## Troubleshooting

### Serial port not found

**Problem:** `/dev/ttyAMA0` doesn't exist

**Solution:**
```bash
# Check if UART is enabled
ls -l /dev/ttyAMA*
ls -l /dev/serial*

# Enable in config
sudo raspi-config
# Interface Options → Serial → Disable login shell, Enable serial hardware

# Reboot
sudo reboot
```

### Permission denied on /dev/ttyAMA0

**Problem:** `PermissionError: [Errno 13] Permission denied: '/dev/ttyAMA0'`

**Solution:**
```bash
# Add user to dialout group
sudo usermod -aG dialout $USER

# Logout and login, or:
newgrp dialout

# Verify
groups
# Should show: dialout
```

### pigpio error

**Problem:** `Can't connect to pigpio daemon`

**Solution:**
```bash
# Start pigpiod
sudo systemctl start pigpiod

# Check status
sudo systemctl status pigpiod

# Enable at boot
sudo systemctl enable pigpiod
```

### SPI not available

**Problem:** `/dev/spidev0.0` not found when flashing Arduino

**Solution:**
```bash
# Enable SPI
sudo raspi-config
# Interface Options → SPI → Enable

# Or edit config manually
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt

# Reboot
sudo reboot

# Verify
ls -l /dev/spidev*
# Should show: /dev/spidev0.0 and /dev/spidev0.1
```

### avrdude can't find device

**Problem:** `avrdude: error: unable to open: Device or resource busy`

**Solution:**
```bash
# Make sure no other SPI devices are using the bus
sudo systemctl stop spi-related-service

# Check GPIO pin configuration
raspi-gpio get 8,9,10,11,25

# Run flash script (it configures pins automatically)
./flash_arduino.sh
```

### Firmware flashes but terminal doesn't work

**Problem:** Terminal starts but no communication with XE

**Check list:**
1. Fuses are correct (JTAG disabled): `./flash_arduino.sh` shows fuse status
2. Serial console is disabled: `cat /boot/cmdline.txt` has no console= entries
3. Correct serial port: Using `/dev/ttyAMA0`
4. Hardware connections: TMS/TCK/TDO wired correctly (see HARDWARE.md)
5. XE is powered: check if the screen shows something... anything
6. Should not happen to you but if the reset line is down then the arduino will stay with the screen off, you should still be able to flash it thou, the script takes care of setting the pins in the correct state

**Debug:**
```bash
# Check if serial port is opening
python3 -c "import serial; s = serial.Serial('/dev/ttyAMA0', 19200); print('OK')"

# Check GPIO access
python3 -c "import pigpio; pi = pigpio.pi(); print('OK')"
```

### Screen shows garbage

**Problem:** Random characters or corrupted display

**Possible causes:**
1. Wrong baud rate (should be 19,200)
2. Signal pin not connected (TDO)
3. Electrical noise on serial lines
4. Fuses not set correctly (JTAG enabled)

**Solution:**
```bash
# Verify in config.py
grep "BAUD_RATE" ~/piToDuino/config.py
# Should show: BAUD_RATE_SOFT_SERIAL = 19200

# Check fuses
./flash_arduino.sh
# Look for: High Fuse (0xd9): JTAG: Disabled
```

---

## Development Setup

For developers who want to modify the code:

**Install type checking:**
```bash
sudo apt install python3-mypy
```

**Run type checker:**
```bash
cd ~/piToDuino
mypy *.py --ignore-missing-imports
```

**Edit code:**
```bash
# Any text editor works
nano piToDuinoMain.py
```

**Test changes:**
```bash
sudo pkill python3
python3 ~/piToDuino/piToDuinoMain.py /dev/ttyAMA0
```

**Flash modified Arduino code:**
```bash
# After compiling new .hex file
cp new_sketch.hex ~/sketch_jul16a.ino.hex
./flash_arduino.sh --force
```

---

## Updating

### Update Python code

```bash
# Copy new files
cp *.py ~/piToDuino/

# Restart terminal
sudo pkill python3
./run.sh
```

### Update Arduino firmware

```bash
# Copy new hex file
cp new_sketch.hex ~/sketch_jul16a.ino.hex

# Flash (automatic check for changes)
./flash_arduino.sh

# Or force flash
./flash_arduino.sh --force
```

### Update system

```bash
sudo apt update
sudo apt upgrade
```

---

## Uninstallation

To remove the project:

```bash
# Stop terminal
sudo pkill python3

# Stop pigpiod (if not needed for other projects)
sudo systemctl stop pigpiod
sudo systemctl disable pigpiod

# Remove project directory
rm -rf ~/piToDuino

# Remove Arduino hex
rm ~/sketch_jul16a.ino.hex
rm ~/.sketch_jul16a.ino.hex.last

# Remove scripts
rm ~/setup_pi.sh ~/flash_arduino.sh ~/run.sh

# Remove user from groups (optional)
sudo deluser $USER dialout
sudo deluser $USER gpio
sudo deluser $USER spi

# Re-enable serial console (optional)
sudo raspi-config
# Interface Options → Serial → Enable login shell

# Reboot
sudo reboot
```

---

## Summary

Installation requires:
1. Run `setup_pi.sh` - Install packages, configure system
2. Copy Python files to `~/piToDuino/`
3. Copy Arduino hex to `~/`
4. Run `flash_arduino.sh` - Program Arduino
5. Run terminal with `./run.sh` or `python3 ~/piToDuino/piToDuinoMain.py`

The system is now ready to use as a hardware terminal for the Raspberry Pi.
