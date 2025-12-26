#ifndef SERIAL_CONFIG_H
#define SERIAL_CONFIG_H

#include "SoftClockSerial.h"

// Declare the instance (extern = "it exists somewhere else")
extern SoftClockSerial softSerial;

// Redefine Serial
#define USING_SOFTWARE_SERIAL

#ifdef USING_SOFTWARE_SERIAL
	#define Serial softSerial
#endif

#endif
