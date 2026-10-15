#!/bin/bash

# Remove temp files left over by a previous main.py process.
#
# main.py can be terminated without running its cleanup code: it calls
# os._exit(1) when the memory limit is reached, and a container restart or
# kill has the same effect.  The temp files created by the thumbnail tasks
# (see seafile_thumbnail/thumbnail.py) are then never removed, so they
# accumulate in the temp directory forever.
#
# This runs right before main.py is started, so no thumbnail task can be
# using these files at that moment.
function cleanup_thumbnail_temp_files() {
    local tmp_dir=${TMPDIR:-/tmp}

    find "$tmp_dir" -maxdepth 1 -type f -regextype posix-extended \
        \( -regex '.*/[0-9a-f]{8,40}\.(png|pdf|mp4|xmind)' \
           -o -regex '.*/tmp[A-Za-z0-9_]{8}\.pdf' \) \
        -delete 2>/dev/null

    return 0
}

cleanup_thumbnail_temp_files
