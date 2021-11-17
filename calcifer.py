#!/usr/bin/env python3
"""
TC execution thread
TODO: document

Interrupt thread by connecting to 127.0.01 at port in calcifer.ini
and sending b'off' to socket

# TODO: document hysterysis temperature state interface

Author: Marion Anderson
"""

__all__ = ['Calcifer, temp_all', 'gen_tc_types']

from argparse import ArgumentError, ArgumentParser
from configparser import ConfigParser
from logging import (CRITICAL, DEBUG, ERROR, INFO, WARNING, Formatter, Logger,
                     StreamHandler)
from pathlib import Path
from random import randint
from socket import AF_INET, SOCK_STREAM
from socket import error as sock_error
from socket import socket
from sys import stdout
from threading import Thread
from time import sleep, time

import board
from digitalio import Direction as dioDirection
from digitalio import Pull as dioPull
from digitalio import DigitalInOut as dioDigitalInOut
from adafruit_max31856 import MAX31856, ThermocoupleType


def gen_tc_types():
    """Generate allowed thermocouple types using the attributes of
    ThermocoupleType.

    Returns
    -------
    List of strings
        List of thermocouple type attribute names stored as strings.

    Notes
    -----
    Thermocouple types are 1-3 letters, all caps, attribute names of
    ThermocoupleType. So we can use dir(ThermocoupleType) and skip anything
    with an underscore to only keep the allowable thermocouple types.

    See Also
    --------
    `adafruit_max31856.ThermocoupleType`
    """
    return [str(v) for v in dir(ThermocoupleType) if '_' not in v]


def temp_all(spi, cs):
    """Measure thermocouple temperature for all thermocouple types.

    Parameters
    ----------
    spi : board.SPI object
        spi parameter for MAX31856 object
    cs : dioDigitalInOut object
        cs param for MAX31856 object

    Returns
    -------
    dict
        Temperature measurements keyed with thermocouple type

    See Also
    -------
    adafruit_max31856.MAX31856
    adafruit_max31856.ThermocoupleType
    """
    assert cs.direction == dioDirection.OUTPUT, 'cs must be output'
    outdict = {}
    for k in gen_tc_types():
        tctype = eval(f'ThermocoupleType.{k}')
        tc = MAX31856(spi, cs, thermocouple_type=tctype)
        outdict.update({k: tc.temperature})
    return outdict


