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
import shutil
import math
import glob
import json
import logging
import datetime
import time
import tarfile
import uuid

LOG = logging.getLogger('ibmcloud_test_harness_build')
LOG.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGSTREAM = logging.StreamHandler(sys.stdout)
LOGSTREAM.setFormatter(FORMATTER)
LOG.addHandler(LOGSTREAM)

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

TEMPLATE_DIR = "%s/templates" % SCRIPT_DIR
QUEUE_DIR = "%s/queued_tests" % SCRIPT_DIR

CONFIG_FILE = "%s/builder-config.json" % SCRIPT_DIR
CONFIG = {}


def licenses_available():
    if os.path.exists(CONFIG['license_file']):
        return sum(1 for line in open(CONFIG['license_file']))


def get_license():
    if os.path.exists(CONFIG['license_file']) and \
       os.stat(CONFIG['license_file']).st_size > 0:
        with open(CONFIG['license_file'], 'r+') as f:
            firstLine = f.readline()
            while len(firstLine) < 5:
                firstLine = f.readline()
            data = f.read()
            f.seek(0)
            f.write(data)
            f.truncate()
        return firstLine.strip()
    else:
        return ''


def region_from_zone(zone):
    parts = zone.split('-')
    return "%s-%s" % (parts[0], parts[1])


def get_template_types():
    os.chdir(TEMPLATE_DIR)
    templates = []
    for file in glob.glob("*.gz"):
        templates.append(os.path.basename(file).split('.')[0])
    os.chdir(SCRIPT_DIR)
    return templates


