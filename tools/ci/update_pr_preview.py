#!/usr/bin/env python

# total_count: number
# incomplete_results: boolean
# items: array

import argparse
import contextlib
import json
import logging
import subprocess
import shutil
import sys
import tempfile
import time

import requests

FIVE_MINUTES = 400 * 60
API_RATE_LIMIT_THRESHOLD = 0.2
LABEL = 'pull-request-has-preview'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def request(method_name, url, body=None):
    #github_token = os.environ.get('GITHUB_TOKEN')

    kwargs = {
        'headers': {
            #'Authorization': 'token {}'.format(github_token),
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

class Project(object):
    def __init__(self, host, org, repo):
        self._host = host
        self._org = org
        self._repo = repo

    def get_pull_requests(self, updated_since):
        window_start = time.strftime('%Y-%m-%dT%H:%M:%SZ', updated_since)
        url = '{}/search/issues?q=repo:{}/{}+is:pr+updated:>{}'.format(
            self._host, self._org, self._repo, window_start
        )
        data = request('GET', url)
        if data['incomplete_results']:
            raise Exception('Incomplete results')

        return data['items']

    def add_label(self, pull_request_number, name):
        url = '{}/repos/{}/{}/issues/{}/labels'.format(
            self._host, self._org, self._repo, pull_request_number
        )
        request('POST', url, {'labels': [name]})

    def create_deployment(self, ref):
        url = '{}/repos/{}/{}/deployments'.format(
            self._host, self._org, self._repo
        )
        request('POST', url, {'ref': ref})

class Remote(object):
    def __init__(self, url):
        self._url = url

    @contextlib.contextmanager
    def _make_temp_repo(self):
        '''Some sub-commands of the git CLI only function in the context of a
        valid git repository (even if they do not involve any local objects).
        This context manager creates a temporary empty repository so those
        commands can be executed successfully and without fetching from any
        remote.'''
        directory = tempfile.mkdtemp()
        subprocess.check_call(['git', 'init'], cwd=directory)
        try:
            yield directory
        finally:
            shutil.rmtree(directory)

    def get_revision(self, refspec):
        output = subprocess.check_output([
            'git',
            'ls-remote',
            self._url,
            'refs/{}'.format(refspec)
        ])

        if not output:
            return None

        return output.split()[0]

    def update_ref(self, refspec, revision):
        raise NotImplementedError()

    def delete_ref(self, refspec):
        with self._make_temp_repo() as temp_repo:
            subprocess.check_call(
                ['git', 'push', self._url, '--delete', 'refs/{}'.format(refspec)],
                cwd=temp_repo
            )

def main(host, organization, repository):
    # > Accessing this endpoint does not count against your REST API rate limit.
    #
    # https://developer.github.com/v3/rate_limit/
    limits = request('GET', 'https://api.github.com/rate_limit')

    for name, values in limits['resources'].items():
        remaining = values['remaining']
        limit = values['limit']

        logger.info('Limit for "{}": {}/{}'.format(name, remaining, limit))

        if limit and float(remaining) / limit < API_RATE_LIMIT_THRESHOLD:
            logger.error('Exiting to avoid GitHub.com API request throttling.')
            sys.exit(1)

    project = Project(host, organization, repository)
    remote = Remote('git@github.com:web-platform-tests/wpt.git')
    pull_requests = project.get_pull_requests(
        time.gmtime(time.time() - FIVE_MINUTES)
    )

    logger.info(
        'Found {} pull requests modified in the past {} seconds'.format(
            len(pull_requests), FIVE_MINUTES
        )
    )

    for pull_request in pull_requests:
        logger.info('Processing pull request #{number}'.format(**pull_request))

        has_label = any([
            label['name'] == LABEL for label in pull_request['labels']
        ])
        refspec_labeled = 'prs-labeled-for-preview/{number}'.format(**pull_request)
        refspec_open = 'prs-open/{number}'.format(**pull_request)
        revision_labeled = remote.get_revision(refspec_labeled)

        if pull_request['author_association'] != 'COLLABORATOR' and not has_label:
            if revision_labeled:
                logger.info(
                    'Removing ref "{}" (was {})'.format(refspec_labeled, revision_labeled)
                )
                remote.delete_ref(refspec_labeled)
            else:
                logger.info('No label and submitted by non-collaborator. Skipping.')

            continue

        if not has_label:
            logger.info('Automatically assigning GitHub pull request label')
            project.add_label(pull_request['number'], LABEL)

        revision_open = remote.get_revision(refspec_open)

        if pull_request['closed_at']:
            logger.info('Pull request is closed.')

            if revision_open:
                logger.info(
                    'Removing ref "{}" (was {})'.format(refspec_open, revision_open)
                )
                remote.delete_ref(refspec_open)

            continue

        latest_revision = remote.get_revision('pull/{number}/head'.format(**pull_request))

        if revision_labeled != latest_revision:
            logger.info(
                'Updating ref "{}" to {}'.format(refspec_labeled, latest_revision)
            )
            remote.update_ref(refspec_labeled, latest_revision)

            logger.info('Creating GitHub Deployment')
            project.create_deployment(latest_revision)

        if revision_open != latest_revision:
            logger.info(
                'Updating ref "{}" to {}'.format(refspec_open, latest_revision)
            )
            remote.update_ref(refspec_open, latest_revision)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--organization', required=True)
    parser.add_argument('--repository', required=True)

    main(**vars(parser.parse_args()))
