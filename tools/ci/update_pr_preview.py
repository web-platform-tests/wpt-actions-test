import json
import logging
import os
import subprocess
import sys

import requests

here = os.path.abspath(os.path.dirname(__file__))
wpt_root = os.path.abspath(os.path.join(here, os.pardir, os.pardir))

if not(wpt_root in sys.path):
    sys.path.append(wpt_root)

from tools.wpt.testfiles import get_git_cmd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Status(object):
    SUCCESS = 0
    FAIL = 1
    NEUTRAL = 78


def main():
    owner, repo = os.environ['GITHUB_REPOSITORY'].split('/', 1)

    with open(os.environ['GITHUB_EVENT_PATH']) as f:
        event = json.load(f)
        logger.info(json.dumps(event, indent=2))

    return Status.SUCCESS


if __name__ == '__main__':
    code = main()
    assert isinstance(code, int)
    sys.exit(code)
