#!/usr/bin/env python3
# sesheta-operator
# Copyright(C) 2019 Christoph Görn
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


"""Sesheta Operator."""

import os
import logging

import kopf
import kubernetes
import json

from kubernetes.client.rest import ApiException
from kopf import config as kopf_config

from thoth.common import init_logging


__version__ = "0.1.0-dev"

_DEBUG = os.getenv("CYBORG_DEBUG", True)


init_logging()
_LOGGER = logging.getLogger("thoth.cyborg.sesheta_operator")
logging.getLogger().setLevel(logging.DEBUG if _DEBUG else logging.INFO)



def _check_prerequisites():
    """Check if all the prerequisites are fulfilled."""

    # TODO check if the required Secret 'sesheta-pubsub-consumer' is present

    # TODO check if the required ImageStreamTag 'sesheta' is present

    return True

def _create_cron_job_data(name: str, namespace: str, env_vars={}) -> kubernetes.client.V1beta1CronJob:
    """Create a CronJob as a dict."""
    cron_job = kubernetes.client.V1beta1CronJob(api_version="batch/v1beta1", kind="CronJob")
    cron_job.metadata = kubernetes.client.V1ObjectMeta(namespace=namespace, generate_name=f"{name}-")
    cron_job.status = kubernetes.client.V1beta1CronJobStatus()
    cron_job.failed_jobs_history_limit = 4

    env_list = []
    for env_name, env_value in env_vars.items():
        env_list.append(kubernetes.client.V1EnvVar(name=env_name, value=env_value))
        
    containers = []
    containers.append(kubernetes.client.V1Container(name="standup", image="sesheta:latest", env=env_list))

    # TODO add resources!

    pod_spec = kubernetes.client.V1PodSpec(containers=containers, restart_policy="Never")

    pod_template = kubernetes.client.V1PodTemplateSpec()
    pod_template.spec = pod_spec

    job = kubernetes.client.V1JobSpec(template=pod_template)

    job_template = kubernetes.client.V1beta1JobTemplateSpec()
    job_template.spec = job

    cron_job.spec = kubernetes.client.V1beta1CronJobSpec(job_template=job_template, schedule="29 12 * * 1,3,5")

    return cron_job

@kopf.on.create("thoth-station.ninja", "v1alpha1", "cyborgs")
def create_cyborg(body, meta, spec, namespace, **kwargs):
    """handle on_create events."""
    sesheta_config_map = None
    sesheta_cron_job = None

    name = meta.get("name")
    
    _LOGGER.debug(f"on_create handler is called: {spec}")

    if not _check_prerequisites():
        raise kopf.HandlerRetryError("Cyborg's Secret or ConfigMap does not exist")

    config_map_data = {
        "metadata": {
            "generateName": f"cyborg-{name}-",
        },
        "data": {
            "sesheta-verbose": str(bool(spec.get("verbose"))),
            "scrum-space": spec.get("scrum").get("space"),
            "scrum-message": spec.get("scrum").get("message"),
            "scrum-url": spec.get("scrum").get("url"),
            "scrum-threadkey": spec.get("scrum").get("threadkey"),
    # FIXME                    "users-invited": spec.get("users").get("invited")
        }
    }
    # add ownerReferences for cascading delete
    kopf.adopt(config_map_data, owner=body)

    try:
        api = kubernetes.client.CoreV1Api()

        sesheta_config_map = api.create_namespaced_config_map(
            namespace=namespace,
            body=config_map_data
        )
    except ApiException as e:
        raise kopf.HandlerRetryError("Could not create required ConfigMap.", delay=60)


    try:
        cron_job_data = _create_cron_job_data(f"cyborg-{name}", namespace)
        _LOGGER.debug(cron_job_data)

        # add ownerReferences for cascading delete
        kopf.adopt(cron_job_data, owner=body)

        batch = kubernetes.client.BatchV1beta1Api()

        sesheta_cron_job = batch.create_namespaced_cron_job(
            namespace=namespace,
            body=cron_job_data,
            pretty=True,
        )

        _LOGGER.debug(sesheta_cron_job)

    except (ValueError, ApiException) as e:
        # let's delete the ConfigMap we have created before
        api = kubernetes.client.CoreV1Api()
        api.delete_namespaced_config_map(sesheta_config_map.metadata.name, namespace)
        _LOGGER.debug(f"deleted ConfigMap {sesheta_config_map.metadata.name}")
        _LOGGER.debug(f"The CronJob I would like to create: {cron_job_data}")

        raise kopf.HandlerRetryError("Could not create required CronJob.", delay=60)


    # TODO there is a better way for this?!
    if sesheta_config_map is not None:
        if sesheta_cron_job is not None:
            return {
                "children": [sesheta_config_map.metadata.uid, sesheta_cron_job.metadata.uid],
                "configMapName": sesheta_config_map.metadata.name
            }

    
@kopf.on.update('thoth-station.ninja', 'v1alpha1', 'cyborgs')
def update_cyborg(spec, old, new, diff, namespace, **kwargs):
    api = kubernetes.client.CoreV1Api()

    _LOGGER.info(f"on_update handler called: {spec}")

@kopf.on.delete('thoth-station.ninja', 'v1alpha1', 'cyborgs')
def delete_cyborg(spec, status, namespace, **kwargs):
    api = kubernetes.client.CoreV1Api()

    _LOGGER.info(f"on_delete handler called: {spec}")
