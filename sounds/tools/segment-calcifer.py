#!/usr/bin/env python3
from pathlib import Path
from scipy.io import wavfile

fn = 'Calcifer\'s Best Moments _ Studio Ghibli.wav'
timestamps = [(11.2,15.7), (20,28.7), (32.77,36.7), (41.5,45.8), (47,56), (58,60.97)]

try:
    fs
    w
    print('using file stored in RAM')
except NameError:
    print('reading file from disk')
    cwd = Path(__file__).resolve().parent
    fs, w = wavfile.read(cwd / fn)


for i, ts in enumerate(timestamps):
    curfn = f'calcifer-{i+1}.wav'
    n1 = round(ts[0]*fs)
    n2 = round(ts[1]*fs)
    data = w[n1:n2+1]
    wavfile.write(cwd.parent / curfn, fs, data)

