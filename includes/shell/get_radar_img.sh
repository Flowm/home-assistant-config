#!/usr/bin/env bash

# Config
OUT_DIR="/home/homeassistant/.homeassistant/media/"
mkdir -p $OUT_DIR
cd $OUT_DIR

# Get images
wget -qN 'http://www.dwd.de/DWD/wetter/radar/rad_bay_akt.jpg'
