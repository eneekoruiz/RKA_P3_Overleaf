#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exekuzio desberdinen ibilbideak eta paretarekiko angeluak konparatzeko grafikoak.

wall_follow_ls nodoak CSV bat gordetzen du exekuzio bakoitzaren amaieran (Ctrl+C),
results/ karpetan. Script honek CSV horiek irakurri eta bi irudi sortzen ditu.

Erabilera:
    python3 wf_plot.py IZENA fitxategia1.csv fitxategia2.csv ...   (gehienez 4)

Emaitza:
    IZENA_ibilbideak.png   robotaren ibilbideak (x, y)
    IZENA_angeluak.png     paretarekiko angelua denboran zehar
"""
import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np

KOLOREAK = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']


def etiketa(bidea):
    """Fitxategiaren izenetik irabazien etiketa osatu (adib. Kp=2, Ki=0.05, Kd=0.1)."""
    z = re.search(r'kp([\d.]+)_ki([\d.]+)_kd([\d.]+)_v([\d.]+)_kv([\d.]+)', os.path.basename(bidea))
    if z is None:
        return os.path.basename(bidea)
    kp, ki, kd, v0, kv = (float(g) for g in z.groups())
    testua = 'Kp=%g, Ki=%g, Kd=%g, v0=%g' % (kp, ki, kd, v0)
    return testua + (', kv=%g' % kv if kv > 0 else '')


def apaindu(ax):
    """Ardatzak eta sareta soildu, datuak nabarmentzeko."""
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(True, color='#e4e3df', linewidth=0.8)
    ax.set_axisbelow(True)


def ibilbideak(exekuzioak, irteera):
    """Ibilbide guztiak irudi berean marraztu, eskala errealean."""
    fig, ax = plt.subplots(figsize=(7, 5))
    for kolorea, (izena, d) in zip(KOLOREAK, exekuzioak):
        ax.plot(d['x'], d['y'], color=kolorea, linewidth=2, label=izena)
        ax.plot(d['x'][0], d['y'][0], 'o', color=kolorea, markersize=7)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel('x (m)')
    ax.set_ylabel('y (m)')
    ax.set_title('Robotaren ibilbideak (puntua: abiapuntua)')
    ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=2)
    apaindu(ax)
    fig.tight_layout()
    fig.savefig(irteera, dpi=150)


def angeluak(exekuzioak, irteera):
    """Exekuzio bakoitzaren angelua bere grafikoan, eskala berean konparatzeko."""
    n = len(exekuzioak)
    fig, axes = plt.subplots(n, 1, figsize=(7, 1.9 * n + 0.6), sharex=True, sharey=True, squeeze=False)
    for ax, kolorea, (izena, d) in zip(axes[:, 0], KOLOREAK, exekuzioak):
        ax.plot(d['t'], np.degrees(d['theta']), color=kolorea, linewidth=1.5)
        ax.axhline(0.0, color='#8a8984', linewidth=0.8)
        ax.set_ylabel('θ (gradu)')
        ax.set_title(izena, loc='left', fontsize=10)
        apaindu(ax)
    axes[-1, 0].set_xlabel('Denbora (s)')
    fig.tight_layout()
    fig.savefig(irteera, dpi=150)


def laburpena(exekuzioak):
    """Konparaketa-taula pantailan idatzi: txostenera zuzenean eraman daiteke."""
    print('%-40s %8s %9s %9s %9s %9s' % ('exekuzioa', 'iraup(s)', 'bidea(m)',
                                        '|θ|med(°)', 'θrms(°)', 'θmin(°)'))
    for izena, d in exekuzioak:
        th = np.degrees(d['theta'][~np.isnan(d['theta'])])
        bidea = np.nansum(np.hypot(np.diff(d['x']), np.diff(d['y'])))
        print('%-40s %8.1f %9.1f %9.2f %9.1f %9.1f' % (
            izena, d['t'][-1], bidea, np.median(np.abs(th)), np.sqrt(np.mean(th**2)), th.min()))


def main():
    if not 3 <= len(sys.argv) <= 6:
        sys.exit(__doc__)
    izena, fitxategiak = sys.argv[1], sys.argv[2:]
    exekuzioak = [(etiketa(f), np.genfromtxt(f, delimiter=',', names=True)) for f in fitxategiak]
    ibilbideak(exekuzioak, izena + '_ibilbideak.png')
    angeluak(exekuzioak, izena + '_angeluak.png')
    laburpena(exekuzioak)


if __name__ == '__main__':
    main()