# TODO: document attributes
class Calcifer(object):
    def  __init__(self, fnconf=None, section='DEFAULT', **kwargs):
        # Config Setup
        if fnconf is None:
            fnconf = Path(__file__).resolve().parent / 'calcifer.ini'
        self.fnconf = fnconf  # for --bg cli simply access
        conf = ConfigParser()
        try:
            conf.read(fnconf)
        except OSError as e:
            print('os error on conf read')

        # Overwrite Config File
        for k, v in kwargs.items():
            conf[section][k] = v

        # Read Config Params
        # - before major setup so errors avoid consuming resources
        # logging
        self.loglevel = eval(conf[section]['loglevel'])
        self._configlogger()
        # timing params
        self.T_read = float(conf[section]['T_read'])
        self.T_going = float(conf[section]['T_going'])
        self.T_hbeat = float(conf[section]['T_hbeat'])/2  # half for on/off cycle
        self.tc_reset_delay = float(conf[section]['tc_reset_delay'])
        self.drdy_count = 0  # timeout counter
        self.drdy_count_timeout = int(conf[section]['drdy_count_timeout'])
        self.prevdrdytime = time()
        # hysterysis temperature state thresholds
        self.thresh = float(conf[section]['thresh'])
        self.off_thresh = float(conf[section]['off_thresh'])
        # sound files
        self.soundpath = Path(__file__).resolve().parent / 'sounds'
        self.soundfns = list(self.soundpath.iterdir())
        # socket connections
        self.host = conf[section]['host']
        self.port = int(conf[section]['port'])
        # thermocouple
        self._tctype_str = conf[section]['tctype']  # for debugging
        self.tctype =  eval(f'ThermocoupleType.{conf[section]["tctype"]}')

        # Internal Setup
        self._buflen = 2  # buffer length
        self.clr_tempbuf()  # set self.tempbuf, self.bufndx
        self.fire_going = False
        self.runthread = None
        self.sockthread = None
        self.hbeatthread = None
        self.go = False

        # Thermocouple Setup
        self.spi = eval(conf[section]['spi'])
        self.cs = dioDigitalInOut(eval(conf[section]['cs']))
        self.cs.direction = dioDirection.OUTPUT
        self.drdy = dioDigitalInOut(eval(conf[section]['drdy']))
        self.drdy.direction = dioDirection.INPUT
        self.drdy.pull = dioPull.DOWN
        self._configtc()

        # TC Reset Relay Setup
        self.tc_reset = dioDigitalInOut(eval(conf[section]['tc_reset']))
        self.tc_reset.direction = dioDirection.OUTPUT
        self.tc_reset.value = 0

        # Indicator LED Setup
        self.hbeat = dioDigitalInOut(eval(conf[section]['hbeat']))
        self.hbeat.direction = dioDirection.OUTPUT
        self.hbeat.value = 0
        self.fault = dioDigitalInOut(eval(conf[section]['fault']))
        self.fault.direction = dioDirection.OUTPUT
        self.fault.value = 0

        # Sound Control Switch Setup
        self.soundswitch = dioDigitalInOut(eval(conf[section]['soundswitch']))
        self.soundswitch.direction = dioDirection.INPUT
        self.soundswitch.pull = dioPull.UP

        # Socket Setup
        self.sock = socket(AF_INET, SOCK_STREAM)

        # Log
        self.logger.debug(f'Calcifer setup complete. Configuration:{dict(conf[section])}')

    def _configtc(self):
        """Update `self.tc` with current spi, cs, tctype params.

        Notes
        -----
        Uses SPI bus, so can only be called after SPI bus setup
        """
        self.tc = MAX31856(self.spi, self.cs, thermocouple_type=self.tctype)

    def _configlogger(self):
        """Update `self.logger` with current loglevel param."""
        self.logger = Logger(__file__)
        handler = StreamHandler(stdout)
        handler.setLevel(self.loglevel)
        formatter = Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def set_tc_type(self, tctype):
        """Update thermocouple type.

        Parameters
        ----------
        tctype : str
            Thermocouple type being read; attribute of `ThermocoupleType`

        See Also
        --------
        adafruit_max31856.ThermocoupleType
        """
        self._tctypestr = tctype
        self.tctype = eval(f'ThermocoupleType.{tctype}')
        self._configtc()

    def set_loglevel(self, loglevel):
        """Change logger loglevel

        Parameters
        ----------
        loglevel : str/loglevel
            logging library loglevel. Choices: 'DEBUG', 'INFO', 'WARNING',
                                               'ERROR', 'CRITICAL'

        See Also
        --------
        logging
        logging.Logger
        """
        if str(loglevel) not in ('DEBUG','INFO','WARNING','ERROR','CRITICAL'):
            self.logger.error(f'invalid loglevel:{loglevel}')
            return
        self.loglevel = eval(loglevel)
        self._configlogger()

    @property
    def temperature(self):
        """Read sensor temperature"""
        return self.tc.temperature

    def clr_tempbuf(self):
        """Fill temperature buffer with zeros & reset buffer index."""
        self.tempbuf = [0 for i in range(self._buflen)]
        self.bufndx = 0

    def update_tempbuf(self):
        """Update self.tempbuf circular buffer."""
        # check that data is ready to be read
        drdyval = self.drdy.value
        if drdyval:
            self.bufndx = (self.bufndx + 1) % self._buflen  # current data ndx
            self.tempbuf[self.bufndx] = self.temperature
            self.drdy_count = 0  # reset timeout counter
        self.logger.debug(f'drdy before read:{self.drdy.value}')
        self.logger.debug(f'fault before read:{self.fault.value}')
        # timeout condition
        self.logger.debug(f'drdy_count:{self.drdy_count}')
        if self.drdy_count < self.drdy_count_timeout:
            self.fault.value = 0
        else:
            self.fault.value = 1
            self.logger.critical(f'drdy timed out; power cycling max')
            self.powercycle_max()

        self.drdy_count += 1  # increment timeout counter every time

    def soundbyte(self):
        """Play random file from `sounds/` directory."""
        n = randint(0, len(self.soundfns)-1)
        fn = self.soundfns[n]
        # https://github.com/TaylorSMarks/playsound/issues/16
        mixer.init()
        mixer.music.load(fn)
        mixer.music.play()
        while mixer.music.get_busy():  # TODO: infinite loop
            continue

    def _run(self):
        """Calcifer mainloop. Controlled by `self.go` attribute."""
        while self.go:
            self.update_tempbuf()
            self.logger.debug(f'tempbuf:{self.tempbuf}')
            self.logger.debug(f'fire_going:{self.fire_going}')

            if self.fire_going:
                if self.tempbuf[self.bufndx] < self.off_thresh:
                    self.fire_going = False
                    self.logger.info(f'Fire no longer going, tempbuf:{self.tempbuf}')
                sleep(self.T_going)

            else:
                if self.tempbuf[self.bufndx] > self.thresh:
                    # TODO: log thresh cross
                    if self.soundswitch.value:
                        self.soundbyte()
                    else:
                        self.logger.info('soundswitch low; not playing sound')
                    self.fire_going = True
                    self.logger.info(f'Fire going, tempbuf:{self.tempbuf}')
                sleep(self.T_read)

        self.logger.debug(f'run thread exited. go:{self.go}')
        self.logger.info('Calcifer program ended.')

    def _listen(self):
        """Shutoff command listener thread. Controlled by `self.go` attribute."""
        while self.go:
            self.sock.listen()
            conn, addr = self.sock.accept()
            data = conn.recv(128).decode('utf-8')
            # TODO: log received connections
            if data == 'off':
                self.go = False
                self.sock.close()
                self.logger.info('Shutoff signal recieved. Shutting down...')
            else:
                self.logger.warning(f'Socket connection sent {data} rather than off')
                self.fault.value = 1  # turn on fault led to alert user
            self.logger.debug(
                f'socket connection; conn:{conn} addr:{addr} data:{data} go:{self.go}'
            )
        self.logger.debug(f'listen thread exited. go:{self.go}')

    def _hbeat(self):
        """Heartbeat LED execution thread. Controlled by `self.go` attribute."""
        while self.go:
            self.hbeat.value = not self.hbeat.value if (self.T_hbeat>0) else 0  # no hbeat case
            sleep(self.T_hbeat)
        self.hbeat.hbeat = 0  # turn off led when ending program
        self.logger.debug(f'hbeat thread exited. go:{self.go}')

    def start(self):
        """Start Calcifer mainloop thread."""
        if self.go:
            self.logger.error('start called but go already True')
            return
        try:
            self.sock.bind(('127.0.0.1', self.port))
        except sock_error as e:
            print(e)
            self.logger.error(f'start called but 127.0.0.1:{self.port} already in use')
            return
        self.go = True
        # calcifer thread
        self.runthread = Thread(target=self._run, args=())
        self.runthread.daemon = True
        # shutoff command socket thread
        self.sockthread = Thread(target=self._listen, args=())
        self.sockthread.daemon = True
        # heartbeat thread
        self.hbeatthread = Thread(target=self._hbeat, args=())
        self.hbeatthread.daemon = True
        # start threads
        self.runthread.start()
        self.sockthread.start()
        self.hbeatthread.start()

    def _wrapup(self):
        """Release resources + turn off relay/leds."""
        self.hbeat.value = 0
        self.tc_reset.value = 0
        try:
            self.sock.close()
        except sock_error as e:
            pass

    def join(self):
        """Calcifer instance equivalent to `thread.join`"""
        self.hbeatthread.join()
        self.sockthread.join()
        self.runthread.join()
        self.logger.debug('All threads have joined')
        self._wrapup()

    def stop(self, join=False):
        """Stop Calcifer mainloop thread.

        Parameters
        ----------
        join : bool, optional
            Whether or not to join instance's run threads, by default False
        """
        # use socket to enforce
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.connect( (self.host, self.port) )
            sock.sendall( b'off' )
        if join:
            self.join()

    def powercycle_max(self):
        """Power cycle max chip using relay on relay pin."""
        self.tc_reset.value = True
        sleep(self.tc_reset_delay)  # TODO: empirically determined
        self.tc_reset.value = False
        self._configtc()  # call to ensure correct tc chip configuration
        sleep(self.tc_reset_delay)  # TODO: empirically determined


