from sqlmodel import Field, SQLModel

MIN_VOLUME = 0
MAX_VOLUME = 100
DEFAULT_VOLUME = 100


class AudioStatusPublic(SQLModel):
    # `handles_audio` is this device's own real config field (set from
    # master, like every other `Device` column) -- read-only here, never
    # written by this page. `audiofile`/`test_audiofile`/`volume`/
    # `playing` are this device's own local playback state
    # (audio_player.py's JSON file + the live mpv process), deliberately
    # NOT the `devices` table's `audiofile` column: that column is
    # master-authoritative and gets overwritten by the next automatic
    # config sync, so writing an upload's filename there would just get
    # silently reverted. This is a standalone test/config tool, not part
    # of the config-sync chain.
    handles_audio: bool
    audiofile: str | None = None
    # A separate calibration sample, uploaded via its own slot and
    # played by the "Son test" button -- independent of `audiofile` (the
    # real show file, played by "Lecture") so testing volume/playback
    # never touches what's actually configured to play.
    test_audiofile: str | None = None
    volume: int
    # Shared by both playback slots (there's only ever one mpv process)
    # -- whichever file is currently playing loops when this is set.
    loop: bool
    playing: bool


class AudioVolumeRequest(SQLModel):
    volume: int = Field(ge=MIN_VOLUME, le=MAX_VOLUME)


class AudioLoopRequest(SQLModel):
    enabled: bool
