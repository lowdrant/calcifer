#!/usr/bin/env python3
"""
Wrapper for Adafruit TC library. Only automates determining TC type for now

Author: Marion Anderson
"""

import board
import digitalio
from adafruit_max31856 import ThermocoupleType, MAX31856

__all__ = ['temp_all', 'determine_type']


def temp_all(spi,cs):
    """Measure TC temp for all TC types

    Parameters
    ----------
    spi : board.SPI object
        spi param for TC object
    cs : digitalio.DigitalInOut object
        cs param for TC object

    Returns
    -------
    dict
        Temperature measurements paired with TC type

    See Also
    -------
    adafruit_max31856
    """
    assert cs.direction == digitalio.Direction.OUTPUT, 'cs must be output'
    tc_types = [v for v in dir(ThermocoupleType) if '_' not in v]  # strs
    outdict = {}
    for k in tc_types:
        tc = MAX31856(spi,cs,type=eval('ThermocoupleType.'+k))
        outdict.update({k:tc.temperature})
    return outdict


def determine_type(spi,cs,tact):
    """Determine TC type using a reference temperature.

    Parameters
    ----------
    spi : board.SPI object
        spi param for TC object
    cs : digitalio.DigitalInOut object
        cs param for TC object
    tact : float
        actual temperature being measured

    Returns
    -------
    dict
        Temperature measurements paired with TC type

    See Also
    -------
    adafruit_max31856

    Notes
    -----
    Determines TC type by choosing TC type that minimizes absolute error
    between measured and actual temperature.
    """
    tdict = temp_all(spi,cs)
    errdict = {k:abs(tact-v) for k,v in tdict.items()}
    return min(errdict, key=lambda k: errdict[k])


