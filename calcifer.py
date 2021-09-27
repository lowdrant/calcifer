#!/usr/bin/env python3
"""
TC execution thread

Author: Marion Anderson
"""

__all__ = ['Calcifer, temp_all']

from argparse import ArgumentParser
from configparser import ConfigParser
from pathlib import Path
from random import randint
from time import time

import board
import digitalio
import matplotlib.pyplot as plt
from adafruit_max31856 import MAX31856, ThermocoupleType
from numpy import asarray
from playsound import playsound


def temp_all(spi, cs):
    """Measure thermocouple temperature of all thermocouple types

    Parameters
    ----------
    spi : board.SPI object
        spi parameter for MAX31856 object
    cs : digitalio.DigitalInOut object
        cs param for MAX31856 object

    Returns
    -------
    dict
        Temperature measurements paired with TC type

    See Also
    -------
    adafruit_max31856.MAX31856
    """
    assert cs.direction == digitalio.Direction.OUTPUT, 'cs must be output'
    tc_types = [v for v in dir(ThermocoupleType) if '_' not in v]  # strs
    outdict = {}
    for k in tc_types:
        tc = MAX31856(spi, cs, thermocouple_type=eval(f'ThermocoupleType.{k}'))
        outdict.update({k:tc.temperature})
    return outdict


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

        # Operating Params
        # - b4 tc setup so errors avoid consuming pinout resources
        self.T_read = conf[section]['T_read']
        self.thresh = conf[section]['thresh']
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

        # Setup
        self.clr_tempbuf()  # set self.tempbuf
        self.t_lastread = 0
        self.fire_going = False

    def _configtc(self):
        """Update `self.tc` with current spi, cs, tctype params."""
        self.tc = MAX31856(self.spi, self.cs, thermocouple_type=self.tctype)

    @property
    def temperature(self):
        """Read sensor temperature"""
        return self.tc.temperature

    def clr_tempbuf(self):
        """Clear temperature buffer."""
        self.tempbuf = [None,None]

    def update_tempbuf(self):
        """Update self.tempbuf using self.get_temp()."""
        self.tempbuf[0] = self.tempbuf[1]
        self.tempbuf[1] = self.temperature

    def set_tc_type(self, tctype):
        """Update thermocouple type.

        Parameters
        ----------
        tctype : str
            Thermocouple type being read
        """
        self._tctypestr = tctype
        self.tctype = eval(f'ThermocoupleType.{tctype}')
        self._configtc()

    def soundbyte(self):
        """Play random file from `sounds/` directory."""
        n = randint(0, len(self.soundfns))
        fn = self.soundfns[n]
        playsound(fn)

    def run(self):
        """[summary]

        Raises
        ------
        NotImplementedError
            [description]
        """
        while self.go:
            while not self.fire_going:
                if time() - self.t_lastread > self.T_read:
                    self.update_tempbuf()
                    self.t_lastread = time()
                if self.tempbuf[0] < self.temp_thresh and self.tempbuf[1] < self.temp_thresh:
                    self.playsound()
                    self.update_tempbuf()  # prevent continuous sound playing
                    self.fire_going = True
            while self.fire_going:
                raise NotImplementedError


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
if __name__ == '__main__':
    args = parser.parse_args()
    job = Calcifer(fnconf=args.fnconf, section=args.section)
    if args.type is not None:  # set tc type after for simplicity
        job.set_tc_type(args.type)

    if args.oneshot:
        print(f'{job._tctype_str}-type Temperature: {job.temperature}')

    if args.characterize:
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

        fig, ax = plt.subplots(ncols=2, num='tc-characterization')
        # Measurement Plot
        ax[0].set_title('Temperature Measurements')
        ax[0].set_ylabel('Temperature [deg C]')
        ax[0].set_xlabel('sample')
        for k,v in meastemp_dict.items():
            ax[0].plot(v, '.-', label=f'{k}', marker=f'${k}$')
        # plot ground truth last for color matching b/t subplots
        ax[0].plot(truetemp, '.-', label='Ground Truth')
        ax[0].legend()

        # Error Plot
        ax[1].set_title('Temperature Error')
        ax[1].set_ylabel('Temperature Error [deg C]')
        ax[1].set_xlabel('sample')
        for k,v in errtemp.items():
            ax[1].plot(v, '.-', label=f'{k}', marker=f'${k}$')
        ax[1].legend()

        plt.show()
