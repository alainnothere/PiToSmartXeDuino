#ifndef SOFT_CLOCK_SERIAL_H
#define SOFT_CLOCK_SERIAL_H
#define RX_PIN 30  // Change this to 31 for the other version


// In SerialConfig.h or at the top of SoftClockSerial.h


// Pin mapping:
// Pin 30 (TCK) = PF4
// Pin 31 (TMS) = PF5
// Pin 32 (TDO) = PF6

#if RX_PIN == 30
    // Version 1: RX=30 (PF4), TX=31 (PF5), Signal=32 (PF6)
    #define TX_HIGH()    (PORTF |= (1 << PF5))
    #define TX_LOW()     (PORTF &= ~(1 << PF5))
    #define TX_WRITE(b)  if (b) TX_HIGH(); else TX_LOW()
    #define RX_READ()    (PINF & (1 << PF4))
    #define SIG_HIGH()   (PORTF |= (1 << PF6))
    #define SIG_LOW()    (PORTF &= ~(1 << PF6))
    #define PINS_SETUP() do { \
        DDRF |= (1 << PF5) | (1 << PF6); \
        DDRF &= ~(1 << PF4); \
        PORTF |= (1 << PF4); \
        TX_HIGH(); \
        SIG_HIGH(); \
    } while(0)

#elif RX_PIN == 31
    // Version 2: RX=31 (PF5), TX=30 (PF4), Signal=32 (PF6)
    #define TX_HIGH()    (PORTF |= (1 << PF4))
    #define TX_LOW()     (PORTF &= ~(1 << PF4))
    #define TX_WRITE(b)  if (b) TX_HIGH(); else TX_LOW()
    #define RX_READ()    (PINF & (1 << PF5))
    #define SIG_HIGH()   (PORTF |= (1 << PF6))
    #define SIG_LOW()    (PORTF &= ~(1 << PF6))
    #define PINS_SETUP() do { \
        DDRF |= (1 << PF4) | (1 << PF6); \
        DDRF &= ~(1 << PF5); \
        PORTF |= (1 << PF5); \
        TX_HIGH(); \
        SIG_HIGH(); \
    } while(0)

#else
    #error "RX_PIN must be 30 or 31"
#endif

#include <Arduino.h>

/*
 * Timer-Based Software Serial
 *
 * Uses Timer1 counter for precise bit timing - no interrupts
 * Standard async serial: start bit, 8 data bits (LSB first), stop bit
 *
 * Baud: 4800
 */

class SoftClockSerial {
public:
    // Buffer sizes
    static const uint8_t RX_BUFFER_SIZE =128;

    // Constructor - takes pin numbers
    SoftClockSerial(uint8_t txPin, uint8_t rxPin, uint8_t signalPin);

    // Initialize pins and timer
    void begin(int bla);
    void end();

    // Serial-like API
    uint8_t available();      // Returns number of bytes in RX buffer
    int read();               // Returns next byte from RX buffer, or -1 if empty
    size_t write(uint8_t b);  // Send one byte immediately
    size_t write(const uint8_t* buffer, size_t length);  // Send multiple bytes

    // Process incoming data - call this frequently from main loop
    // Checks for start bit and receives complete byte if detected
    void update();

    // Check if TX buffer is empty (for compatibility - always true since we send immediately)
    bool txEmpty();
    void flushTxBuffer();

    // Error counters (for compatibility)
    uint16_t parityErrors();
    uint16_t framingErrors();
    void clearErrors();

private:
    // Pins
    uint8_t _txPin;
    uint8_t _rxPin;
    uint8_t _signalPin;

    // RX buffer (circular)
    volatile uint8_t _rxBuffer[RX_BUFFER_SIZE];
    volatile uint8_t _rxHead;  // Write position
    volatile uint8_t _rxTail;  // Read position

    // TX buffer
    volatile uint8_t _txBuffer[RX_BUFFER_SIZE];
    volatile uint8_t _txHead;
    volatile uint8_t _txTail;

    volatile bool _isReceiving;

    // Error counters (for compatibility)
    uint16_t _framingErrorCount;

    // Timer constants for 4800 baud
    // Timer1 with prescaler 8 on 16MHz = 2MHz (0.5µs per tick)
    // Ticks per bit at 4800 baud = 2000000 / 4800 = 416.67 ≈ 417
    static const uint16_t BAUD_RATE = 19200;
    static const uint16_t BIT_TICKS = ((F_CPU / 8) / BAUD_RATE);       // 417
    static const uint16_t HALF_BIT_TICKS = (BIT_TICKS / 2);       // 208

    static const uint16_t _timeoutTimeToWaitForSignalOnMs = 10;

    // Internal methods
    void setupTimer();
    inline void timerReset();
    inline void waitTicks(uint16_t ticks);
    void transmitByte(uint8_t data);
    uint8_t receiveByte();
    bool startBitDetected();
    void rxBufferPush(uint8_t b);
    bool rxBufferFull();


    bool txBufferFull();
    void txBufferPush(uint8_t b);
};

#endif
