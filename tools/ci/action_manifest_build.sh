#!/bin/bash
mkdir -p ~/meta

WPT_MANIFEST_FILE=~/meta/MANIFEST.json

./wpt manifest -p $WPT_MANIFEST_FILE
gzip -f $WPT_MANIFEST_FILE
