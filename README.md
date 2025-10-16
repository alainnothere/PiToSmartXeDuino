# PiToSmartXeDuino

PiToSmartXeDuino aims to use the Smart Xe as the keyboard and screen for a raspberry, in this case a pi zero 2w (you are going to read here like 10,000 different names for the berry and the pi including the typo of the Raspeberry which I'm to lazy to fix).

Right now, the duino is able to send the keys to the pi and the pi, executes the command, and send to duino what it needs to print on the screen.

In that sense the pi handles all the "intelligence", it has all the logic, keeps the status of the terminal, what's need to be send, what has been sent from the duino.

The duino in the other side just know to print whatever it receives from the pi and send to pi the keys pressed.

Communication is through the serial port, the SmartXe has a serial with pads but needs wires to bridge a missing component to be able to be used.

This project is based on:

- a ton of knowledge that exists in this forum https://community.arduboy.com/t/smart-response-xe-re-purposed-into-arduboy/6094/22
- this library by amazing https://github.com/bitbank2/SmartResponseXE by bitbank
- a ton of people how have done a lot of work to document the platform

The thing right now works as a terminal to the pi, in the sense that you can type commands and see results.
It cannot display yet say a nano editor window or top because that will probably require more refinement.

There are a couple of optimizations:
- If the command and the response are two lines, the screen is being "scrolled" up two lines and you print just the new lines
- If you need to print everything, right now we are printing just the chars that are needed to cover the previous string in the screen

After running lscpu
![My Image](photos/smartXe_001.jpg)

After running free
![My Image](photos/smartXe_002.jpg)

After running bad command bla
![My Image](photos/smartXe_000.jpg)

![My Image](photos/smartXe_setup_000.jpg)
![My Image](photos/smartXe_setup_001.jpg)
![My Image](photos/smartXe_setup_002.jpg)

