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
from flask import Flask, request, send_file
import os
import io
import tarfile

from arch.api.utils.core import base64_decode
from fate_flow.driver.job_controller import JobController
from fate_flow.settings import stat_logger
from fate_flow.utils.api_utils import get_json_result
from fate_flow.utils import job_utils
from arch.api.utils.core import json_loads

manager = Flask(__name__)


@manager.errorhandler(500)
def internal_server_error(e):
    stat_logger.exception(e)
    return get_json_result(retcode=100, retmsg=str(e))


# User interface
@manager.route('/submit', methods=['POST'])
def submit_job():
    job_id, job_dsl_path, job_runtime_conf_path, model_info = JobController.submit_job(request.json)
    return get_json_result(job_id=job_id, data={'job_dsl_path': job_dsl_path,
                                                'job_runtime_conf_path': job_runtime_conf_path,
                                                'model_info': model_info
                                                })


@manager.route('/stop', methods=['POST'])
def stop_job():
    JobController.stop_job(job_id=request.json.get('job_id', ''))
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/query', methods=['POST'])
def query_job():
    jobs = job_utils.query_job(**request.json)
    if not jobs:
        return get_json_result(retcode=101, retmsg='find job failed')
    return get_json_result(retcode=0, retmsg='success', data=[job.to_json() for job in jobs])


@manager.route('/config', methods=['POST'])
def job_config():
    jobs = job_utils.query_job(**request.json)
    if not jobs:
        return get_json_result(retcode=101, retmsg='find job failed')
    else:
        job = jobs[0]
        response_data = dict()
        response_data['job_id'] = job.f_job_id
        response_data['dsl'] = json_loads(job.f_dsl)
        response_data['runtime_conf'] = json_loads(job.f_runtime_conf)
        response_data['model_info'] = JobController.gen_model_info(response_data['runtime_conf']['role'], response_data['runtime_conf']['job_parameters']['model_key'], job.f_job_id)
        return get_json_result(retcode=0, retmsg='success', data=response_data)


@manager.route('/log', methods=['get'])
def job_log():
    job_id = request.json.get('job_id', '')
    memory_file = io.BytesIO()
    tar = tarfile.open(fileobj=memory_file, mode='w:gz')
    job_log_dir = job_utils.get_job_log_directory(job_id=job_id)
    for root, dir, files in os.walk(job_log_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, job_log_dir)
            tar.add(full_path, rel_path)
    tar.close()
    memory_file.seek(0)
    return send_file(memory_file, attachment_filename='job_{}_log.tar.gz'.format(job_id), as_attachment=True)

# Scheduling interface
@manager.route('/<job_id>/<role>/<party_id>/create', methods=['POST'])
def create_job(job_id, role, party_id):
    JobController.update_job_status(job_id=job_id, role=role, party_id=int(party_id), job_info=request.json,
                                    create=True)
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/<job_id>/<role>/<party_id>/status', methods=['POST'])
def job_status(job_id, role, party_id):
    JobController.update_job_status(job_id=job_id, role=role, party_id=int(party_id), job_info=request.json,
                                    create=False)
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/<job_id>/<role>/<party_id>/<model_id>/save/pipeline', methods=['POST'])
def save_pipeline(job_id, role, party_id, model_id):
    JobController.save_pipeline(job_id=job_id, role=role, party_id=party_id, model_key=base64_decode(model_id))
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/<job_id>/<role>/<party_id>/kill', methods=['POST'])
def kill_job(job_id, role, party_id):
    JobController.kill_job(job_id=job_id, role=role, party_id=int(party_id),
                           job_initiator=request.json.get('job_initiator', {}))
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/<job_id>/<role>/<party_id>/clean', methods=['POST'])
def clean(job_id, role, party_id):
    JobController.clean_job(job_id=job_id, role=role, party_id=party_id)
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/<job_id>/<component_name>/<task_id>/<role>/<party_id>/run', methods=['POST'])
def run_task(job_id, component_name, task_id, role, party_id):
    task_data = request.json
    task_data['request_url_without_host'] = request.url.lstrip(request.host_url)
    JobController.start_task(job_id, component_name, task_id, role, party_id, request.json)
    return get_json_result(retcode=0, retmsg='success')


@manager.route('/<job_id>/<component_name>/<task_id>/<role>/<party_id>/status', methods=['POST'])
def task_status(job_id, component_name, task_id, role, party_id):
    JobController.update_task_status(job_id, component_name, task_id, role, party_id, request.json)
    return get_json_result(retcode=0, retmsg='success')