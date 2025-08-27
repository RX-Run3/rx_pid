'''
Script used to plot histograms made by PIDCalib2
'''
import os
import re
import glob
import pickle
import argparse
from typing import TypeAlias

import tqdm
import numpy
import mplhep
import matplotlib.pyplot as plt
import matplotlib.cm     as cm
from matplotlib.colors import Normalize
from boost_histogram       import Histogram as bh
from dmu.logging.log_store import LogStore

Npa : TypeAlias = numpy.ndarray

log=LogStore.add_logger('rx_pid:plot_histograms')
# ---------------------------------
class Data:
    '''
    Data class
    '''
    sig_cut      = '(PROBNN_E>0.2)&(DLLe>3.0)'
    ctr_cut      = '((PROBNN_E<0.2)|(DLLe<3.0))&(DLLe>-1.0)'
    d_hadron_cut = {'pion' : '&(PROBNN_K<0.1)', 'kaon' : '&(PROBNN_K>0.1)'}

    max_eff_pi : float = 20
    max_eff_k  : float = 20
    min_eff    : float = 0.

    max_rat_pi : float = 2.5
    max_rat_k  : float = 0.4
    min_rat    : float = 0.0

    dir_path   : str
    figsize    : tuple[int,int]
    fontsize   : int
    fancy      : bool = True
    skip_values: bool = True
    regex      : str  = r'effhists-2024_WithUT_(block\d)(?:_v\d+)?-(up|down)-([A-Z,a-z,0-9]+)-(.*)-([\w,(,)]+)\.(\w+)\.pkl'
# ---------------------------------
def _initialize() -> None:
    plt.style.use(mplhep.style.LHCb2)

    if Data.fancy:
        Data.figsize  = 12, 12
        Data.fontsize = 20
    else:
        Data.figsize  = 8, 8
        Data.fontsize = 15
# ------------------------------------
def _parse_args():
    parser = argparse.ArgumentParser(description='Script used to plot histograms in pkl files created by PIDCalib2')
    parser.add_argument('-d', '--dir_path', type=str, help='Path to directory with PKL files')
    args   = parser.parse_args()

    Data.dir_path = args.dir_path
# ------------------------------------
def _get_pkl_paths(kind : str, brem : str) -> list[str]:
    particle = {'kaon' : 'K', 'pion' : 'Pi'}[kind]
    path_wc  = f'{Data.dir_path}/{brem}/*-{particle}-*{Data.sig_cut}*.pkl'
    l_path   = glob.glob(path_wc)
    npath    = len(l_path)

    if npath == 0:
        raise FileNotFoundError(f'No files found in {path_wc}')

    return l_path
# ------------------------------------
def _hist_from_path(pkl_path : str) -> bh|None:
    with open(pkl_path, 'rb') as ifile:
        try:
            hist = pickle.load(ifile)
        except EOFError:
            log.warning(f'EOFError, cannot load: {pkl_path}')
            return None
        except ModuleNotFoundError:
            log.warning(f'ModuleNotFoundError, cannot load: {pkl_path}')
            return None

    log.debug(f'Loaded: {pkl_path}')

    return hist
# ------------------------------------
def _get_values(hist : bh) -> numpy.ndarray:
    bin_values = hist.view()

    try:
        counts = bin_values['value']
    except Exception:
        counts = bin_values

    return counts
# ------------------------------------
def _annotate_pcolormesh(arr_x, arr_y, counts, **kwargs):
    norm = Normalize(vmin=0, vmax=kwargs['maxz'])
    cmap = cm.get_cmap('viridis')

    for i in range(len(arr_x)-1):
        for j in range(len(arr_y)-1):
            x_center = (arr_x[i] + arr_x[i+1]) / 2
            y_center = (arr_y[j] + arr_y[j+1]) / 2

            value = counts[i,j]
            rgba  = cmap(norm(value))
            brightness = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
            color = 'black' if brightness > 0.5 else 'white'
            plt.text(x_center, y_center, f'{value:.2f}', ha='center', va='center', color=color)
