#!/bin/bash
echo "Running entrypoint script"
source /QLC/qt_export.sh

# Deliberately NOT `qlcplus -w -o /QLC/qlc.qxw -p` -- confirmed by
# testing directly (2026-11-02): opening a project via `-o` at launch,
# together with `-w` (web interface) and `-p` (operate mode), hangs the
# web server entirely -- it never binds port 9999 at all, even though
# the main process keeps running. Loading the exact same file via the
# web interface's own upload endpoint (what the "Load project" button
# in the UI does) after the server is actually up works fine, so this
# just automates that instead of passing the file on the command line.
qlcplus -w -p &
QLC_PID=$!

if [ -f /QLC/qlc.qxw ]; then
  echo "Waiting for the QLC+ web interface before loading the project..."
  until curl -s -o /dev/null http://localhost:9999/; do
    sleep 1
  done
  echo "Loading project /QLC/qlc.qxw"
  curl -s -F "qlcprj=@/QLC/qlc.qxw" http://localhost:9999/loadProject -o /dev/null
fi

wait "$QLC_PID"
