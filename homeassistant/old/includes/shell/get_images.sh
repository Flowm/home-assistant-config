#!/usr/bin/env bash

# Config
OUT_DIR="/home/homeassistant/.homeassistant/media/"
mkdir -p $OUT_DIR
cd $OUT_DIR

# Get images
wget -qN "http://www.dwd.de/DWD/wetter/radar/rad_bay_akt.jpg" -O rad_bay_akt.jpg

wget -q "https://www.foto-webcam.eu/webcam/muenchen/current/720.jpg" -O web_freimann.jpg
