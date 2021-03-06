#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only

export NO_BROWSER="true"
export CODEGRADE_DATABASE_URL="postgresql:///codegrade_dev"


if [[ "$1" = npm ]]; then
    npm run dev
elif [[ "$1" = python ]]; then
    if [[ -z "$VIRTUAL_ENV" ]]; then
        source ./env/bin/activate
    fi

    ./run.py
fi