def build_utility():
    zone_resources = {}
    with open(CONFIG['zone_resources_file'], 'r') as zrf:
        zone_resources = json.load(zrf)
    zones = os.listdir(QUEUE_DIR)
    test_map = {}
    for zone in zones:
        if zone in CONFIG['active_zones']:
            if not zone in test_map:
                test_map[zone] = {'test_count': 0}
    number_of_active_zones = len(test_map)
    number_per_zone = CONFIG['utility_pool_tests_per_zone']
    total_tests = 0
    total_zones = 0
    for zone in zones:
        if zone in CONFIG['active_zones']:
            LOG.info('creating tests in zone: %s' % zone)
            test_map[zone]['test_to_create'] = number_per_zone
            zone_dir = os.path.join(QUEUE_DIR, zone)
            images = os.listdir(zone_dir)
            total_zones = total_zones + 1
            LOG.info('each images (there are %d) will be tested %d times', len(images), number_per_zone)
            while test_map[zone]['test_to_create'] > 0:
                for image in images:
                    image_eligible = False
                    for match in CONFIG['active_images']:
                        if image.find(match) > 0:
                            image_eligible = True
                    if image_eligible:
                        image_dir = os.path.join(zone_dir, image)
                        size = ''
                        for sstr in CONFIG['profile_selection']:
                            if image.find(sstr) > 0:
                                size = CONFIG['profile_selection'][sstr]                     
                        temp_types = os.listdir(image_dir)
                        for temp_type in temp_types:
                            temp_dir = os.path.join(image_dir, temp_type)
                            template = "%s/%s.tar.gz" % (TEMPLATE_DIR,
                                                         os.path.basename(temp_type))
                            # LOG.debug('creating a test: %s - %s - %s', zone, image, temp_type)
                            test_id = str(uuid.uuid4())
                            test_dir = os.path.join(temp_dir, test_id)
                            # LOG.info('creating test: %s' % test_dir)
                            os.mkdir(test_dir)
                            test_archive = tarfile.open(template)
                            test_archive.extractall(test_dir)
                            test_archive.close()
                            var_template = {}
                            with open(os.path.join(test_dir, 'variables.json'), 'r') as vj:
                                var_template = json.load(vj)
                            var_json_file = os.path.join(
                                test_dir, 'test_vars.json')
                            var_tf_file = os.path.join(
                                test_dir, 'test_vars.tfvars')
                            var_tf_content = "%s = \"%s\"\n" % (
                                'test_type', temp_type)
                            var_to_write = {'test_type': temp_type}
                            var_to_write['license_type'] = "utilitypool"
                            var_tf_content += "license_type = \"utilitypool\"\n"
                            var_to_write['license_host'] = CONFIG['zone_license_hosts'][zone]['license_host']
                            var_tf_content += "license_host = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_host']
                            var_to_write['license_username'] = CONFIG['zone_license_hosts'][zone]['license_username']
                            var_tf_content += "license_username = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_username']
                            var_to_write['license_password'] = CONFIG['zone_license_hosts'][zone]['license_password']
                            var_tf_content += "license_password = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_password']
                            var_to_write['license_pool'] = CONFIG['zone_license_hosts'][zone]['license_pool']
                            var_tf_content += "license_pool = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_pool']
                            var_to_write['license_sku_keyword_1'] = CONFIG['zone_license_hosts'][zone]['license_sku_keyword_1']
                            var_tf_content += "license_sku_keyword_1 = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_sku_keyword_1']
                            var_to_write['license_unit_of_measure'] = CONFIG['zone_license_hosts'][zone]['license_unit_of_measure']
                            var_tf_content += "license_unit_of_measure = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_unit_of_measure']
                            if CONFIG['zone_license_hosts'][zone]['license_sku_keyword_2']:
                                var_to_write['license_sku_keyword_2'] = CONFIG['zone_license_hosts'][zone]['license_sku_keyword_2']
                                var_tf_content += "license_sku_keyword_2 = \"%s\"\n" % CONFIG['zone_license_hosts'][zone]['license_sku_keyword_2']
                            if 'global_ssh_key' in CONFIG and CONFIG['global_ssh_key']:
                                var_to_write['ssh_key_name'] = CONFIG['global_ssh_key']
                                var_tf_content += "ssh_key_name = \"%s\"\n" % CONFIG['global_ssh_key']
                                   
                            for v in var_template:
                                if v['test_variable'] == 'api_key':
                                    var_to_write[v['variable_name']
                                                ] = CONFIG['api_key']
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], CONFIG['api_key'])
                                if v['test_variable'] == 'region':
                                    var_to_write[v['variable_name']
                                                ] = region_from_zone(zone)
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], region_from_zone(zone))
                                if v['test_variable'] == 'test_id':
                                    var_to_write[v['variable_name']
                                                ] = "t-%s" % test_id
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], "t-%s" % test_id)
                                if v['test_variable'] == 'image_name':
                                    var_to_write[v['variable_name']] = image
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], image)
                                if v['test_variable'] == 'size':
                                    var_to_write[v['variable_name']] = size
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], size)
                                if v['test_variable'] == 'admin_password':
                                    var_to_write[v['variable_name']
                                                ] = 'f5C0nfig'
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], 'f5C0nfig')
                                if 'global_ssh_key' not in CONFIG or not CONFIG['global_ssh_key']:
                                    if v['test_variable'] == 'ssh_key_name':
                                        var_to_write[v['variable_name']
                                                    ] = zone_resources[zone]['ssh_key_name']['value']
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], zone_resources[zone]['ssh_key_name']['value'])
                                if v['test_variable'] == 'f5_management_id':
                                    var_to_write[v['variable_name']
                                                ] = zone_resources[zone]['f5_management_id']['value']
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], zone_resources[zone]['f5_management_id']['value'])
                                if v['test_variable'] == 'f5_cluster_id':
                                    var_to_write[v['variable_name']
                                                ] = zone_resources[zone]['f5_cluster_id']['value']
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], zone_resources[zone]['f5_cluster_id']['value'])
                                if v['test_variable'] == 'f5_internal_id':
                                    var_to_write[v['variable_name']
                                                ] = zone_resources[zone]['f5_internal_id']['value']
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], zone_resources[zone]['f5_internal_id']['value'])
                                if v['test_variable'] == 'f5_external_id':
                                    var_to_write[v['variable_name']
                                                ] = zone_resources[zone]['f5_external_id']['value']
                                    var_tf_content += "%s = \"%s\"\n" % (
                                        v['variable_name'], zone_resources[zone]['f5_external_id']['value'])
                                if v['test_variable'] == 'report_finish_url':
                                    var_to_write[v['variable_name']] = "%s/stop/%s" % (
                                        CONFIG['report_service_base_url'], test_id)
                                    var_tf_content += "%s = \"%s\"\n" % (v['variable_name'], "%s/stop/%s" % (
                                        CONFIG['report_service_base_url'], test_id))
                                if v['test_variable'] == 'f5_hardcoded_sg':
                                    var_to_write[v['variable_name']] = CONFIG['zone_security_groups'][zone]
                                    var_tf_content += "%s = \"%s\"\n" % (v['variable_name'], CONFIG['zone_security_groups'][zone])
                            with open(var_json_file, 'w') as vj:
                                vj.write(json.dumps(
                                    var_to_write, sort_keys=True, indent=4, separators=(',', ': ')))
                            with open(var_tf_file, 'w') as vtf:
                                vtf.write(var_tf_content)
                            total_tests = total_tests + 1
                        test_map[zone]['test_to_create'] = test_map[zone]['test_to_create'] - 1
    LOG.info("%d total tests created in %d zones for %d images", total_tests, total_zones, len(CONFIG['active_images']))

