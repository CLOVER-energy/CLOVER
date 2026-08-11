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
from .__utils__ import Scenario

__all__ = ("Task", "score_hours", "process_load_shifting")


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
        # print("No exception: code worked well.")
        pass
    finally:
        end_time = time.perf_counter()

# @contextmanager
# def time_this_chunk_of_code():
#     start_time = time.perf_counter()
#     try:
#         # caller receives a function to get current elapsed
#         yield lambda: time.perf_counter() - start_time
#     finally:
#         # keep this minimal; logging usually done by caller
#         pass


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


# def score_hours(
#     device_count: defaultdict[Device, pd.Series],
#     hourly_priority_scores: pd.Series,
#     original_time: int,
#     renewables_available: pd.Series,
#     task: Task,
#     valid_hours: set(int),
#     weights: list[float],
# ) -> pd.Series:

#     renewables_weight, priority_weight, penalty_weight, device_count_weight = weights

#     eps = 1e-9
#     cand = sorted(valid_hours)  # NOTE: check if necessary

#     R = pd.Series({h: renewables_available.loc[h] for h in cand})
#     P = pd.Series({h: hourly_priority_scores.loc[h] for h in cand})
#     C = pd.Series(
#         {
#             h: (
#                 task.priority_score
#                 * (task.shift_penalty ** abs(h - original_time))
#                 * abs(h - original_time)
#             )
#             for h in cand
#         },
#     )
#     D = pd.Series({h: device_count.loc[h] for h in cand})

#     D_norm = (D - D.min()) / (D.max() - D.min() + eps)
#     R_norm = (R - R.min()) / (R.max() - R.min() + eps)
#     P_norm = (P - P.min()) / (P.max() - P.min() + eps)
#     C_norm = (C - C.min()) / (C.max() - C.min() + eps)

#     score = (
#         renewables_weight * R_norm
#         - priority_weight * P_norm
#         - penalty_weight * C_norm
#         - device_count_weight * D_norm
#     )
#     return score



def _calculate_best_hour(
    device_count_series: pd.Series,
    hourly_priority_scores: pd.Series,
    original_time: int,
    renewables_available: pd.Series,
    sim_start: int,
    task: Task,
    valid_hours: set[int],
    weights: list[float],
) -> int:
    
    renewables_weight, priority_weight, penalty_weight, device_count_weight = weights
    eps = 1e-9

    def norm(x):
        return (x - x.min()) / (x.max() - x.min() + eps)

    cand = np.fromiter(valid_hours, dtype=np.int64)

    R = renewables_available.values[cand-sim_start]
    P = hourly_priority_scores.values[cand-sim_start]
    D = device_count_series.values[cand-sim_start]

    dist = np.abs(cand - original_time)
    C = task.priority_score * (task.shift_penalty ** dist) * dist

    score = (
        renewables_weight * norm(R)
        - priority_weight * norm(P)
        - penalty_weight * norm(C)
        - device_count_weight * norm(D)
    )

    return int(cand[np.argmax(score)])


