########################################################################################
#
########################################################################################
"""
load_shifting.py - load shifting module for CLOVER.

The load shifting module ...

"""

import os

# from logging import Logger
# from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.animation as anim

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from logging import Logger

from ..load.load import Device, Shiftability

__all__ = ("Task", "process_load_shifting")


@dataclass
class Task:
    device: Device
    original_hour: int
    electric_power: float
    priority_score: float
    shift_limit: int
    is_priority: bool
    shift_penalty: float
    task_id: int
    # duration: float
    _valid_hours: list[int] | None = None

    @property
    def valid_hours(self) -> list[int]:
        """
        A list of the valid hours.

        Returns:
            list[int]: A list containing all of the valid hours.
        """

        if self._valid_hours is None:
            # Calculate valid hours.
            pass

        return self._valid_hours

    def __repr__(self) -> str:
        return str(f"Task(id={self.task_id})")


from contextlib import contextmanager
import time


@contextmanager
def time_this_chunk_of_code() -> float:
    """
    Blah.
    """
    start_time = time.perf_counter()
    end_time = None
    try:
        yield lambda: (
            time.perf_counter() - start_time
            if end_time is None
            else end_time - start_time
        )
    except:
        print("Exception occurred.")
    else:
        print("No exception: code worked well.")
    finally:
        print("All code done: regardless of success, exiting.")
        print(f"{time.perf_counter() - start_time:.3g}")
        end_time = time.perf_counter()


def my_range(max: int):
    current = 0
    yield current
    while current < max:
        current += 1
        yield current
    return


class Context:
    def __init__(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc, tb):
        pass

    def __next__(self):
        pass

    def __iter__(self):
        pass

    def __get__(self, instance, owner):
        pass

    def __set__(self, instance, value):
        pass

    # Lookup more.


def score_hours(
    device_count,
    hourly_priority_scores,
    original_time,
    renewables_available,
    task,
    valid_hours,
) -> pd.Series:
    """_summary_

    Args:
        device_count(_type_): _description_
        hourly_priority_scores (_type_): _description_
        original_time (_type_): _description_
        renewables_available (_type_): _description_
        task (_type_): _description_
        valid_hours (_type_): _description_

    Returns:
        pd.Series: _description_
    """

    eps = 1e-9
    cand = sorted(valid_hours)  # NOTE: check if necessary

    R = pd.Series({h: renewables_available.loc[h] for h in cand})
    P = pd.Series({h: hourly_priority_scores.loc[h] for h in cand})
    C = pd.Series(
        {
            h: (
                task.priority_score
                * (task.shift_penalty ** abs(h - original_time))
                * abs(h - original_time)
            )
            for h in cand
        },
    )
    D = pd.Series({h: device_count.loc[h] for h in cand})

    Dn = (D - D.min()) / (D.max() - D.min() + eps)
    Rn = (R - R.min()) / (R.max() - R.min() + eps)
    Pn = (P - P.min()) / (P.max() - P.min() + eps)
    Cn = (C - C.min()) / (C.max() - C.min() + eps)
    wR, wP, wC, wD = 0.25, 0.35, 0.15, 0.25
    score = wR * Rn - wP * Pn - wC * Cn - wD * Dn
    return score


def _append_animation_frame(
    day1_loads: dict,
    frames: list,
    device: Device,
    orig_hour: int,
    best_hour: int,
    sim_start: int,
):
    # Only animate day 1
    if not (
        sim_start <= orig_hour < (sim_start + 24)
        and sim_start <= best_hour < (sim_start + 24)
    ):
        return

    # Update device hourly loads
    device_name = device.name
    load_val = device.electric_power
    day1_loads[device_name][orig_hour] -= load_val
    day1_loads[device_name][best_hour] += load_val

    # Add new frame
    frames.append({k: v.copy() for k, v in day1_loads.items()})


