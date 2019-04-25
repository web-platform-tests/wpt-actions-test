#!/bin/bash

set -x

neutral_status=78
source_revision=$(git rev-parse HEAD)

function modifies_relevant_files {
  base_revision=$(
    cat ${GITHUB_EVENT_PATH} | \
      python -c 'import json, sys; print json.load(sys.stdin)["before"]'
  )

  git diff --name-only ${base_revision} | \
    grep -E --silent '^(docs|tools)/'
}

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

# Configure DNS
echo web-platform-tests.org > CNAME

# Disable Jekyll
# https://github.blog/2009-12-29-bypassing-jekyll-on-github-pages/
touch .nojekyll

git add .

cat <<HERE |
Build documentation

These files were generated from commit ${source_revision}
HERE
git commit --file -

# The token available in the `GITHUB_TOKEN` variable may be used to push to the
# repository, but GitHub Pages will not rebuild the website in response to such
# events. Use an access token generated for the project's machine user,
# wpt-pr-bot.
#
# https://help.github.com/en/articles/generic-jekyll-build-failures
git push --force \
  https://${DEPLOY_TOKEN}@github.com/web-platform-tests/wpt-actions-test.git master:gh-pages
