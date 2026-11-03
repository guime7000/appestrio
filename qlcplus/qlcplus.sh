#!/bin/bash
echo "Running entrypoint script"
source /QLC/qt_export.sh

# Deliberately NOT `qlcplus -w -o <file> -p` -- confirmed by testing
# directly (2026-11-02): opening a project via `-o` at launch, together
# with `-w` (web interface) and `-p` (operate mode), hangs the web
# server entirely -- it never binds port 9999 at all, even though the
# main process keeps running. Loading the exact same file via the web
# interface's own upload endpoint (what the "Load project" button in
# the UI does) after the server is actually up works fine, so this
# just automates that instead of passing the file on the command line.
qlcplus -w -p &
QLC_PID=$!

# The project folder (compose.yml bind-mounts /home/pi/OhmFiles/qlc
# here, as a whole directory -- not a specific filename) is searched
# for its one .qxw file rather than requiring an exact name like
# "qlc.qxw" -- the external partner's file keeps its own real name.
# Directory-level mount deliberately replaces the earlier single-FILE
# mount (2026-11-03): a missing bind-mount *directory* source just
# auto-creates empty (confirmed harmless), whereas a missing *file*
# source silently became an empty directory in its place and broke
# loading -- searching a directory sidesteps that failure mode
# entirely, matching the explicit ask to "avoid a crash if no file is
# found."
PROJECT_DIR=/QLC/project
mapfile -t PROJECT_FILES < <(find "$PROJECT_DIR" -maxdepth 1 -iname "*.qxw" 2>/dev/null | sort)

if [ "${#PROJECT_FILES[@]}" -eq 0 ]; then
  echo "No .qxw project file found in $PROJECT_DIR -- starting QLC+ with an empty show."
elif [ "${#PROJECT_FILES[@]}" -gt 1 ]; then
  echo "More than one .qxw project file found in $PROJECT_DIR, refusing to guess which one to load:"
  printf '  %s\n' "${PROJECT_FILES[@]}"
  echo "Leave exactly one .qxw file in that folder and restart this container."
else
  PROJECT_FILE="${PROJECT_FILES[0]}"
  echo "Waiting for the QLC+ web interface before loading the project..."
  until curl -s -o /dev/null http://localhost:9999/; do
    sleep 1
  done
  echo "Loading project $PROJECT_FILE"
  curl -s -F "qlcprj=@$PROJECT_FILE" http://localhost:9999/loadProject -o /dev/null
fi

wait "$QLC_PID"
