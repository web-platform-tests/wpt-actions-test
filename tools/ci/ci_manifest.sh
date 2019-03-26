#!/bin/bash
set -ex

SCRIPT_DIR=$(cd $(dirname "$0") && pwd -P)
WPT_ROOT=$SCRIPT_DIR/../..
cd $WPT_ROOT

mkdir -p ~/meta

python tools/ci/tag_master.py
./wpt manifest -p ~/meta/MANIFEST.json
cp ~/meta/MANIFEST.json $WPT_MANIFEST_FILE
# Force overwrite of any existing file
gzip -f --best $WPT_MANIFEST_FILE -c > $WPT_MANIFEST_FILE.gz
bzip2 -c --best $WPT_MANIFEST_FILE > $WPT_MANIFEST_FILE.bz2
zstd -19 $WPT_MANIFEST_FILE $WPT_MANIFEST_FILE.zstd
