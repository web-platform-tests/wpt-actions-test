#!/usr/bin/env python

import argparse
import json
import logging
import time

import requests

POLLING_PERIOD = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def request(method_name, url, body=None):
    github_token = os.environ.get('GITHUB_TOKEN')

    kwargs = {
        'headers': {
            'Authorization': 'token {}'.format(github_token),
            'Accept': 'application/vnd.github.machine-man-preview+json'
        }
    }
    method = getattr(requests, method_name.lower())

    logger.info('Issuing request: {} {}'.format(method_name.upper(), url))
    if body is not None:
        kwargs['json'] = body

    resp = method(url, **kwargs)

    resp.raise_for_status()

    return resp.json()

def is_deployed(host, deployment):
    response = requests.get(
        '{}/.git/worktrees/{}/HEAD'.format(host, deployment['environment'])
    )

    if response.status_code != 200:
        return False

    return response.text.strip() == deployment['sha']

def make_update_deployment(host, target, github_project):
    def update_deployment(state, description=''):
        url = '{}/repos/{}/deployments/{}/statuses'.format(
            host, github_project, deployment['id']
        )
        environment_url = '{}/submissions/{}/'.format(
            target, deployment['environment']
        )

        request('POST', url, {
            'state': state,
            'description': description,
            'environment_url': environment_url
        })

    return update_deployment

def main(host, target, github_project, timeout):
    with open(os.environ['GITHUB_EVENT_PATH']) as handle:
        deployment = json.loads(handle.read())['deployment']

    logger.info(json.dumps(data, indent=2))

    update_deployment = make_update_deployment(host, target, github_project)
    pr_number = int(deployment['environment'])

    update_deployment('in_progress')

    logger.info(
        'Waiting up to {} seconds for pull request #{} to be deployed to {}'.format(timeout, pr_number, target)
    )

    start = time.time()

    while not is_deployed(target, deployment):
        if time.time() - start > timeout:
            message = 'Deployment did not become available after {} seconds'.format(timeout)
            update_deployment('error', message)
            raise Exception(message)

        time.sleep(POLLING_PERIOD)

    update_deployment('success')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--github_project', required=True)
    parser.add_argument('--timeout', type=int, required=True)

    main(**vars(parser.parse_args()))