def process_load_shifting(
    # base_load: pd.Series,
    day: int,
    day1_loads: dict[str, pd.DataFrame],  # animation
    sim_times: tuple[int, int],
    daily_device_ownership: dict[Device, pd.DataFrame],
    device_count: defaultdict[Device, pd.Series],
    frames,  # animation
    hourly_priority_scores: pd.Series,
    renewables_available: pd.DataFrame,
    # shifted_load: pd.Series,
    # total_load: pd.DataFrame,
    total_tasks: list[list[Task]],
    unmet_load,
) -> tuple[dict[str, pd.Series], pd.Series]:
    """

    Rearranges loads over a time period based on renewable energy available
    NOTE: add tests,

    NOTE: could rename this load_shifting, and write a new process_load_shifting function
        that returns final shifted series/dicts, like a wrapper?

    Inputs:
        - period:
            time period within which loads are being shifted
        - device_hourly_usage:
            A mapping between device and its hourly load usage count.
        -
        -

    Outputs:
        -

    """

    # slice to consider time_period data only
    sim_start, sim_end = sim_times

    # create a df of singular, hourly shiftable loads in the time period
    tasks = total_tasks[day]

    # sort tasks in order of: priority, descending load size, original time
    tasks.sort(
        key=lambda t: (
            -t.priority_score,
            -t.electric_power,
            -hourly_priority_scores[t.original_hour],
            renewables_available[t.original_hour],
            t.original_hour,
            t.shift_limit,
        )
    )

    # shift and assign each task
    invalid_tasks: list[Task] = []  # tasks that can't be assigned in greedy loop
    tasks_by_hr_device: defaultdict[(Device, int), list[Task]] = defaultdict(
        list
    )  # assigned, shiftable tasks, by Device and hour

    # with time_this_chunk_of_code():
    for task in tasks:
        original_time = task.original_hour
        power = task.electric_power
        shift_lim = (
            task.shift_limit
        )  # could vary this by adding stochastic limit generation
        device = task.device
        device_ownership = (
            daily_device_ownership[device]
            .iloc[sim_start // 24 : sim_end // 24]
            .reset_index(drop=True)
        )  # ownership df of the device in the task

        # find valid hours for task, set comprehension
        valid_hours = {
            hour
            for hour in range(
                max((original_time - shift_lim), sim_start),
                min((original_time + shift_lim), sim_end),
            )
            if device_count[device].loc[hour]
            < device_ownership.iloc[
                day, 0
            ]  # number of active devices < number of devices owned
        }
        # find most suitable hour
        score = score_hours(
            device_count[device],
            hourly_priority_scores,
            original_time,
            renewables_available,
            task,
            valid_hours,
        )

        if score.empty:
            best_hour = np.int64(original_time)
        else:
            best_hour = score.idxmax()

        # assign the task
        device_count[device].loc[best_hour] += 1
        device_count[device].loc[original_time] -= 1
        hourly_priority_scores.loc[best_hour] += task.priority_score * abs(
            best_hour - original_time
        )
        hourly_priority_scores.loc[original_time] -= device.priority
        renewables_available.loc[best_hour] -= power  # NOTE: potential issue:
        # by not setting to zero, it allows for assigned load to exceed
        # renewables available
        renewables_available.loc[original_time] += power
        # shifted_load.loc[best_hour] += power
        tasks_by_hr_device[(device, best_hour)].append(task)

        if day == 0:  # frame for task shifting
            _append_animation_frame(
                day1_loads, frames, device, original_time, best_hour, sim_start
            )

    # try to swap tasks to fit in invalid_tasks
    # with time_this_chunk_of_code():
    invalid_tasks.sort(
        key=lambda t: (
            -t.priority_score,
            -t.electric_power,
            -hourly_priority_scores[t.original_hour],
            t.original_hour,
            t.shift_limit,
        )
    )

    for task in invalid_tasks:
        # find task's shifting window
        original_time = task.original_hour
        lower = max(original_time - task.shift_limit, sim_start)
        upper = min(original_time + task.shift_limit, sim_end)
        cand_hours = list(range(lower, upper))
        placed = False
        # score and sort cand_hours
        cand_score = score_hours(
            device_count[task.device],
            hourly_priority_scores,
            original_time,
            renewables_available,
            task,
            cand_hours,
        )
        cand_hours = sorted(
            cand_hours,
            key=lambda h: cand_score[h],
            reverse=True,
        )
        # go through cand_hours and the device tasks within them and try to rearrange
        for h in cand_hours:  # all hours will be full since task is in invalid_tasks
            if placed:
                break
            curr_instances = list(tasks_by_hr_device[(task.device, h)])
            curr_instances = sorted(
                curr_instances,
                key=lambda d: max(
                    abs(d.original_hour + d.shift_limit - original_time),
                    abs(d.original_hour - d.shift_limit - original_time),
                ),
                reverse=True,
            )  # sort current instances in h by descending order of shifting window furthest
            # from original_time of invalid task

            for inst in curr_instances:
                if placed == True:
                    break
                # find alternative hour, if none, continue to next instance
                inst_lower = max(inst.original_hour - inst.shift_limit, sim_start)
                inst_upper = min(inst.original_hour + inst.shift_limit, sim_end)

                inst_alt_h = [  # valid hours of inst that aren't h
                    hr
                    for hr in range(inst_lower, inst_upper)
                    if hr != h
                    and device_count[inst.device].loc[hr]
                    < daily_device_ownership[inst.device].loc[hr // 24, 0]
                ]

                if len(inst_alt_h) == 0:
                    continue

                inst_score = score_hours(
                    device_count[inst.device],
                    hourly_priority_scores,
                    inst.original_hour,
                    renewables_available,
                    inst,
                    inst_alt_h,
                )
                best_hour_2 = inst_score.idxmax()

                # rearrange tasks if possible
                # a. remove inst from h
                tasks_by_hr_device[(inst.device, h)].remove(inst)
                # device_count[inst.device].iloc[h] -= 1
                # shifted_load.iloc[h] -= inst.electric_power
                # renewables_available.iloc[h] += inst.electric_power
                hourly_priority_scores.loc[h] -= inst.priority_score * abs(
                    h - inst.original_hour
                )
                # b. place inst in best_hour_2
                tasks_by_hr_device[(inst.device, best_hour_2)].append(inst)
                device_count[inst.device].loc[best_hour_2] += 1
                # shifted_load.loc[best_hour_2] += inst.electric_power
                renewables_available.loc[best_hour_2] -= inst.electric_power
                hourly_priority_scores.loc[best_hour_2] += inst.priority_score * abs(
                    best_hour_2 - inst.original_hour
                )
                # c. place task in h
                tasks_by_hr_device[(task.device, h)].append(task)
                # device_count[task.device].iloc[h] += 1
                # shifted_load.iloc[h] += task.electric_power
                # renewables_available.iloc[h] -= task.electric_power
                hourly_priority_scores.loc[h] += task.priority_score * abs(
                    h - task.original_hour
                )
                hourly_priority_scores.loc[original_time] -= device.priority

                _append_animation_frame(
                    day1_loads, frames, device, original_time, best_hour, sim_start
                )
                placed = True

        # # or no swaps possible and load is unmet (unless it can move to next day)
        # if (
        #     placed == False
        # ):  # **load unmet, or moved to next day, then continue to next task
        #     pass

        invalid_tasks.remove(task)

    if len(invalid_tasks) > 0:
        # import pdb
        # pdb.set_trace()
        unmet_tasks = invalid_tasks
        additions = (
            pd.Series(
                [t.electric_power for t in invalid_tasks],
                index=[t.original_hour for t in invalid_tasks],
            )
            .groupby(level=0)
            .sum()
        )

        unmet_load = unmet_load.add(additions, fill_value=0)
    else:
        unmet_tasks = []
        unmet_load = None
    # find load profile after shifting
    # base_load += shifted_load

    # construct device-specific hourly usages
    devices = set(device for device in daily_device_ownership)
    device_hourly_loads_shifted: dict[str, pd.DataFrame] = {}
    for d in devices:
        p = d.electric_power
        n = d.name
        device_hourly_loads_shifted[n] = (device_count[d] * p).to_frame()
        # else:  # unshiftable devices
        #     d_hourly_usage = device_hourly_usage[d].iloc[hours, 0].astype(int)
        #     device_hourly_loads_shifted[n] = (d_hourly_usage * p).to_frame()

    return (
        device_hourly_loads_shifted,  # by device
        unmet_tasks,
        unmet_load,
    )  # total loads over time_period by DemandType
