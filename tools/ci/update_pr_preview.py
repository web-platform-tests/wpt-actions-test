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

        logger.info(
            'Searching for pull requests updated since "{}"'.format(window_start)
        )

        data = request('GET', url)

        if data['incomplete_results']:
            raise Exception('Incomplete results')

        logger.info('Found {} pull requests'.format(len(data['items'])))

        return data['items']

    def add_label(self, pull_request, name):
        number = pull_request['number']
        url = '{}/repos/{}/{}/issues/{}/labels'.format(
            self._host, self._org, self._repo, number
        )

        logger.info('Adding label "{}" for pull request #{}"'.format(number, name))

        request('POST', url, {'labels': [name]})

    def remove_label(self, pull_request, name):
        raise NotImplementedError()

    def create_deployment(self, ref):
        url = '{}/repos/{}/{}/deployments'.format(
            self._host, self._org, self._repo
        )

        logger.info('Creating deployment for "{}"'.format(ref))

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
        logger.info('Deleting ref "{}"'.format(refspec))

        with self._make_temp_repo() as temp_repo:
            subprocess.check_call(
                ['git', 'push', self._url, '--delete', 'refs/{}'.format(refspec)],
                cwd=temp_repo
            )

def is_open(pull_request):
    return not pull_request['closed_at']

def has_label(pull_request):
    for label in pull_request['labels']:
        if label['name'] == LABEL:
            return True
    return False

def should_be_mirrored(pull_request):
    return is_open(pull_request) and (
        pull_request['author_association'] == 'COLLABORATOR' or
        has_label(pull_request)
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

    for pull_request in pull_requests:
        logger.info('Processing pull request #{number}'.format(**pull_request))

        refspec_labeled = 'prs-labeled-for-preview/{number}'.format(**pull_request)
        refspec_open = 'prs-open/{number}'.format(**pull_request)
        revision_latest = remote.get_revision(
            'pull/{number}/head'.format(**pull_request)
        )
        revision_labeled = remote.get_revision(refspec_labeled)
        revision_open = remote.get_revision(refspec_open)

        if should_be_mirrored(pull_request):
            logger.info('Pull request should be mirrored')

            if not has_label(pull_request):
                project.add_label(pull_request, LABEL)

            if revision_labeled != latest_revision:
                remote.update_ref(refspec_open, latest_revision)

            if revision_open != latest_revision:
                remote.update_ref(refspec_labeled, latest_revision)
        else:
            logger.info('Pull request should not be mirrored')

            if has_label(pull_request):
                project.remove_label(pull_request, LABEL)

            if revision_labeled != None:
                remote.delete_ref(refspec_labeled)

            if revision_open != None and not is_open(pull_request):
                remote.delete_ref(refspec_labeled)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--organization', required=True)
    parser.add_argument('--repository', required=True)

    main(**vars(parser.parse_args()))
