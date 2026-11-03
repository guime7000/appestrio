from sqlmodel import SQLModel


class DmxStatusPublic(SQLModel):
    # Gates the frontend's "QLC+" nav link, same `handles_dmx` real
    # config field (set from master) the Audio page's `handles_audio`
    # already follows the same pattern for.
    handles_dmx: bool
