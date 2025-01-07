#!/bin/bash
sudo systemctl stop controlm.service
sudo cp controlm.service /etc/systemd/system || exit 1
sudo systemctl daemon-reload || exit 1
sudo systemctl start controlm.service || exit 1
sudo systemctl enable controlm.service
sudo cp controlm.py /usr/bin/controlm