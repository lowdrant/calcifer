"""
TC execution thread

Author: Marion Anderson
"""
import configparser
import threading
from time import time

import board
import digitalio
from adafruit_max31856 import ThermocoupleType, MAX31856

class job(threading.Thread):
   def  __init__(self, spi=None, cs=None, tctype=None, T_read=None, temp_thresh=None, **thread_kwargs):
        raise NotImplementedError
        super().__init__(**thread_kwargs)  # init thread class first

        # Config Setup
        # TODO: read config file using ConfigParser
        if spi is None:
            raise NotImplementedError  # TODO
        if cs is None:
            raise NotImplementedError  # TODO
        if tctype is None:
            raise NotImplementedError  # TODO

        # Parameter Assigment
        self.spi = deepcopy(spi)
        self.cs = deepcopy(cs)
        self.set_tc_type(tctype)  # set self.tc attr
        self.clr_tempbuf()        # set self.tempbuf
        self.t_lastread = 0
        self.fire_going = False

    def run(self):
        """
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

    def get_temp(self):
        """Read TC temperature.

        Returns
        -------
        temp : float
            Measured temperature
        """
        # TODO: mutex
        return self.tc.temperature

    def update_tempbuf(self):
        """Update self.tempbuf using self.get_temp()."""
        self.tempbuf[0] = self.tempbuf[1]
        self.tempbuf[1] = self.get_temp()

    def set_tc_type(self, tctype):
        """Update TC type.

        Parameters
        ----------
        tctype : adafruit_max31856.ThermocoupleType attribute
            Thermocouple type being read

        Returns
        -------
        None
        """
        self.tc = MAX31856(self.spi, self.cs, type=tctype)

    def clr_tempbuf(self):
        """Clear temperature buffer."""
        self.tempbuf = [None,None]

    def playsound(self,fn):
        """Play sound through headphone jack.

        Parameters
        ----------
        fn : str or pathlib.Path object
            filename of audio file to play
        """
        raise NotImplementedError
        # TODO: mutex


