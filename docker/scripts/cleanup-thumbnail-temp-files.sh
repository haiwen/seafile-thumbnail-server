#!/bin/bash

function cleanup_thumbnail_temp_files() {
    local tmp_dir=${TMPDIR:-/tmp}

    # Remove old thumbnail-processing temporary files by extension.
    find "$tmp_dir" -type f -mmin +60 \
        \( -name '*.png' -o -name '*.pdf' -o -name '*.mp4' -o -name '*.xmind' \) \
        -delete 2>/dev/null

    return 0
}

cleanup_thumbnail_temp_files
