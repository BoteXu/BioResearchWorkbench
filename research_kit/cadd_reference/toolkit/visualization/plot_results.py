#!/usr/bin/env python3
"""Plot supplied counts or per-replicate observables. Never invent data or run MD."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import re
import sys


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def configure_font(data, font_file):
    from matplotlib import font_manager, rcParams
    if font_file:
        font_manager.fontManager.addfont(str(font_file))
        family = font_manager.FontProperties(fname=str(font_file)).get_name()
    else:
        needs_cjk = bool(re.search(r'[\u3400-\u9fff]', json.dumps(data, ensure_ascii=False)))
        family = None
        names = ('Noto Sans CJK SC', 'Microsoft YaHei', 'SimHei', 'Arial Unicode MS') if needs_cjk else ('DejaVu Sans',)
        for name in names:
            try:
                font_manager.findfont(name, fallback_to_default=False)
                family = name
                break
            except ValueError:
                pass
        if family is None:
            raise ValueError('No suitable CJK font was found; provide --font-file with a local font file.')
    rcParams.update({'font.family': family, 'font.size': 10, 'axes.unicode_minus': False,
                     'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False})


def draw_funnel(data, plt):
    stages = data.get('stages')
    unit = data.get('counting_unit')
    if not isinstance(unit, str) or not unit or not isinstance(stages, list) or not stages:
        raise ValueError('Specify one counting_unit and a non-empty stages list.')
    previous = None
    labels, retained, filtered, failed = [], [], [], []
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get('label'), str) or not stage['label']:
            raise ValueError('Every stage requires a label.')
        values = [stage.get(key) for key in ('input_count', 'retained_count', 'filtered_count', 'failed_count')]
        if any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in values):
            raise ValueError('Every count must be a nonnegative integer; unfilled/null counts cannot be plotted.')
        n, r, f, e = values
        if n != r + f + e:
            raise ValueError(f"Counts do not balance at {stage['label']}: input != retained + filtered + failed")
        if previous is not None and n != previous:
            raise ValueError('Sequential funnel input must equal previous retained count. Split branching or state-expansion stages into separate diagrams.')
        previous = r
        labels.append(stage['label']);retained.append(r);filtered.append(f);failed.append(e)
    if max(r+f+e for r,f,e in zip(retained,filtered,failed)) == 0:
        raise ValueError('All counts are zero; no screening funnel exists to display.')
    fig, ax = plt.subplots(figsize=(8.2, max(3.2, .52 * len(stages) + 1.2)), layout='constrained')
    y = list(range(len(stages)))
    ax.barh(y, retained, color='#183A60', label='Retained')
    ax.barh(y, filtered, left=retained, color='#BFC8D1', label='Filtered')
    ax.barh(y, failed, left=[a+b for a,b in zip(retained,filtered)], color='#CC8053', label='Failed')
    ax.set_yticks(y, labels);ax.invert_yaxis();ax.set_xlabel('Count (' + unit + ')')
    ax.set_title(data.get('title', 'Screening stage accounting'), loc='left')
    for row, value in enumerate(retained):
        ax.text(value, row, f'  retained {value:,}', va='center', fontsize=9)
    # Keep the legend outside the data axes. Constrained layout reserves its
    # width while the left-aligned axes title remains above both bars and labels.
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0),
              borderaxespad=0, frameon=False)
    ax.grid(axis='x', alpha=.15);ax.set_axisbelow(True)
    return fig


def draw_timeseries(data, plt):
    for key in ('metric', 'unit', 'time_unit'):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f'{key} must be specified.')
    rows = data.get('records')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Provide non-empty records; the template has no simulated data.')
    groups = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):raise ValueError('Every record must be an object.')
        sid, rid, time, value = (row.get(k) for k in ('system_id', 'replicate_id', 'time', 'value'))
        if not isinstance(sid, str) or not sid or not isinstance(rid, str) or not rid:
            raise ValueError('Each record needs system_id and replicate_id.')
        if not finite_number(time) or (value is not None and not finite_number(value)):
            raise ValueError('Times must be finite; values must be finite or null for explicitly missing values.')
        if row.get('unit', data['unit']) != data['unit']:
            raise ValueError('Mixed units are not supported; convert explicitly before plotting.')
        key = (sid, rid)
        if groups[key] and time <= groups[key][-1][0]:
            raise ValueError(f'Time must strictly increase within {key}; check duplicate frames and segment joins.')
        groups[key].append((time, float('nan') if value is None else value))
    systems = list(dict.fromkeys(s for s,r in groups))
    if len(systems) > 12:raise ValueError('Select at most 12 systems per figure for readability.')
    if not any(math.isfinite(v) for points in groups.values() for t,v in points):
        raise ValueError('No finite observed values are available.')
    replicates = list(dict.fromkeys(r for s,r in groups))
    palette = plt.get_cmap('tab10')
    colors = {r:palette(i % 10) for i,r in enumerate(replicates)}
    fig, axs = plt.subplots(len(systems), 1, figsize=(8.2, 2.6 * len(systems)), sharex=True, sharey=True, squeeze=False, layout='constrained')
    for ax, sid in zip(axs[:,0], systems):
        for (system, rep), points in groups.items():
            if system == sid:
                times, values = zip(*points)
                ax.plot(times, values, label=rep, color=colors[rep], lw=1, alpha=.85)
        ax.set_title(sid, loc='left');ax.set_ylabel(data['metric']+' ('+data['unit']+')')
        ax.legend(loc='best', fontsize=8);ax.grid(alpha=.15)
    axs[-1,0].set_xlabel('Time ('+data['time_unit']+')')
    fig.suptitle(data.get('title', 'Per-replicate time series'), x=.01, ha='left', fontsize=12)
    return fig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('funnel','timeseries'))
    parser.add_argument('input', type=Path)
    parser.add_argument('--out-prefix', required=True, type=Path)
    parser.add_argument('--font-file', type=Path)
    args=parser.parse_args()
    try:
        data=json.loads(args.input.read_text(encoding='utf-8'))
        if not isinstance(data,dict):raise ValueError('Input must be a JSON object.')
        outputs=[Path(str(args.out_prefix)+suffix) for suffix in ('.svg','.png')]
        if any(p.exists() for p in outputs):raise FileExistsError('Output exists; choose a new output prefix.')
        if not args.out_prefix.parent.is_dir():raise FileNotFoundError('Create the output directory first.')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        configure_font(data,args.font_file)
        fig=draw_funnel(data,plt) if args.mode=='funnel' else draw_timeseries(data,plt)
        for output in outputs:fig.savefig(output,dpi=300,bbox_inches='tight')
        plt.close(fig)
        print(json.dumps({'outputs':[str(p.resolve()) for p in outputs], 'data_source':str(args.input.resolve()), 'statistics_computed':False},indent=2))
        return 0
    except (OSError,ValueError,TypeError,KeyError,ImportError) as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