def build_byol():
    zone_resources = {}
    with open(CONFIG['zone_resources_file'], 'r') as zrf:
        zone_resources = json.load(zrf)
    zones = os.listdir(QUEUE_DIR)
    num_licenses = licenses_available()
    test_map = {}
    for zone in zones:
        if zone in CONFIG['active_zones']:
            if not zone in test_map:
                test_map[zone] = {'test_count': 0}
    number_of_active_zones = len(test_map)
    number_per_zone = num_licenses / number_of_active_zones
    number_license_left = num_licenses % number_of_active_zones
    for zone in zones:
        if zone in CONFIG['active_zones']:
            test_map[zone]['test_to_create'] = number_per_zone
            zone_dir = os.path.join(QUEUE_DIR, zone)
            images = os.listdir(zone_dir)
            while test_map[zone]['test_to_create'] > 0:
                for image in images:
                    image_eligible = False
                    for match in CONFIG['active_images']:
                        if image.find(match) > 0:
                            image_eligible = True
                    if image_eligible:
                        image_dir = os.path.join(zone_dir, image)
                        size = ''
                        for sstr in CONFIG['profile_selection']:
                            if image.find(sstr) > 0:
                                size = CONFIG['profile_selection'][sstr]                     
                        temp_types = os.listdir(image_dir)
                        for temp_type in temp_types:
                            temp_dir = os.path.join(image_dir, temp_type)
                            template = "%s/%s.tar.gz" % (TEMPLATE_DIR,
                                                            os.path.basename(temp_type))
                            LOG.debug('creating a test: %s - %s - %s', zone, image, temp_type)
                            license = get_license()
                            if len(license) > 0:
                                test_id = str(uuid.uuid4())
                                test_dir = os.path.join(temp_dir, test_id)
                                LOG.info('creating test: %s' % test_dir)
                                os.mkdir(test_dir)
                                test_archive = tarfile.open(template)
                                test_archive.extractall(test_dir)
                                test_archive.close()
                                var_template = {}
                                with open(os.path.join(test_dir, 'variables.json'), 'r') as vj:
                                    var_template = json.load(vj)
                                var_json_file = os.path.join(
                                    test_dir, 'test_vars.json')
                                var_tf_file = os.path.join(
                                    test_dir, 'test_vars.tfvars')
                                var_tf_content = "%s = \"%s\"\n" % (
                                    'test_type', temp_type)
                                var_to_write = {'test_type': temp_type}
                                var_to_write['license_type'] = 'byol'
                                var_tf_content += "license_type = \"byol\"\n"
                                if 'global_ssh_key' in CONFIG and CONFIG['global_ssh_key']:
                                    var_to_write['ssh_key_name'] = CONFIG['global_ssh_key']
                                    var_tf_content += "ssh_key_name = \"%s\"\n" % CONFIG['global_ssh_key']
                                for v in var_template:
                                    if v['test_variable'] == 'api_key':
                                        var_to_write[v['variable_name']
                                                    ] = CONFIG['api_key']
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], CONFIG['api_key'])
                                    if v['test_variable'] == 'region':
                                        var_to_write[v['variable_name']
                                                    ] = region_from_zone(zone)
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], region_from_zone(zone))
                                    if v['test_variable'] == 'test_id':
                                        var_to_write[v['variable_name']
                                                    ] = "t-%s" % test_id
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], "t-%s" % test_id)
                                    if v['test_variable'] == 'image_name':
                                        var_to_write[v['variable_name']] = image
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], image)
                                    if v['test_variable'] == 'size':
                                        var_to_write[v['variable_name']] = size
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], size)
                                    if v['test_variable'] == 'byol_license_basekey':
                                        var_to_write[v['variable_name']
                                                    ] = license
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], license)
                                    if v['test_variable'] == 'admin_password':
                                        var_to_write[v['variable_name']
                                                    ] = 'f5C0nfig'
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], 'f5C0nfig')
                                    if 'global_ssh_key' not in CONFIG or not CONFIG['global_ssh_key']:
                                        if v['test_variable'] == 'ssh_key_name':
                                            var_to_write[v['variable_name']
                                                        ] = zone_resources[zone]['ssh_key_name']['value']
                                            var_tf_content += "%s = \"%s\"\n" % (
                                                v['variable_name'], zone_resources[zone]['ssh_key_name']['value'])
                                    if v['test_variable'] == 'f5_management_id':
                                        var_to_write[v['variable_name']
                                                    ] = zone_resources[zone]['f5_management_id']['value']
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], zone_resources[zone]['f5_management_id']['value'])
                                    if v['test_variable'] == 'f5_cluster_id':
                                        var_to_write[v['variable_name']
                                                    ] = zone_resources[zone]['f5_cluster_id']['value']
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], zone_resources[zone]['f5_cluster_id']['value'])
                                    if v['test_variable'] == 'f5_internal_id':
                                        var_to_write[v['variable_name']
                                                    ] = zone_resources[zone]['f5_internal_id']['value']
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], zone_resources[zone]['f5_internal_id']['value'])
                                    if v['test_variable'] == 'f5_external_id':
                                        var_to_write[v['variable_name']
                                                    ] = zone_resources[zone]['f5_external_id']['value']
                                        var_tf_content += "%s = \"%s\"\n" % (
                                            v['variable_name'], zone_resources[zone]['f5_external_id']['value'])
                                    if v['test_variable'] == 'report_finish_url':
                                        var_to_write[v['variable_name']] = "%s/stop/%s" % (
                                            CONFIG['report_service_base_url'], test_id)
                                        var_tf_content += "%s = \"%s\"\n" % (v['variable_name'], "%s/stop/%s" % (
                                            CONFIG['report_service_base_url'], test_id))
                                    if v['test_variable'] == 'f5_hardcoded_sg':
                                        var_to_write[v['variable_name']] = CONFIG['zone_security_groups'][zone]
                                        var_tf_content += "%s = \"%s\"\n" % (v['variable_name'], CONFIG['zone_security_groups'][zone])
                                with open(var_json_file, 'w') as vj:
                                    vj.write(json.dumps(
                                        var_to_write, sort_keys=True, indent=4, separators=(',', ': ')))
                                with open(var_tf_file, 'w') as vtf:
                                    vtf.write(var_tf_content)
                                test_map[zone]['test_to_create'] = test_map[zone]['test_to_create'] - 1


