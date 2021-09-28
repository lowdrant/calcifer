#!/usr/bin/env python3
"""
TC execution thread
TODO: document

Author: Marion Anderson
"""

__all__ = ['Calcifer, temp_all']

from argparse import ArgumentError, ArgumentParser
from configparser import ConfigParser
from pathlib import Path
from random import randint
from threading import Thread
from time import sleep, time

import board
import digitalio
from adafruit_max31856 import MAX31856, ThermocoupleType
from pygame import mixer  # https://github.com/TaylorSMarks/playsound/issues/16


def temp_all(spi, cs):
    """Measure thermocouple temperature for all thermocouple types.

    Parameters
    ----------
    spi : board.SPI object
        spi parameter for MAX31856 object
    cs : digitalio.DigitalInOut object
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
    assert cs.direction == digitalio.Direction.OUTPUT, 'cs must be output'
    tc_types = [v for v in dir(ThermocoupleType) if '_' not in v]  # strs
    outdict = {}
    for k in tc_types:
        tctype = eval(f'ThermocoupleType.{k}')
        tc = MAX31856(spi, cs, thermocouple_type=tctype)
        outdict.update({k: tc.temperature})
    return outdict


# TODO: implement logger
# TODO: implement signal handling for external shutdown sig
# TODO: document attributes
class Calcifer(object):
    def  __init__(self, fnconf=None, section='DEFAULT', **kwargs_tc):
        # Config Setup
        if fnconf is None:
            fnconf = Path(__file__).resolve().parent / 'calcifer.ini'
        conf = ConfigParser()
        conf.read(fnconf)

        # Overwrite Config File
        for k,v in kwargs_tc:
            conf[section][k] = v

        # consts
        self._buflen = 2

        # Operating Params
        # - b4 tc setup so errors avoid consuming pinout resources
        self.T_read = float(conf[section]['T_read'])
        self.T_going = float(conf[section]['T_going'])
        self.thresh = float(conf[section]['thresh'])
        self.off_thresh = float(conf[section]['off_thresh'])
        self.soundpath = Path(__file__).resolve().parent / 'sounds'
        self.soundfns = list(self.soundpath.iterdir())

        # Thermocouple Setup
        self.spi = eval(conf[section]['spi'])
        self.cs = digitalio.DigitalInOut(eval(conf[section]['cs']))
        self.cs.direction = digitalio.Direction.OUTPUT
        self.drdy = digitalio.DigitalInOut(eval(conf[section]['drdy']))
        self.drdy.direction = digitalio.Direction.INPUT
        self.tctype = eval(f'ThermocoupleType.{conf[section]["tctype"]}')
        self._tctype_str = conf[section]['tctype']  # for debugging
        self._configtc()

        # Power Relay Setup
        self.relay = digitalio.DigitalInOut(eval(conf[section]['relay']))
        self.relay.direction = digitalio.Direction.OUTPUT
        self.relay.pull = digitalio.Pull.DOWN

        # Setup
        self.clr_tempbuf()  # set self.tempbuf, self.bufndx
        self.fire_going = False
        self.thread = None
        self.go = False

    def _configtc(self):
        """Update `self.tc` with current spi, cs, tctype params."""
        self.tc = MAX31856(self.spi, self.cs, thermocouple_type=self.tctype)

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
        # move ndx to ndx to be filled w/data, not next ndx
        self.bufndx = (self.bufndx + 1) % self._buflen
        self.tempbuf[self.bufndx] = self.temperature
        # TODO: log drdy state

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

    def soundbyte(self):
        """Play random file from `sounds/` directory."""
        n = randint(0, len(self.soundfns)-1)
        fn = self.soundfns[n]
        # https://github.com/TaylorSMarks/playsound/issues/16
        mixer.init()
        mixer.music.load(fn)
        mixer.music.play()
        while mixer.music.get_busy():
            continue

    def _run(self):
        """Calcifer mainloop. Controlled by `self.go` attribute."""
        while self.go:
            self.update_tempbuf()
            print(self.tempbuf)  # TODO: log temp
            if self.fire_going:
                if self.tempbuf[self.bufndx] < self.off_thresh:
                    self.fire_going = False
                sleep(self.T_going)
            else:
                if self.tempbuf[self.bufndx] > self.thresh:
                    # TODO: log thresh cross
                    self.soundbyte()
                    self.fire_going = True
                sleep(self.T_read)

    def start(self):
        """Start Calcifer mainloop thread."""
        if self.go:
            # TODO: log err
            return
        self.go = True
        self.thread = Thread(target=self._run, args=())
        self.thread.daemon = True
        self.thread.start()

    def join(self):
        """Equivalent to `thread.join`"""
        self.thread.join()

    def stop(self):
        """Stop Calcifer mainloop thread."""
        if self.thread is None:
            # TODO: log err
            return
        if not self.go:
            # TODO: log err
            return
        self.go = False
        self.thread.join()

    def powercycle_max(self):
        """Power cycle max chip using relay on relay pin."""
        self.relay.value = True
        sleep(0.01)  # empirically determined
        self.relay.value = False
        self._configtc()


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
parser.add_argument('--type', default=None,
                    help='Specify thermocouple type from command line.')
parser.add_argument('--run', action='store_true', help='Run Calcifer mainloop')
parser.add_argument('--bg', action='store_true', help='Run Calcifer mainloop in background.')
parser.add_argument('--stop', action='store_true', help='Stop Calcifer mainloop')
if __name__ == '__main__':
    args = parser.parse_args()
    job = Calcifer(fnconf=args.fnconf, section=args.section)
    if args.type is not None:  # set tc type after init for simplicity
        job.set_tc_type(args.type)

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
        import subprocess  # subprocess only used here
        fnpath = Path(__file__).resolve()
        argstr = f'--run --fnconf={fnconf} --section={section} --type={type}'
        subprocess.run(f'python3 {fnpath} --run &')

    if args.run:
        import signal
        job.start()
        job.join()
        # TODO: register signal handler
        # TODO: signal.pause() instead of .join?

    if args.stop:
        raise NotImplementedError
        # TODO: find all 'calcifer' processes
        # TODO: send signal.USR1
