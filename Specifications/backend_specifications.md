# Backend Specifications

## Lumestrio
Payload example when looking for Lumestrio config detail
```json
{
    "uuid": "12345",
    "device_id": "lumestrio13",
    "device_name": "Le 13e lumestrio",
    "active": true,
    "group": "group A",
    "calendar": {
        "uuid": "calendar_uuid",
        "calendar_name": "calendar_id",
        "presets": {
            "setup1": {
                "start_time": "9h15",
                "end_time": "19h"
            },
            "exception": {
                "start_time": "10h15",
                "end_time": "11h30"
            }
        }
        "days": {
            "lundi": "setup1",
            "mardi": "setup1",
            "mercredi": "exception",
            "jeudi": "exception",
            "vendredi": "setup1",
            "samedi": "setup1 ",
            "dimanche": "exception"
        }
    },
    "audiofile": "the audio.mp3",
    "config_version": "cfg-123"
    "ip": "127.0.0.13"
    "master_ip": "127.0.0.1"
}
```

The config_version field is a reconciliation value to easily check from master if the active configuration on slave is the same as the one in master db. To check if configuration in master DB is the same as the one in the slave lumestrio, we then only need to compare "config_version" values on both master and slave, thus avoiding to transmit full payload via the slow LORA network.

Required endpoints:
Create
List/Detail
Update/Patch
Delete

## Groups

Required endpoints:
Create
List/Detail
Update/Patch
Delete

## Calendars

Required endpoints:
Create
List/Detail
Update/Patch
Delete
Calendar paylod could look like:
```json
"calendar": {
        "uuid": "calendar_uuid",
        "calendar_name": "calendar_id",
        "presets": {
            "setup1": {
                "start_time": "9h15",
                "end_time": "19h"
            },
            "exception": {
                "start_time": "10h15",
                "end_time": "11h30"
            }
        }
        "days": {
            "lundi": "setup1",
            "mardi": "setup1",
            "mercredi": "exception",
            "jeudi": "exception",
            "vendredi": "setup1",
            "samedi": "setup1 ",
            "dimanche": "exception"
        }
    }
```

## Architecture

Using FastAPI and psotgres.

Backend is the same on all devices.
The global setup is made of devices (identical raspberry pis) with one master and many slaves.

Slaves can be reached by two manners:
- remotely, from the master device using LORA protocol
- locally, via a direct WiFi connection to the slave device.

Master is the source of truth. For the first time, configs are done on the master and sent to the slaves.

When configured locally, slave should be able to send updated config to master (audio file name modified for example) to update the source of truth configuration.

### DB:

#### table devices:
uuid: UUID
id: string
name: string
active: boolean
group: relationship to group table
calendar: retrievable with relationship between group and calendar
audiofile: string
config_version: string
ip: string
master_ip: string

#### table groups:
uuid: UUID
label: string
calendar: relationship with calendar table
devices: relationship with devices table

#### table calendars:
uuid: UUID
label: string
presets: serialized JSON
days: one column for each day ? Serialized JSON ?


#### Relationships:

One lumestrio belongs to one group
One group can own one or more lumestrio

One groups is associated to one calendar
One calendar can be associated to one or more groups

#### Useful endpoints:

- api/is_active : let master know if a requested lumestrio is active or not. **[not sure as master already knows this]** 

- api/get_config_version : check if configuration stored on master is the same as the one stored on the requested lumestrio. If not, Master should send back a configuration.