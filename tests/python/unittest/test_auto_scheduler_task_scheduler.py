# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
""" Test task scheduler """

import tempfile

import numpy as np

from tvm import auto_scheduler

from test_auto_scheduler_common import matmul_auto_scheduler_test


def test_task_scheduler_round_robin():
    tasks = []
    for n in [2, 4, 8]:
        tasks.append(auto_scheduler.create_task(matmul_auto_scheduler_test, (n, n, n), "llvm"))

    def objective_func(costs):
        return sum(costs)

    with tempfile.NamedTemporaryFile() as fp:
        log_file = fp.name
        num_trials_per_task = 2

        # Tune all tasks
        tune_option = auto_scheduler.TuningOptions(
            num_measure_trials=num_trials_per_task * len(tasks),
            num_measures_per_round=1,
            measure_callbacks=[auto_scheduler.RecordToFile(log_file)],
        )
        task_scheduler = auto_scheduler.TaskScheduler(tasks, objective_func, strategy="round-robin")
        task_scheduler.tune(tune_option, search_policy="sketch.random")

        # Check the result of round robin
        counters = {}
        for task in tasks:
            counters[task.workload_key] = 0

        for inp, res in auto_scheduler.load_records(log_file):
            counters[inp.task.workload_key] += 1

        for task in tasks:
            assert counters[task.workload_key] == num_trials_per_task

        # test continuous tuning (restoring the status)
        task_scheduler = auto_scheduler.TaskScheduler(
            tasks, objective_func, strategy="round-robin", load_log_file=log_file
        )
        tune_option = auto_scheduler.TuningOptions(
            num_measure_trials=len(tasks),
            num_measures_per_round=1,
        )
        task_scheduler.tune(tune_option, search_policy="sketch.random")


def test_task_scheduler_gradient():
    tasks = []
    for n in [2, 4]:
        tasks.append(auto_scheduler.create_task(matmul_auto_scheduler_test, (n, n, n), "llvm"))

    def objective_func(costs):
        return costs[0]

    with tempfile.NamedTemporaryFile() as fp:
        log_file = fp.name

        n_trials = 5

        # Tune all tasks
        tune_option = auto_scheduler.TuningOptions(
            num_measure_trials=n_trials,
            num_measures_per_round=1,
            measure_callbacks=[auto_scheduler.RecordToFile(log_file)],
        )
        task_scheduler = auto_scheduler.TaskScheduler(tasks, objective_func)

        # Forcely rewrite the initial values.
        # This can make this test more stable on the slow CI machines
        task_scheduler.best_costs = np.array([1e2, 1e-8])

        task_scheduler.tune(tune_option, search_policy="sketch.random")

        # Check the allocation results
        counters = {}
        for task in tasks:
            counters[task.workload_key] = 0

        for inp, res in auto_scheduler.load_records(log_file):
            counters[inp.task.workload_key] += 1

        assert counters[tasks[0].workload_key] == n_trials - 1
        assert counters[tasks[1].workload_key] == 1


if __name__ == "__main__":
    test_task_scheduler_round_robin()
    test_task_scheduler_gradient()
