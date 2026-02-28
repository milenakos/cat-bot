# Cat Bot - A Discord bot about catching cats.
# Copyright (C) 2026 Lia Milenakos & Cat Bot Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# this is almost fully coded by chatgpt i do not give a crap about matplotlib and numpy

import io
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np


def floor_to_bucket(ts_seconds: int, bucket_min: int) -> int:
    dt = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
    floored_min = (dt.minute // bucket_min) * bucket_min
    floored = dt.replace(minute=floored_min, second=0, microsecond=0)
    return int(floored.timestamp())


def aggregate_by_bucket(samples, bucket_minutes=5, lookback_days=3):
    now = datetime.now(timezone.utc)
    start_cutoff = now - timedelta(days=lookback_days)
    start_cutoff_ts = int(start_cutoff.timestamp())

    buckets = defaultdict(list)
    CHUNK = 10000
    for i in range(0, len(samples), CHUNK):
        chunk = samples[i : i + CHUNK]
        for ts, price in chunk:
            if ts < start_cutoff_ts or ts > int(now.timestamp()):
                continue
            b = floor_to_bucket(ts, bucket_minutes)
            buckets[b].append(price)

    timeline = OrderedDict()
    start_bucket = floor_to_bucket(start_cutoff_ts, bucket_minutes)
    end_bucket = floor_to_bucket(int(now.timestamp()), bucket_minutes)
    step = bucket_minutes * 60

    for b in range(start_bucket, end_bucket + 1, step):
        vals = buckets.get(b)
        if vals:
            arr = np.array(vals, dtype=float)
            timeline[b] = {"count": int(arr.size), "mean": float(arr.mean()), "min": float(arr.min()), "max": float(arr.max()), "sum": float(arr.sum())}
        else:
            timeline[b] = {"count": 0, "mean": float("nan"), "min": float("nan"), "max": float("nan"), "sum": 0.0}
    return timeline


def interpolate_means(timeline):
    xs = np.array(list(timeline.keys()), dtype=float)
    means = np.array([v["mean"] for v in timeline.values()], dtype=float)

    finite_mask = np.isfinite(means)
    if finite_mask.sum() == 0:
        return xs, means

    first_finite = np.where(finite_mask)[0][0]
    last_finite = np.where(finite_mask)[0][-1]
    means[:first_finite] = means[first_finite]
    means[last_finite + 1 :] = means[last_finite]

    interp_indices = np.where(~finite_mask)[0]
    if interp_indices.size:
        means = np.interp(xs, xs[finite_mask], means[finite_mask])

    return xs, means


def plot_aggregated(timeline, title="Price (5-min buckets, past 3 days)"):
    xs_ts, means = interpolate_means(timeline)
    xs = [datetime.fromtimestamp(int(ts), tz=timezone.utc) for ts in xs_ts]

    fig, ax = plt.subplots(figsize=(4.5, 3))
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    fig.set_facecolor("none")
    ax.set_facecolor("none")

    ax.plot(xs, means, color="#6e593c", linestyle="-", linewidth=1)
    ax.title.set_color("#808080")
    ax.xaxis.label.set_color("#808080")
    ax.yaxis.label.set_color("#808080")
    ax.tick_params(colors="#808080", which="both")
    for spine in ax.spines.values():
        spine.set_color("#808080")

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate(rotation=0)
    ax.set_xlim(xs[0], xs[-1])
    plt.tight_layout()

    for lbl in ax.get_xticklabels():
        lbl.set_rotation(0)
        lbl.set_ha("center")

    buffer = io.BytesIO()
    plt.savefig(buffer, dpi=67, format="png")
    plt.close()
    buffer.seek(0)

    return buffer


def make_graph(samples, minutes, days):
    timeline = aggregate_by_bucket(samples, minutes, days)
    return plot_aggregated(timeline)
