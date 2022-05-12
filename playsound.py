#!/usr/bin/env python3
"""
play arbitrary sound from Rpi
"""
if __name__ == '__main__':
    from argparse import ArgumentParser
    from pygame import mixer
    parser = ArgumentParser('Play arbitrary sound file from RPi')
    parser.add_argument('fn', type=str, help='sound file filename+path')
    args = parser.parse_args()
    mixer.init()
    mixer.music.load(args.fn)
    mixer.music.play()
    while mixer.music.get_busy():
        pass
    mixer.quit()