parser = ArgumentParser('CLI for thermocouples. ' +
                        'Also provides thermocouple threading class')
parser.add_argument('--fnconf', type=str, default=None,
                    help='Conf file for thermocouple. Defaults to calcifer.ini')
parser.add_argument('--section', type=str, default='DEFAULT',
                    help='Conf file section to use for thermocouple.')
parser.add_argument('--characterize', action='store_true',
                    help='Thermocouple characterization interface.')
parser.add_argument('--oneshot', action='store_true',
                    help='Report a single temperature reading.')
parser.add_argument('--type', type=str, default=None, choices=gen_tc_types(),
                    help='Specify thermocouple type; overrides config file setting.')
parser.add_argument('--loglevel', type=str, default=None,
                    choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                    help='Specify loglevel overriding config file setting.')
parser.add_argument('--run', action='store_true', help='Run Calcifer mainloop')
parser.add_argument('--bg', action='store_true', help='Run Calcifer mainloop in background.')
parser.add_argument('--stop', action='store_true', help='Stop Calcifer backgrounded mainloop')

if __name__ == '__main__':
    args = parser.parse_args()
    kwargs = {}
    if args.type is not None:  # set tc type after init for simplicity
        kwargs.update({'tctype':args.type})
    if args.loglevel is not None:
        kwargs.update({'loglevel':args.loglevel})
    job = Calcifer(fnconf=args.fnconf, section=args.section, **kwargs)

    if args.oneshot:
        print(f'{job._tctype_str}-type Temperature: {job.temperature}')

    if args.characterize:
        import matplotlib.pyplot as plt  # numerics only used here; import
        from numpy import asarray  # here to avoid slowing startup
        truetemp = []
        meastemp = []
        while True:
            inp = input('Reference Temperature (degC) (or \'quit\'): ')
            # exit cond
            if inp.lower() in ('q','quit','exit'):
                print('End characterization')
                break
            try:
                t = float(inp)
            # bad input
            except ValueError:
                print('Bad input')
                continue
            # temp reading
            else:
                truetemp.append(t)
                meastemp.append(temp_all(job.spi, job.cs))
        # reorder measurements into dict of lists
        meastemp_dict = {k:[] for k in meastemp[0].keys()}
        for m in meastemp:
            [meastemp_dict[k].append(v) for k,v in m.items()]
        meastemp = {k:asarray(v) for k,v in meastemp_dict.items()}
        errtemp = {k:v-truetemp for k,v in meastemp.items()}
        print('End computations')

        print('Plotting...')
        fig, ax = plt.subplots(ncols=2, num='tc-characterization')
        # Measurement Plot
        ax[0].set_title('Temperature Measurements')
        ax[0].set_ylabel('Temperature [deg C]')
        ax[0].set_xlabel('sample')
        for k,v in meastemp_dict.items():
            ax[0].plot(v, '-', label=f'{k}', marker=f'${k}$')
        # plot ground truth last for color matching b/t subplots
        ax[0].plot(truetemp, '.-', label='Ground Truth')
        ax[0].legend()

        # Error Plot
        ax[1].set_title('Temperature Error')
        ax[1].set_ylabel('Temperature Error [deg C]')
        ax[1].set_xlabel('sample')
        for k,v in errtemp.items():
            ax[1].plot(v, '-', label=f'{k}', marker=f'${k}$')
        ax[1].legend()

        plt.show()

    if args.bg:
        from subprocess import Popen  # subprocess only used here
        act = Path(__file__).resolve().parent / 'env/bin/activate'
        fn = Path(__file__).resolve()
        Popen(['python3', fn, f'--fnconf={job.fnconf}',
               f'--section={args.section}', f'--type={args.type}', '--run'])

    if args.run:
        # basic install check
        try:
            # https://github.com/TaylorSMarks/playsound/issues/16
            from pygame import mixer
        except Exception as e:
            print('Did you run `install-pygame-deps.sh`?')
            raise e
        # run job
        try:
            job.start()
            job.join()
        except (Exception, KeyboardInterrupt) as e:
            job.go = False
            if type(e) != KeyboardInterrupt:
                job.fault.value = 1  # turn on fault led
                job.logger.error(e)  # log error
                raise e

    if args.stop:
        job.stop(join=False)  # can't join; threads on diff Calcifer instance
