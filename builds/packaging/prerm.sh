#!/bin/bash

BIN_DIR=/usr/bin

# Distribution-specific logic
if [[ -f /etc/debian_version ]]; then
    # Debian/Ubuntu logic
    which systemctl &>/dev/null
    if [[ $? -eq 0 ]]; then
    deb-systemd-invoke stop valmond.service
    else
    # Assuming sysv
    invoke-rc.d valmond stop
    fi
fi
