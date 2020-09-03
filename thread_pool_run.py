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

LOG = logging.getLogger('ibmcloud_test_harness_run')
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

CONFIG_FILE = "%s/runners-config.json" % SCRIPT_DIR
CONFIG = {}

POOLED_JOBS = []

MY_PID = None

def check_pid(pid):        
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def start_report(test_id, start_data):
    headers = {
        'Content-Type': 'application/json'
    }
    requests.post("%s/start/%s" % (CONFIG['report_service_base_url'], test_id),
                  headers=headers, data=json.dumps(start_data))


def update_report(test_id, update_data):
    headers = {
        'Content-Type': 'application/json'
    }
    requests.put("%s/report/%s" % (CONFIG['report_service_base_url'], test_id),
                  headers=headers, data=json.dumps(update_data))


def stop_report(test_id, results):
    headers = {
        'Content-Type': 'application/json'
    }
    requests.post("%s/stop/%s" % (CONFIG['report_service_base_url'], test_id),
                  headers=headers, data=json.dumps(results))


def poll_report(test_id):
    end_time = time.time() + int(CONFIG['test_timeout'])
    while (end_time - time.time()) > 0:
        base_url = CONFIG['report_service_base_url']
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.get("%s/report/%s" % (base_url, test_id), headers=headers)
        if response.status_code < 400:
            data = response.json()
            if data['duration'] > 0:
                LOG.info('test run %s completed', test_id)
                return data
        seconds_left = int(end_time - time.time())
        LOG.debug('test_id: %s with %s seconds left', test_id, str(seconds_left))
        time.sleep(CONFIG['report_request_frequency'])
    return None


def run_test(test_dir, zone, image, ttype):
    test_id = os.path.basename(test_dir)
    LOG.info('running test %s' % test_id)
    start_data = {
        'zone': zone,
        'image_name': image,
        'type': ttype
    }
    start_report(test_id, start_data)
    tf = pt.Terraform(working_dir=test_dir, var_file='test_vars.tfvars')
    (rc, out, err) = tf.init()
    if rc > 0:
        results = {'terraform_failed': "init failure: %s" % err }
        stop_report(test_id, results)
    LOG.info('creating cloud resources for test %s', test_id)
    (rc, out, err) = tf.apply(dir_or_plan=False, skip_plan=True)
    if rc > 0:
        LOG.error('terraform failed for test: %s - %s', test_id, err)
        results = {'terraform_failed': "apply failure: %s" % err }
        stop_report(test_id, results)
    out = tf.output(json=True)
    now = datetime.datetime.utcnow()
    update_data = {
        'terraform_apply_result_code': rc,
        'terraform_output': out,
        'terraform_apply_completed_at': now.timestamp(),
        'terraform_apply_completed_at_readable': now.strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    update_report(test_id, update_data)
    results = poll_report(test_id)
    if not results:
        results = {"test timedout": "(%d seconds)" % int(CONFIG['test_timeout'])}
        stop_report(test_id, results)
    LOG.info('destroying cloud resources for test %s', test_id)
    (rc, out, err) = tf.destroy()
    if rc > 0:
        LOG.error('could not destroy test: %s: %s. Manually fix.', test_id, err)
    else:
        shutil.move(test_dir, os.path.join(COMPLETE_DIR, test_id))
    

def initialize_test_dir(test_path):
    test_dir = os.path.basename(test_path)
    test_path_parts = test_path.split(os.path.sep)
    zone = test_path_parts[(len(test_path_parts) - 4)]
    image = test_path_parts[(len(test_path_parts) - 3)]
    ttype = test_path_parts[(len(test_path_parts) - 2)]
    dest = os.path.join(RUNNING_DIR, test_dir)
    shutil.move(test_path, dest)
    return (zone, image, ttype, dest)


def build_pool():
    pool = []
    zones_dir = os.listdir(QUEUE_DIR)
    for zone in zones_dir:
        images_dir = os.path.join(QUEUE_DIR, zone)
        zone_images = os.listdir(images_dir)
        for zi in zone_images:
            tts_dir = os.path.join(images_dir, zi)
            tts = os.listdir(tts_dir)
            for tt in tts:
                tests_dir = os.path.join(tts_dir, tt)
                tests = os.listdir(tests_dir)
                for test in tests:
                    pool.append(os.path.join(tests_dir, test))
    return pool


def runner():
    test_pool = build_pool()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG['thread_pool_size']) as executor:
        for test_path in test_pool:
            (zone, image, ttype, test_dir) = initialize_test_dir(test_path)
            executor.submit(run_test, test_dir=test_dir, zone=zone, image=image, ttype=ttype)


def initialize():
    global MY_PID, CONFIG
    MY_PID = os.getpid()
    os.makedirs(QUEUE_DIR, exist_ok = True)
    os.makedirs(RUNNING_DIR, exist_ok = True)
    os.makedirs(COMPLETE_DIR, exist_ok = True)    
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