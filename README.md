# calcifer
Raspberry Pi Talking Fireplace

## Quick Start
1. Use AdaFruit's [MAX31856 breakout board](https://www.adafruit.com/product/3263) and a fire-resistant [thermocouple](https://www.adafruit.com/product/3245) setup.
2. Follow this [AdaFruit wiring guide](https://learn.adafruit.com/assets/82229) and connect `DRDY` to `Board D27` and `FAULT` to `Board D20`
3. Put the thermocouple in your fireplace
4. Connect a speaker to the RPI headphone jack
5. Run the following in the terminal:
```
> git clone https://github.com/lowdrant/calcifer.git
> sudo apt install python3-pip  # skip if pip3 installed
> cd calcifer
> ./install.sh
> python3 calcifer.py --run --section=ADAFRUIT
```
### Fixing Sound Issues
Some PyGame dependencies need to be built from source (namely LibSDL2) for unknown reasons. If you are getting sound issues, run the below to install them.
```
> ./install-pygame-deps.sh
```

### Using with calciHATter PCB
calciHATter has a different wiring than the Adafruit guide. Tell the program to use the `CALCIHATTER` config section to adjust behavior accordingly.
```
> python3 calcifer.py --run --section=CALCIHATTER
```

### Run as a Background Process (Not Hang the Terminal)
```
> python3 calcifer.py --bg --section=<your section>
```
Running caclifer as a background process multiple times in a row may cause issues. Stop the background process using
```
> python3 calcifer.py --stop --section=<your section>
```

### Configure Calcifer to Start on Boot
TODO: rc.local editing script


## Customization with [calcifer.ini](calcifer.ini)

[calcifer.ini](calcifer.ini) can be edited to configure entire hardware pinout and some program logic. It must be edited before running `calcifer.py`. Editing it while calcifer is running will have no effect. It is parsed using Python3's `ConfigParser` object.

### GPIO Configuration
GPIO values need to be of the form `board.XX` as if they are commands in a Python script. This is because initialization uses `eval(\<param\>)` to init GPIO objects. Look into CircuitPython for more details.

| Field       | Desc                       | Example     | Notes                                  |
| ----------- | -------------------------- | ----------- | -------------------------------------- |
| spi         | Amplifier SPI bus          | board.SPI() | RPi SPI busses are weirdly specific    |
| cs          | Amplifier chip select      | board.D22   | Digital Output                         |
| drdy        | Amplifier data ready pin   | board.D27   | Digital Input                          |
| tc_fault    | Amplifier fault pin        | board.D3    | Digital Input                          |
| tc_reset    | Amplifier power switch pin | board.D26   | Digital Output; power cycles amplifier |
| soundswitch | Toggle sound playing       | board.D2    | Digital Input; play sound if high      |
| hbeat       | Heartbeat LED              | board.D21   | Digital Output                         |
| fault       | Fault indicator LED        | board.D20   | Digital Output                         |

### Temperature Logic
Configure temperature sensor type, active/inactive temperature thresholds, and data reading frequency.

| Field      | Desc                               | Example | Notes                                                    |
| ---------- | ---------------------------------- | ------- | -------------------------------------------------------- |
| tctype     | Thermocouple type                  | K       | Probably K. Must be `adafruit_max31856.ThermocoupleType` |
| thresh     | Fire-going detection threshold     | 100     | degC float                                               |
| off_thresh | Fire-off detection threshold       | 50      | degC float; must be less than thresh                     |
| T_read     | Temp sample period when fire-off   | 1       | Seconds; sets speed of fire detection                    |
| T_going    | Temp sample period when fire-going | 10      | Seconds; sets speed of fire-off detection                |

### Misc Behavior
This does not affect the user experience.
| Field              | Desc                        | Example   | Notes                                    |
| ------------------ | --------------------------- | --------- | ---------------------------------------- |
| host               | Host for `--stop`           | 127.0.0.1 | host must be RPi                         |
| port               | Port for `--stop`           | 10000     |                                          |
| loglevel           | log level to stdout         | DEBUG     | must be logging.Logger compatiable value |
| drdy_count_timeout | Timeout for amp power cycle | 3         | int                                      |
| T_hbeat            | Heartbeat period            | 2         | Seconds                                  |

## Design Overview
### Hardware
The calciHATter PCB conforms to the Raspberry Pi HAT standard. Its documentation, fabrication files, and bill of materials can be found in [calciHATter/](calciHATter/). I do not provide a means to program the HAT EEPROM for calciHATter setup.

### Software
Calcifer is packaged as an object inside a CLI script to run the calcifer mainloop in a clean, stateful way while also providing a basic testing/characterization interface for thermocouple evaluation and debugging.

The Calcifer object uses 3 threads in its execution
1. `_run`, which measures temperature and plays sound if fire goes from off to on
2. `_hbeat`, which blinks the heartbeat LED
3. `_listen`, which listens for a shutdown command on `port` and joins the threads on receipt of said shutdown command

## Author
Marion Anderson - [lmanderson42@gmail.com](mailto:lmanderson42@gmail.com)
