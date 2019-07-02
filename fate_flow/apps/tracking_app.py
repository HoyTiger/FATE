#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
from fate_flow.utils.api_utils import get_json_result
from fate_flow.settings import logger
from flask import Flask, request
from fate_flow.manager.tracking import Tracking
from fate_flow.db.db_models import Job
from fate_flow.utils import job_utils, data_utils
from google.protobuf import json_format
from fate_flow.storage.fate_storage import FateStorage

manager = Flask(__name__)


@manager.errorhandler(500)
def internal_server_error(e):
    logger.exception(e)
    return get_json_result(retcode=100, retmsg=str(e))


@manager.route('/component/metrics', methods=['post'])
def component_metrics():
    request_data = request.json
    fill_request_data(request_data)
    tracker = Tracking(job_id=request_data['job_id'], component_name=request_data['component_name'],
                       role=request_data['role'], party_id=request_data['party_id'])
    metrics = tracker.get_metric_list()
    if metrics:
        return get_json_result(retcode=0, retmsg='success', data=metrics)
    else:
        return get_json_result(retcode=101, retmsg='error')


@manager.route('/component/metric_data', methods=['post'])
def component_metric_data():
    request_data = request.json
    fill_request_data(request_data)
    tracker = Tracking(job_id=request_data['job_id'], component_name=request_data['component_name'],
                       role=request_data['role'], party_id=request_data['party_id'])
    metric_data = tracker.read_metric_data(metric_namespace=request_data['metric_namespace'],
                                           metric_name=request_data['metric_name'])
    if metric_data:
        metric_data_list = [(metric.key, metric.value) for metric in metric_data]
        metric_data_list.sort(key=lambda x: x[0])
        return get_json_result(retcode=0, retmsg='success', data=metric_data_list)
    else:
        return get_json_result(retcode=101, retmsg='error')


@manager.route('/component/parameters', methods=['post'])
def component_parameters():
    request_data = request.json
    fill_request_data(request_data)
    job_id = request_data.get('job_id', '')
    jobs = Job.select(Job.f_dsl, Job.f_runtime_conf).where(Job.f_job_id == job_id, Job.f_is_initiator == 1)
    if jobs:
        job_dsl_path, job_runtime_conf_path = job_utils.get_job_conf_path(job_id=job_id)
        job_dsl_parser = job_utils.get_job_dsl_parser(job_id=job_id, job_dsl_path=job_dsl_path,
                                                      job_runtime_conf_path=job_runtime_conf_path)
        component = job_dsl_parser.get_component_info(request_data['component_name'])
        parameters = component.get_role_parameters()
        for role, partys_parameters in parameters.items():
            for party_parameters in partys_parameters:
                if party_parameters.get('local', {}).get('role', '') == request_data['role'] and party_parameters.get(
                        'local', {}).get('party_id', '') == request_data['party_id']:
                    return get_json_result(retcode=0, retmsg='success', data=party_parameters)
        else:
            return get_json_result(retcode=102, retmsg='can not found this component parameters')
    else:
        return get_json_result(retcode=101, retmsg='can not found this job')


@manager.route('/component/output/model', methods=['post'])
def component_output_model():
    request_data = request.json
    fill_request_data(request_data)
    tracker = Tracking(job_id=request_data['job_id'], component_name=request_data['component_name'],
                       role=request_data['role'], party_id=request_data['party_id'], model_id='jarvis_test')
    output_model = tracker.get_output_model()
    output_model_json = {}
    for buffer_name, buffer_object in output_model.items():
        if buffer_name.endswith('Param'):
            output_model_json = json_format.MessageToDict(buffer_object)
    if output_model_json:
        return get_json_result(retcode=0, retmsg='success', data=output_model_json, meta=tracker.get_output_model_meta())
    else:
        return get_json_result(retcode=101, retmsg='can not found model')


@manager.route('/component/output/data', methods=['post'])
def component_output_data():
    request_data = request.json
    fill_request_data(request_data)
    tracker = Tracking(job_id=request_data['job_id'], component_name=request_data['component_name'],
                       role=request_data['role'], party_id=request_data['party_id'])
    output_data_table = tracker.get_output_data_table('train')
    output_data = []
    num = 10
    for k, v in output_data_table.collect():
        if num == 0:
            break
        l = [k]
        l.extend(data_utils.dataset_to_list(v.features))
        output_data.append(l)
        num -= 1
    if output_data:
        output_data_meta = FateStorage.get_data_table_meta_by_instance(output_data_table)
        return get_json_result(retcode=0, retmsg='success', data=output_data, meta=output_data_meta)
    else:
        return get_json_result(retcode=101, retmsg='no data')


def fill_request_data(request_data):
    request_data['role'] = request_data.get('role', 'guest')
    request_data['party_id'] = int(request_data.get('party_id', 9999))