def build_tests():
    if CONFIG['license_type'] == 'byol':
        num_licenses = licenses_available()
        LOG.info('%d BYOL licenses available for test queuing', num_licenses)
        while num_licenses > 0:
            build_byol()
            num_licenses = licenses_available()
    if CONFIG['license_type'] == 'utilitypool':
        build_utility()


def initialize():
    global CONFIG
    os.makedirs(QUEUE_DIR, exist_ok=True)
    config_json = ''
    with open(CONFIG_FILE, 'r') as cf:
        config_json = cf.read()
    config = json.loads(config_json)
    if not config['license_file'].startswith('/'):
        config['license_file'] = "%s/%s" % (SCRIPT_DIR, config['license_file'])
    if not config['f5_images_catalog_file'].startswith('/'):
        config['f5_images_catalog_file'] = "%s/%s" % (
            SCRIPT_DIR, config['f5_images_catalog_file'])
    if not config['zone_resources_file'].startswith('/'):
        config['zone_resources_file'] = "%s/%s" % (
            SCRIPT_DIR, config['zone_resources_file'])
    images_json = ''
    with open(config['f5_images_catalog_file'], 'r') as imf:
        images_json = imf.read()
    images = json.loads(images_json)
    for zone in config['active_zones']:
        zone_queue = "%s/%s" % (QUEUE_DIR, zone)
        os.makedirs(zone_queue, exist_ok=True)
        region = region_from_zone(zone)
        if region in images:
            for image in images[region]:
                image_queue = "%s/%s" % (zone_queue, image['image_name'])
                os.makedirs(image_queue, exist_ok=True)
                template_types = get_template_types()
                for template_type in template_types:
                    template_queue = "%s/%s" % (image_queue, template_type)
                    os.makedirs(template_queue, exist_ok=True)
    CONFIG = config


if __name__ == "__main__":
    START_TIME = time.time()
    LOG.debug('process start time: %s', datetime.datetime.fromtimestamp(
        START_TIME).strftime("%A, %B %d, %Y %I:%M:%S"))
    initialize()
    ERROR_MESSAGE = ''
    ERROR = False
    build_tests()
    STOP_TIME = time.time()
    DURATION = STOP_TIME - START_TIME
    LOG.debug(
        'process end time: %s - ran %s (seconds)',
        datetime.datetime.fromtimestamp(
            STOP_TIME).strftime("%A, %B %d, %Y %I:%M:%S"),
        DURATION
    )
