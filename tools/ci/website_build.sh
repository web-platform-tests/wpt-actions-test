#!/bin/bash

set -x

neutral_status=78
source_revision=$(git rev-parse HEAD)
# The token available in the `GITHUB_TOKEN` variable may be used to push to the
# repository, but GitHub Pages will not rebuild the website in response to such
# events. Use an access token generated for the project's machine user,
# wpt-pr-bot.
#
# https://help.github.com/en/articles/generic-jekyll-build-failures
remote_url=https://${DEPLOY_TOKEN}@github.com/web-platform-tests/wpt-actions-test.git

function json_property {
  cat ${1} | \
    python -c "import json, sys; print json.load(sys.stdin).get(\"${2}\", \"\")"
}

function is_pull_request {
  test -n $(json_property ${GITHUB_EVENT_PATH} pull_request)
}

function targets_master {
  test $(json_property ${GITHUB_EVENT_PATH} ref) == '/refs/heads/master'
}

function modifies_relevant_files {
  base_revision=$(json_property ${GITHUB_EVENT_PATH} before)

  git diff --name-only ${base_revision} | \
    grep -E --silent '^(docs|tools)/'
}

if is_pull_request ; then
  echo Submission comes from a pull request. Exiting without building.

  exit ${neutral_status}
fi

if ! targets_master ; then
  echo Submission does not target the 'master' branch. Exiting without building.

  exit ${neutral_status}
fi

if ! modifies_relevant_files ; then
  echo No files related to the website have been modified. Exiting without
  echo building.

  exit ${neutral_status}
fi

git config --global user.email "wpt-pr-bot@users.noreply.github.com"
git config --global user.name "wpt-pr-bot"

cd docs

pip install -r requirements.txt

make html

cd _build/html

git init

git fetch --depth 1 ${remote_url}

git checkout FETCH_HEAD

git rm -r .

# Configure DNS
echo web-platform-tests.org > CNAME

# Disable Jekyll
# https://github.blog/2009-12-29-bypassing-jekyll-on-github-pages/
touch .nojekyll

git add .

git commit --message "Build documentation

These files were generated from commit ${source_revision}"

git push --force ${remote_url} HEAD:gh-pages