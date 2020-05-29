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
import shutil
import python_terraform as pt

LOG = logging.getLogger('ibmcloud_test_process_running')
LOG.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGSTREAM = logging.StreamHandler(sys.stdout)
LOGSTREAM.setFormatter(FORMATTER)
LOG.addHandler(LOGSTREAM)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
RUNNING_DIR = "%s/running_tests" % SCRIPT_DIR

CONFIG_FILE = "%s/builder-config.json" % SCRIPT_DIR
CONFIG = {}


def clean():
    if os.path.exists(RUNNING_DIR):
        test_dirs = os.listdir(RUNNING_DIR)
        left_over_tests = []
        for test_id in test_dirs:
            left_over_tests.append(test_id)
        report_url = "%s/report" % CONFIG['report_service_base_url']
        resp = requests.get(report_url)
        reports = resp.json()
        output = {}
        for test_id in reports:
            if 'test timedout' in reports[test_id]['results'] and \
                    test_id in left_over_tests:
                state = {}
                with open(os.path.join(RUNNING_DIR, test_id, 'terraform.tfstate'), 'r') as sf:
                    state = json.load(sf)
                for r in state['resources']:
                    if r['type'] == 'ibm_is_instance':
                        output[test_id] = {
                            'instance_id': r['instances'][0]['attributes']['id'],
                            'image_id': r['instances'][0]['attributes']['image'],
                            'status': r['instances'][0]['attributes']['status']
                        }
            else:
                test_dir = os.path.join(RUNNING_DIR, test_id)
                if os.path.exists(test_dir):
                    tf = pt.Terraform(working_dir=test_dir, var_file='test_vars.tfvars')
                    tf.init()
                    tf.destroy()
                    shutil.rmtree(test_dir)
        print(json.dumps(output, sort_keys=True,
              indent=4, separators=(',', ': ')))


def initialize():
    global CONFIG
    config_json = ''
    with open(CONFIG_FILE, 'r') as cf:
        config_json = cf.read()
    CONFIG = json.loads(config_json)


if __name__ == "__main__":
    START_TIME = time.time()
    LOG.debug('process start time: %s', datetime.datetime.fromtimestamp(
        START_TIME).strftime("%A, %B %d, %Y %I:%M:%S"))
    initialize()
    ERROR_MESSAGE = ''
    ERROR = False

    clean()

    STOP_TIME = time.time()
    DURATION = STOP_TIME - START_TIME
    LOG.debug(
        'process end time: %s - ran %s (seconds)',
        datetime.datetime.fromtimestamp(
            STOP_TIME).strftime("%A, %B %d, %Y %I:%M:%S"),
        DURATION
    )

