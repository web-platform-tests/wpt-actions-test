#!/bin/bash

set -x

cd docs

apt-get install git
pip install -r requirements.txt

make html

cd _build/html

git init
git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
git config --global user.name "${GITHUB_ACTOR}"

echo web-platform-tests.org > CNAME

git add .

git commit -m 'Build documentation'

git push --force \
  https://${GITHUB_TOKEN}@github.com/web-platform-tests/wpt.git master:gh-pages
