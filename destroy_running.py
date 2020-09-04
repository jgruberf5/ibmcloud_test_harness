#!/usr/bin/env python3

# coding=utf-8
# pylint: disable=broad-except,unused-argument,line-too-long, unused-variable
# Copyright (c) 2016-2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import sys
import json
import logging
import datetime
import time
import requests
import concurrent.futures
import threading
import shutil
import python_terraform as pt
import random

LOG = logging.getLogger('ibmcloud_test_harness_destroy_running')
LOG.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGSTREAM = logging.StreamHandler(sys.stdout)
LOGSTREAM.setFormatter(FORMATTER)
LOG.addHandler(LOGSTREAM)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

QUEUE_DIR = "%s/queued_tests" % SCRIPT_DIR
RUNNING_DIR = "%s/running_tests" % SCRIPT_DIR
COMPLETE_DIR = "%s/completed_tests" % SCRIPT_DIR
ERRORED_DIR = "%s/errored_tests" % SCRIPT_DIR

CONFIG_FILE = "%s/runners-config.json" % SCRIPT_DIR
CONFIG = {}

MY_PID = None


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def stop_report(test_id, results):
    headers = {
        'Content-Type': 'application/json'
    }
    requests.post("%s/stop/%s" % (CONFIG['report_service_base_url'], test_id),
                  headers=headers, data=json.dumps(results))


def destroy_test(test_path):
    LOG.info("destroying %s", test_path)
    test_id = os.path.basename(test_path)
    results = {"test_aborted": "forced destroyed"}
    stop_report(test_id, results)
    tf = pt.Terraform(working_dir=test_path, var_file='test_vars.tfvars')
    (rc, out, err) = tf.init()
    results = {'terraform_failed': "init failure: %s" % err}
    LOG.info('destroying cloud resources for test %s', test_id)
    (rc, out, err) = tf.destroy()
    if rc > 0:
        LOG.error(
            'could not destroy test: %s: %s. Manually fix.', test_id, err)
    else:
        shutil.rmtree(test_path)


def build_pool():
    pool = []
    for rt in os.listdir(RUNNING_DIR):
        pool.append(os.path.join(RUNNING_DIR, rt))
    return pool


def runner():
    test_pool = build_pool()
    random.shuffle(test_pool)
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG['thread_pool_size']) as executor:
        for test_path in test_pool:
            executor.submit(destroy_test, test_path=test_path)


def initialize():
    global MY_PID, CONFIG
    MY_PID = os.getpid()
    os.makedirs(QUEUE_DIR, exist_ok=True)
    os.makedirs(RUNNING_DIR, exist_ok=True)
    os.makedirs(COMPLETE_DIR, exist_ok=True)
    config_json = ''
    with open(CONFIG_FILE, 'r') as cf:
        config_json = cf.read()
    config = json.loads(config_json)
    # intialize missing config defaults
    CONFIG = config


if __name__ == "__main__":
    START_TIME = time.time()
    LOG.debug('process start time: %s', datetime.datetime.fromtimestamp(
        START_TIME).strftime("%A, %B %d, %Y %I:%M:%S"))
    initialize()
    runner()
    ERROR_MESSAGE = ''
    ERROR = False

    STOP_TIME = time.time()
    DURATION = STOP_TIME - START_TIME
    LOG.debug(
        'process end time: %s - ran %s (seconds)',
        datetime.datetime.fromtimestamp(
            STOP_TIME).strftime("%A, %B %d, %Y %I:%M:%S"),
        DURATION
    )
