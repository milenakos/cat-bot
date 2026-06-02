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

import os
import subprocess
import sys
import time

import requests

import config

CLUSTERS = 16

req = requests.get("https://discord.com/api/v10/gateway/bot", headers={"Authorization": f"Bot {config.TOKEN}"})
total = req.json()["shards"]

processes = {}


def start_cluster(start, end):
    args = [sys.executable, os.path.join(os.path.dirname(__file__), "bot.py"), str(start), str(end), str(total)]
    # this enherits env
    proc = subprocess.Popen(args)
    processes[proc.pid] = (proc, start, end)
    print(f"Started cluster w/shards {start}-{end - 1} pid={proc.pid}")
    return proc


def shutdown_all():
    print("Shutting down clusters...")
    for pid, (proc, start, end) in list(processes.items()):
        try:
            proc.terminate()
        except Exception:
            pass
    # give them a moment, then kill if needed
    time.sleep(3)
    for pid, (proc, start, end) in list(processes.items()):
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


if total < CLUSTERS:
    print("no")
    sys.exit()

base, extra = divmod(total, CLUSTERS)
n = min(CLUSTERS, total)
start = 0
for i in range(n):
    size = base + (1 if i < extra else 0)
    start_cluster(start, start + size)
    start += size

try:
    # monitor loop
    while processes:
        for pid, (proc, start, end) in list(processes.items()):
            ret = proc.poll()
            if ret is not None:
                print(f"Cluster shards {start}-{end - 1} (pid={pid}) exited with code {ret}")
                processes.pop(pid, None)
                print(f"Restarting cluster shards {start}-{end - 1} after 2s")
                time.sleep(2)
                start_cluster(start, end)
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    shutdown_all()