def _append_animation_frame(
    day1_loads: dict,
    frames: list,
    frames_subtitle: list[str],
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
    frames_subtitle.append(f"{device.name} from hour {orig_hour-sim_start} to hour {best_hour-sim_start}")


def process_load_shifting(
    # base_load: pd.Series,
    day: int,
    day1_loads: dict[str, pd.DataFrame],  # animation
    sim_times: tuple[int, int],
    daily_device_ownership: dict[Device, pd.DataFrame],
    device_count: defaultdict[Device, pd.Series],
    frames: list,  # animation
    frames_subtitle: list[str],
    hourly_priority_scores: pd.Series,
    total_load: pd.Series,
    renewables_available: pd.DataFrame,
    renewables_produced,
    renewables_used_directly,
    renewables_used_directly_metric,
    total_tasks: list[list[Task]],
    weights,
    logger
    # unmet_load,
) -> tuple[dict[str, pd.Series], pd.Series]:
    """

    Rearranges loads over a time period based on renewable energy available and priority scores
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

    # with time_this_chunk_of_code() as elapsed_t:
    # slice to consider time_period data only
    sim_start, sim_end = sim_times
    ownerships = {device: df.iloc[day+sim_start//24,0] for device, df in daily_device_ownership.items()}
    # create a df of singular, hourly shiftable loads in the time period
    tasks = total_tasks[day]

    # sort tasks in order of: priority, descending load size, original time
    tasks.sort(
        key=lambda t: (
            -t.priority_score,
            -t.electric_power,
            -hourly_priority_scores.loc[t.original_hour],
            renewables_available.loc[t.original_hour],
            t.original_hour,
            t.shift_limit,
        )
    )

    # if day%50 == 0:
    #     logger.info(f"TIMING: day {day} sort tasks for shifting took {elapsed_t():.6f}s")

    tasks_iter = (t for t in tasks)
    for task in tasks_iter:
        # with time_this_chunk_of_code() as elapsed_t:
        original_time = task.original_hour
        power = task.electric_power
        shift_lim = (
            task.shift_limit
        )  # could vary this by adding stochastic limit generation
        device = task.device
        device_ownership = ownerships[device] # ownership df of the device in the task

        # find valid hours for task, set comprehension
        valid_hours = {
            hour
            for hour in range(
                max((original_time - shift_lim), sim_start),
                min((original_time + shift_lim), sim_end),
            )
            if device_count[device].loc[hour]
            < device_ownership  # number of active devices < number of devices owned
        }
        # if day%50 == 0 and task.task_id%100==0:
        #         logger.info(f"TIMING: task {task.task_id} find valid hours {elapsed_t():.6f}s")
        # find most suitable hour
        # with time_this_chunk_of_code() as elapsed_t:
        if len(valid_hours) == 0:
            # best_hour = np.int64(original_time)
            continue
        else:
            # if device.name == "fan":
            #     import pdb
            #     pdb.set_trace()
            best_hour = _calculate_best_hour(
                device_count[device],
                hourly_priority_scores,
                original_time,
                renewables_available,
                sim_start,
                task,
                valid_hours,
                weights,
            )
        if best_hour == original_time: 
            continue
        # if day%50 == 0 and task.task_id%100==0:
        #         logger.info(f"TIMING: task {task.task_id} find best hour {elapsed_t():.6f}s")

        # check shifting increases the metric
        # with time_this_chunk_of_code() as elapsed_t:
        metric_before_shift = (
            renewables_used_directly.loc[original_time]
            + renewables_used_directly.loc[best_hour]
        )
        metric_after_shift = (
            ((renewables_available.loc[original_time] + power) > 0)
            * (total_load[original_time] - power)
            + ((renewables_available.loc[original_time] + power) < 0)
            * (renewables_produced[original_time])
            + ((renewables_available.loc[best_hour] - power) > 0)
            * (total_load[best_hour] + power)
            + ((renewables_available.loc[best_hour] - power) < 0)
            * (renewables_produced[best_hour])
        )
        # if day%50 == 0 and task.task_id%100==0:
        #         logger.info(f"TIMING: task {task.task_id} find metric change {elapsed_t():.6f}s")

        # with time_this_chunk_of_code() as elapsed_t:
        if (metric_after_shift - metric_before_shift) > -0.20 * power:
            # assign the task
            device_count[device].loc[best_hour] += 1
            device_count[device].loc[original_time] -= 1
            hourly_priority_scores.loc[best_hour] += task.priority_score * abs(
                best_hour - original_time
            )
            hourly_priority_scores.loc[original_time] -= device.priority
            renewables_available.loc[best_hour] -= power
            renewables_available.loc[original_time] += power
            total_load.loc[best_hour] += power
            total_load.loc[original_time] -= power
            renewables_used_directly: pd.Series = (
                renewables_available > 0
            ) * total_load.loc[sim_start:sim_end].values + (
                renewables_available < 0
            ) * renewables_produced.loc[
                sim_start:sim_end
            ].values

            if day == 0:  # frame for animation
                _append_animation_frame(
                    day1_loads, frames, frames_subtitle, device, original_time, best_hour, sim_start
                )
                renewables_used_directly_metric.append(
                    renewables_used_directly_metric[-1]
                    + (metric_after_shift - metric_before_shift)
                )
        else:
            continue
        # if day%50 == 0 and task.task_id%100==0:
        #     logger.info(f"TIMING: task {task.task_id} assigning (or not) took {elapsed_t():.6f}s")


    # construct device-specific hourly usages
    devices = set(device for device in ownerships)
    device_hourly_loads_shifted: dict[str, pd.DataFrame] = {}
    for d in devices:
        p = d.electric_power
        n = d.name
        device_hourly_loads_shifted[n] = (device_count[d] * p).to_frame()
        # else:  # unshiftable devices
        #     d_hourly_usage = device_hourly_usage[d].iloc[hours, 0].astype(int)
        #     device_hourly_loads_shifted[n] = (d_hourly_usage * p).to_frame()

    return (device_hourly_loads_shifted,)  # by device
    # total loads over time_period by DemandType
