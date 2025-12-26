#include "SoftClockSerial.h"

SoftClockSerial::SoftClockSerial(uint8_t txPin, uint8_t rxPin, uint8_t signalPin)
    : _txPin(txPin), _rxPin(rxPin), _signalPin(signalPin) {
    _rxHead = 0;
    _rxTail = 0;
    _txHead = 0;
    _txTail = 0;
    _framingErrorCount = 0;
    _isReceiving = false;
}

void SoftClockSerial::begin(int _bla) {
    PINS_SETUP();
    setupTimer();
}

void SoftClockSerial::end() {
}

void SoftClockSerial::setupTimer() {
    // Timer1: Normal mode, prescaler 8
    // On 16MHz: 2MHz tick rate (0.5µs per tick)
    TCCR1A = 0;
    TCCR1B = (1 << CS11);  // Prescaler 8
    TCNT1 = 0;
}

inline void SoftClockSerial::timerReset() {
    TCNT1 = 0;
}

inline void SoftClockSerial::waitTicks(uint16_t ticks) {
    timerReset();
    while (TCNT1 < ticks);
}

uint8_t SoftClockSerial::available() {
    return (_rxHead - _rxTail + RX_BUFFER_SIZE) % RX_BUFFER_SIZE;
}

int SoftClockSerial::read() {
    if (_rxHead == _rxTail) {
        return -1;  // Buffer empty
    }

    uint8_t b = _rxBuffer[_rxTail];
    _rxTail = (_rxTail + 1) % RX_BUFFER_SIZE;
    return b;
}

size_t SoftClockSerial::write(uint8_t b) {
    // If we're in the middle of receiving, buffer for later
    if (_isReceiving) {
        txBufferPush(b);
        return 1;
    }

    // Otherwise send immediately
    transmitByte(b);
    return 1;
}

size_t SoftClockSerial::write(const uint8_t* buffer, size_t length) {
    for (size_t i = 0; i < length; i++) {
        write(buffer[i]);
    }
    return length;
}

bool SoftClockSerial::txEmpty() {
    return _txHead == _txTail;
}

uint16_t SoftClockSerial::parityErrors() {
    return 0;  // No parity in this version
}

uint16_t SoftClockSerial::framingErrors() {
    return _framingErrorCount;
}

void SoftClockSerial::clearErrors() {
    _framingErrorCount = 0;
}

void SoftClockSerial::update() {
    unsigned long startTime = millis();

    // Mark that we're in receive mode
    _isReceiving = true;

    // Signal ready to receive
    SIG_LOW();

    while (millis() - startTime < _timeoutTimeToWaitForSignalOnMs) {

        // Check for start bit (RX goes LOW)
        if (!RX_READ()) {
            // Start bit detected - receive immediately, inline
            cli();
            TCNT1 = 0;

            // Wait to middle of start bit
            while (TCNT1 < HALF_BIT_TICKS);

            // Verify start bit still LOW
            if (RX_READ()) {
                sei();
                continue;  // False start, keep looking
            }

            // Wait to middle of first data bit
            TCNT1 = 0;
            while (TCNT1 < BIT_TICKS);

            // Read 8 bits, LSB first
            uint8_t data = 0;
            for (uint8_t i = 0; i < 8; i++) {
                if (RX_READ()) {
                    data |= (1 << i);
                }
                TCNT1 = 0;
                while (TCNT1 < BIT_TICKS);
            }

            // Check stop bit (should be HIGH)
            if (!RX_READ()) {
                _framingErrorCount++;
            }

            sei();

            // Store in buffer
            rxBufferPush(data);

            // Restart timeout after receiving
            startTime = millis();
        }
    }

    // Signal not ready
    SIG_HIGH();

    // No longer receiving
    _isReceiving = false;

    // Now flush any buffered TX data
    flushTxBuffer();
}

void SoftClockSerial::flushTxBuffer() {
    while (_txHead != _txTail) {
        uint8_t b = _txBuffer[_txTail];
        _txTail = (_txTail + 1) % RX_BUFFER_SIZE;
        transmitByte(b);
    }
}

bool SoftClockSerial::startBitDetected() {
    unsigned long startTime = millis();

    while (digitalRead(_rxPin) == HIGH) {
        if (millis() - startTime >= _timeoutTimeToWaitForSignalOnMs) {
            return false;  // Timeout
        }
    }

    return true;  // Exited loop because pin went LOW = start bit detected
}

void SoftClockSerial::transmitByte(uint8_t data) {
    uint8_t oldSREG = SREG;
    cli();

    // Start bit
    TX_LOW();
    waitTicks(BIT_TICKS);

    // 8 data bits, LSB first
    for (uint8_t i = 0; i < 8; i++) {
        TX_WRITE(data & 0x01);
        data >>= 1;
        waitTicks(BIT_TICKS);
    }

    // Stop bit
    TX_HIGH();
    waitTicks(BIT_TICKS);

    SREG = oldSREG;
}

uint8_t SoftClockSerial::receiveByte() {
    uint8_t oldSREG = SREG;
    cli();

    waitTicks(HALF_BIT_TICKS);
    if (RX_READ()) {  // Should be LOW for valid start bit
        SREG = oldSREG;
        return 0;
    }

    waitTicks(BIT_TICKS);

    uint8_t data = 0;
    for (uint8_t i = 0; i < 8; i++) {
        if (RX_READ()) {
            data |= (1 << i);
        }
        waitTicks(BIT_TICKS);
    }

    if (!RX_READ()) {  // Stop bit should be HIGH
        _framingErrorCount++;
    }

    SREG = oldSREG;
    return data;
}

bool SoftClockSerial::rxBufferFull() {
    return ((_rxHead + 1) % RX_BUFFER_SIZE) == _rxTail;
}

void SoftClockSerial::rxBufferPush(uint8_t b) {
    if (!rxBufferFull()) {
        _rxBuffer[_rxHead] = b;
        _rxHead = (_rxHead + 1) % RX_BUFFER_SIZE;
    }
}

bool SoftClockSerial::txBufferFull() {
    return ((_txHead + 1) % RX_BUFFER_SIZE) == _txTail;
}

void SoftClockSerial::txBufferPush(uint8_t b) {
    if (!txBufferFull()) {
        _txBuffer[_txHead] = b;
        _txHead = (_txHead + 1) % RX_BUFFER_SIZE;
    }
}
