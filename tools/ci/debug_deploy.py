#!/usr/bin/env python

import json
import os

import requests

def gh_request(method_name, url, body=None, accept=None):
    github_token = os.environ.get('GITHUB_TOKEN')

    kwargs = {
        'headers': {
            'Authorization': 'token {}'.format(github_token),
            'Accept': accept or 'application/vnd.github.v3+json'
        }
    }
    method = getattr(requests, method_name.lower())

    if body is not None:
        kwargs['json'] = body

    print 'Issuing request: {} {}'.format(method_name.upper(), url)
    print 'Request body: {}'.format(json.dumps(kwargs, indent=2))

    resp = method(url, **kwargs)

    resp.raise_for_status()

    resp_body = resp.json()
    print 'Response status code: {}'.format(resp.status_code)
    print 'Response body: {}'.format(json.dumps(resp_body, indent=2))

    return resp.json()

with open(os.environ['GITHUB_EVENT_PATH']) as handle:
    data = json.loads(handle.read())

print 'Event data: {}'.format(json.dumps(data, indent=2))

url_base = 'https://api.github.com/repos/web-platform-tests/wpt-actions-test'

gh_request(
  'GET',
  '{}/deployments/{}/statuses'.format(url_base, data['deployment']['id'])
)

gh_request(
  'POST',
  '{}/deployments/{}/statuses'.format(url_base, data['deployment']['id']),
  {
    'state': 'pending',
    'description': 'Waiting up to %d seconds for deployment %s to be available on %s',
    'environment_url': 'http://s92097608.onlinehome.us/tmp/submissions/gh-17'
  },
  'application/vnd.github.ant-man-preview+json'
)

gh_request(
  'GET',
  '{}/deployments/{}/statuses'.format(url_base, data['deployment']['id'])
)