# ------------------------------------
def _plot_hist(
    hist     : bh, 
    pkl_path : str,
    brem     : str,
    is_ratio : bool = False) -> None:
    x_edges    = hist.axes[0].edges
    y_edges    = hist.axes[1].edges
    counts     = _get_values(hist)

    arr_x, arr_y = numpy.meshgrid(x_edges, y_edges)

    plt.figure(figsize=(30, 15))

    if is_ratio:
        maxz = Data.max_rat_pi if '-Pi-' in pkl_path else Data.max_rat_k
        plt.pcolormesh(arr_x, arr_y, counts.T, shading='auto', norm=None, vmin=Data.min_rat, vmax=maxz)
        plt.colorbar(label='$w_{fake}$')
    else:
        counts  = 100 * counts
        maxz = Data.max_eff_pi if '-Pi-' in pkl_path else Data.max_eff_k
        plt.pcolormesh(arr_x, arr_y, counts.T, shading='auto', norm=None, vmin=Data.min_eff, vmax=maxz)
        plt.colorbar(label='Efficiency [%]')

    _annotate_pcolormesh(x_edges, y_edges, counts, maxz=maxz)
    _add_info(pkl_path, is_ratio, brem)

    ext      = '_ratio.png' if is_ratio else '.png'
    out_path = pkl_path.replace('.pkl', ext)

    plt.savefig(out_path)
    plt.close()
# ------------------------------------
def _add_info(
    pkl_path : str, 
    is_ratio : bool,
    brem     : str)-> None:
    file_name = os.path.basename(pkl_path)
    mtch      = re.match(Data.regex, file_name)
    if not mtch:
        raise ValueError(f'Cannot extract information from {file_name}, using {Data.regex}')

    [block, pol, par, cut, xlabel, ylabel] = mtch.groups()

    par   = {'K' : 'Kaon', 'Pi' : 'Pion'}[par]
    brem  = {'brem' : 'brem != 0', 'nobrem' : 'brem == 0'}[brem]

    title = f'{par}; Mag {pol}; {block}, {brem}'
    if not is_ratio:
        title += f';\n{cut}'
    else:
        title += '\n Signal over Control'

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
# ------------------------------------
def _divide_hists(sig : bh, ctr : bh) -> bh:
    vfun    = numpy.vectorize(lambda x : x[0])

    values1 = sig.view()
    values2 = ctr.view()

    values1 = vfun(values1)
    values2 = vfun(values2)

    ax_x = sig.axes[0]
    ax_y = sig.axes[1]

    rat  = bh(ax_x, ax_y)
    rat.values()[:] = numpy.where(values2 != 0, values1 / values2, numpy.nan)

    return rat
# ------------------------------------
def _plot_maps(l_path : list[str], brem : str) -> None:
    for sig_pkl_path in tqdm.tqdm(l_path, ascii=' -'):
        sig_hist = _hist_from_path(sig_pkl_path)
        if sig_hist is None:
            continue

        _plot_hist(hist=sig_hist, pkl_path=sig_pkl_path, brem=brem)

        ctr_pkl_path = sig_pkl_path.replace(Data.sig_cut, Data.ctr_cut)
        ctr_hist = _hist_from_path(ctr_pkl_path)
        if ctr_hist is None:
            continue

        _plot_hist(hist=ctr_hist, pkl_path=ctr_pkl_path, brem=brem)

        rat_hist = _divide_hists(sig=sig_hist, ctr=ctr_hist)
        _plot_hist(hist=rat_hist, pkl_path=sig_pkl_path, brem=brem, is_ratio=True)
# ------------------------------------
def main():
    '''
    start here
    '''
    _parse_args()
    _initialize()

    for kind in ['kaon', 'pion']:
        for brem in ['brem', 'nobrem']:
            l_path = _get_pkl_paths(kind, brem)
            _plot_maps(l_path, brem)
# ------------------------------------
if __name__ == "__main__":
    main()
