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


import logging

import kopf
import kubernetes
import yaml

from kubernetes.client.rest import ApiException


__version__ = "0.1.0-dev"


def _check_prerequisites():
    """Check if all the prerequisites are fulfilled."""

    # TODO check if the required Secret is present

    # TODO check if the required ImageStreamTag is present

    return True

@kopf.on.create("thoth-station.ninja", "v1alpha1", "cyborgs")
def create_cyborg(body, meta, spec, namespace, logger, **kwargs):
    """handle on_create events."""
    sesheta_configmap = None

    name = meta.get("name")
    logger.debug(body)
    logger.debug(meta)
    logger.debug(spec)
    
    logger.info(f"on_create handler is called: {spec}")

    if not _check_prerequisites():
        raise kopf.HandlerRetryError("Cyborg's Secret or ConfigMap does not exist")

    data = {
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
    kopf.adopt(data, owner=body)

    try:
        api = kubernetes.client.CoreV1Api()

        sesheta_configmap = api.create_namespaced_config_map(
            namespace=namespace,
            body=data
        )

        logger.debug(sesheta_configmap)
    except ApiException as e:
        raise kopf.HandlerRetryError("Could not create required ConfigMap.", delay=60)


    batch = kubernetes.client.BatchV1beta1Api()

    if sesheta_configmap is not None:
        return {'children': [sesheta_configmap.metadata.uid]}

    
@kopf.on.update('thoth-station.ninja', 'v1alpha1', 'cyborgs')
def update_cyborg(spec, status, namespace, logger, **kwargs):
    api = kubernetes.client.CoreV1Api()

    logger.info(f"on_update handler called: {spec}")

@kopf.on.delete('thoth-station.ninja', 'v1alpha1', 'cyborgs')
def delete_cyborg(spec, status, namespace, logger, **kwargs):
    api = kubernetes.client.CoreV1Api()

    logger.info(f"on_delete handler called: {spec}")
