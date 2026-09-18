# %%

import matplotlib.pyplot as plt
import numpy as np
import os
import datetime
import json
import collections

os.chdir(os.path.dirname(os.path.abspath(__file__))+ "/../")

from last_translation_benchmark.utils import permissive_strptime, save_compact_json

# progress over time figure
def date_to_delta(date_str):
    # subtract fom 2026-05-01
    # 2026-05-26 23:23
    # remove micros?
    if date_str.count(":") == 2:
        date_str = date_str.rsplit(":", 1)[0]
    date_obj = permissive_strptime(date_str)
    delta = date_obj - datetime.datetime(2026, 5, 1, tzinfo=datetime.UTC)
    return delta.days



with open("data/submissions.json", "r") as f:
    data_submissions = json.load(f)

# number of accepted, rejected, pending submissions
status_count = collections.Counter()
delta_today = date_to_delta(datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d %H:%M"))
dates_pending = [0]*(delta_today+1)
dates_accepted = [0]*(delta_today+1)
dates_returned = [0]*(delta_today+1)
for submission in data_submissions:
    status_count[submission["status"]] += 1
    dates = [submission["created_at"]] + [x["created_at"] for x in submission["comments"]]
    delta_first = date_to_delta(min(dates))
    delta_last = date_to_delta(max(dates))

    if submission["status"] == "accept":
        for i in range(delta_last, delta_today+1): 
            dates_accepted[i] += 1
        for i in range(delta_first, delta_last):
            dates_pending[i] += 1
    elif submission["status"] == "return":
        for i in range(delta_first, delta_last+1):
            dates_pending[i] += 1
        for i in range(delta_last, delta_today+1):
            dates_returned[i] += 1
    elif submission["status"] == "pending":
        for i in range(delta_first, delta_today+1):
            dates_pending[i] += 1

dates_accepted = np.array(dates_accepted)
dates_pending = np.array(dates_pending)
dates_returned = np.array(dates_returned)

plt.figure(figsize=(4, 2.5))
plt.plot(range(delta_today+1), dates_accepted, color="green", linewidth=2)
plt.plot(range(delta_today+1), dates_pending, color="orange", linewidth=2)
plt.plot(range(delta_today+1), dates_returned, color="red", linewidth=2)
plt.plot(range(delta_today+1), dates_accepted+dates_pending+dates_returned, color="black", linewidth=2)
plt.ylabel("Number of submissions")
plt.xlabel("Days since 2026-05-01")
plt.text(
    x=delta_today,
    y=dates_accepted[-1],
    s=f" Accepted: {status_count['accept']}",
    ha="left", va="center"
)
plt.text(
    x=delta_today,
    y=dates_pending[-1],
    s=f" Pending: {status_count['pending']}\n",
    ha="left", va="center",
)
plt.text(
    x=delta_today,
    y=dates_returned[-1],
    s=f" Returned: {status_count['return']}",
    ha="left", va="center",
)
plt.text(
    x=delta_today,
    y=dates_accepted[-1]+dates_pending[-1]+dates_returned[-1],
    s=f" Total: {len(data_submissions)}",
    ha="left", va="center",
)
print(dates_accepted[-8], dates_accepted[-8]+dates_pending[-8]+dates_returned[-8])
print(dates_accepted[-1], dates_accepted[-1]+dates_pending[-1]+dates_returned[-1])
plt.gca().spines[["top", "right"]].set_visible(False)
plt.tight_layout(pad=0.5)
plt.gca().patch.set_alpha(0)
plt.gcf().patch.set_alpha(0)
plt.savefig("computed/collection_progress.svg")
plt.show()