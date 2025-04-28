'''
Script used to plot histograms made by PIDCalib2
'''
import os
import re
import glob
import pickle
import argparse
from typing import TypeAlias, Union

import numpy
import mplhep
import matplotlib.pyplot as plt
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
    ctr_cut      = '(PROBNN_E<0.2|DLLe<3.0)&(DLLe>-1.0)'
    d_hadron_cut = {'pion' : '&(PROBNN_K<0.1)', 'kaon' : '&(PROBNN_K>0.1)'}

    max_eff_pi : float = 0.05
    max_eff_k  : float = 0.05
    min_eff    : float = 0.00

    max_rat_pi : float = 8.0
    max_rat_k  : float = 0.5
    min_rat    : float = 0.0

    dir_path   : str
    figsize    : tuple[int,int]
    fontsize   : int
    fancy      : bool = True
    skip_values: bool = True
    regex      : str  = r'effhists-2024_WithUT_(block\d)(?:_v1)?-(up|down)-([A-Z,a-z,0-9]+)-(.*)-([\w,(,)]+)\.(\w+)\.pkl'
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
def _get_pkl_paths(kind : str) -> list[str]:
    particle = {'kaon' : 'K', 'pion' : 'Pi'}[kind]
    path_wc  = f'{Data.dir_path}/*-{particle}-*{Data.sig_cut}*.pkl'
    l_path   = glob.glob(path_wc)
    npath    = len(l_path)

    if npath == 0:
        raise FileNotFoundError(f'No files found in {path_wc}')

    return l_path
# ------------------------------------
def _hist_from_path(pkl_path : str) -> Union[bh,None]:
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
def _plot_hist(hist : bh, pkl_path : str, is_ratio : bool = False) -> None:
    x_edges    = hist.axes[0].edges
    y_edges    = hist.axes[1].edges
    counts     = _get_values(hist)

    arr_x, arr_y = numpy.meshgrid(x_edges, y_edges)

    if is_ratio:
        max_rat = Data.max_rat_pi if '-Pi-' in pkl_path else Data.max_rat_k
        plt.pcolormesh(arr_x, arr_y, counts.T, shading='auto', norm=None, vmin=Data.min_rat, vmax=max_rat)
        plt.colorbar(label='$w_{fake}$')
    else:
        max_eff = Data.max_eff_pi if '-Pi-' in pkl_path else Data.max_eff_k
        plt.pcolormesh(arr_x, arr_y, counts.T, shading='auto', norm=None, vmin=Data.min_eff, vmax=max_eff)
        plt.colorbar(label='Efficiency')

    _add_info(pkl_path, is_ratio)

    ext      = '_ratio.png' if is_ratio else '.png'
    out_path = pkl_path.replace('.pkl', ext)

    plt.savefig(out_path)
    plt.close()
# ------------------------------------
def _add_info(pkl_path : str, is_ratio : bool) -> None:
    file_name = os.path.basename(pkl_path)
    mtch      = re.match(Data.regex, file_name)
    if not mtch:
        raise ValueError(f'Cannot extract information from {file_name}, using {Data.regex}')

    [block, pol, par, cut, xlabel, ylabel] = mtch.groups()

    par   = {'K' : 'Kaon', 'Pi' : 'Pion'}[par]
    title = f'{par}; Mag {pol}; {block}'
    if not is_ratio:
        title += f';\n{cut}'
    else:
        title += '\n Signal over Control'

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
# ------------------------------------
def _divide_hists(sig : str, ctr : str) -> bh:
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
def _plot_maps(l_path : list[str], kind : str) -> None:
    for sig_pkl_path in l_path:
        sig_hist = _hist_from_path(sig_pkl_path)
        if sig_hist is None:
            continue

        _plot_hist(hist=sig_hist, pkl_path=sig_pkl_path)

        ctr_pkl_path = sig_pkl_path.replace(Data.sig_cut, Data.ctr_cut)
        ctr_hist = _hist_from_path(ctr_pkl_path)
        if ctr_hist is None:
            continue

        _plot_hist(hist=ctr_hist, pkl_path=ctr_pkl_path)

        rat_hist = _divide_hists(sig=sig_hist, ctr=ctr_hist)
        _plot_hist(hist=rat_hist, pkl_path=sig_pkl_path, is_ratio=True)
# ------------------------------------
def main():
    '''
    start here
    '''
    _parse_args()
    _initialize()

    for kind in ['kaon', 'pion']:
        l_path = _get_pkl_paths(kind)
        _plot_maps(l_path, kind)
# ------------------------------------
if __name__ == "__main__":
    main()
