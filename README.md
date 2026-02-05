---

## Screenshots

![Screenshot 1](screenshots/1.png)
![Screenshot 2](screenshots/2.png)
![Screenshot 3](screenshots/3.png)
![Screenshot 4](screenshots/4.png)


---

# WiFMan by LAB5 - WiFi Network Manager

**WiFi Profile Manager for Hak5 WiFi Pineapple Pager**

WiFMan is a graphical payload that allows easy management and switching between saved WiFi networks on the WiFi Pineapple Pager device.

---

## Table of Contents

1. Features
2. Requirements
3. Installation
4. Controls
5. User Interface
6. File Structure
7. Profile Format
8. Troubleshooting
9. License

---

## Features

* **Multi-profile storage** – store multiple WiFi networks in a local JSON file
* **GUI-compatible** – fully compatible with Pineapple GUI Client Mode
* **Real-time status** – displays actual connection state (not just configuration)
* **Network scanning** – automatic detection of available WiFi networks
* **Quick connect** – "Connect Last" for instant reconnection
* **Full on-screen keyboard** – enter SSIDs and passwords directly
* **Security support** – Open, WEP, WPA, WPA2, WPA3
* **Connection verification** – verifies that connection is actually established

---

## How it Works

WiFMan stores multiple network profiles in `profiles.json`, but when connecting it **replaces credentials inside the single STA profile** (`wireless.wlan0cli`) used by the Pineapple GUI.

This ensures:

* Pineapple GUI shows correct Client Mode state
* No conflicts with other services (PineAP, etc.)
* System stability

---

## Requirements

### Hardware

* Hak5 WiFi Pineapple Pager

### Software

* Python3 + python3-ctypes (installed automatically if missing)

---

## Installation

### Step 1: Download the repository

#### Option A — Clone using Git (Recommended)

```bash
git clone https://github.com/LOCOSP/pineapple_pager_wifman.git
cd pineapple_pager_wifman
```

---

#### Option B — Download ZIP from GitHub

1. Download ZIP from GitHub repository page
2. Extract archive
3. Go to extracted folder:

```bash
cd pineapple_pager_wifman
```

---

### Step 2: Copy payload to the device

```bash
scp -r wifman root@172.16.52.1:/root/payloads/user/general/
```

---

### Step 3: Run payload

Launch from:

```
Payloads → General → WiFMan
```

---


## Controls

WiFi Pineapple Pager has 6 physical buttons:

```
    [UP]
[LEFT] [RIGHT]    [RED]  [GREEN]
   [DOWN]
```

### Button Mapping

| Button    | Function                 |
| --------- | ------------------------ |
| UP        | Navigate up              |
| DOWN      | Navigate down            |
| LEFT      | Navigate left (keyboard) |
| RIGHT     | Profile action menu      |
| GREEN (A) | Select / Confirm         |
| RED (B)   | Back / Cancel            |

---

## User Interface

### Splash Screen

```
+----------------------------------+
|        WiFMan by LAB5            |
|     WiFi Network Manager         |
|             v1.0                 |
+----------------------------------+
```

---

### Main Menu

```
+----------------------------------+
|  WiFMan          Not connected   |
+----------------------------------+
|                                  |
|  > 1. Profiles                   |
|    2. Connect Last (none)        |
|    3. Disconnect                 |
|    4. Exit                       |
|                                  |
+----------------------------------+
| UP/DOWN=Move GREEN=Select RED=Back|
+----------------------------------+
```

| Option       | Description                     |
| ------------ | ------------------------------- |
| Profiles     | Manage saved WiFi networks      |
| Connect Last | Connect to last used network    |
| Disconnect   | Disconnect from current network |
| Exit         | Exit payload                    |

---

### Profiles Screen

```
+----------------------------------+
|  WiFi Profiles   Connected: Home |
+----------------------------------+
|                                  |
|  > HomeNetwork [WPA2]            |
|    OfficeWiFi [WPA2]             |
|    CafeHotspot [OPEN]            |
|    + Scan Networks               |
|    + Add Manually                |
|                                  |
+----------------------------------+
| UP/DOWN=Move GREEN=Select RED=Back|
+----------------------------------+
```

**Actions**

* GREEN on profile → connect
* GREEN on Scan Networks → scan available networks
* GREEN on Add Manually → add profile manually
* RIGHT on profile → edit/delete menu
* RED → back

---

### Network Scan Screen

```
+----------------------------------+
|      Found 5 Networks            |
+----------------------------------+
|                                  |
|  > HomeNetwork [WPA2] -45dBm     |
|    OfficeWiFi [WPA2] -62dBm      |
|    OpenCafe [OPEN] -70dBm        |
|    Neighbor5G [WPA3] -75dBm      |
|                                  |
+----------------------------------+
```

---

### On-Screen Keyboard

```
+----------------------------------+
|        Enter Password            |
+----------------------------------+
| [MyPassword123_                ] |
+----------------------------------+
|  1  2  3  4  5  6  7  8  9  0   |
|  q  w  e  r  t  y  u  i  o  p   |
|  a  s  d  f  g  h  j  k  l      |
|  z  x  c  v  b  n  m  .  -  _   |
+----------------------------------+
|  [SPC]  [DEL]  [aA]  [OK]       |
+----------------------------------+
```

---

### Security Selection

```
+----------------------------------+
|        Security Type             |
+----------------------------------+
|    Open                          |
|    WEP                           |
|    WPA                           |
|  > WPA2 (Recommended)            |
|    WPA3                          |
+----------------------------------+
```

---

### Profile Action Menu

```
+----------------------------------+
|         HomeNetwork              |
+----------------------------------+
|  > Connect                       |
|    Edit                          |
|    Delete                        |
|    Cancel                        |
+----------------------------------+
```

---

## File Structure

```
wifman/
├── payload.sh          # Payload entry script
├── profiles.json       # Stored WiFi profiles
├── wifman.py           # Main application
├── lib/
│   ├── pagerctl.py     # Python wrapper
│   └── libpagerctl.so  # Native display library
└── fonts/              # Optional fonts

```

---

## Profile Format

Profiles are stored in:

```
wifman/profiles.json
```

### Example

```json
{
  "profiles": [
    {
      "ssid": "KnownAP1",
      "security": "wpa2",
      "password": "Password1"
    },
    {
      "ssid": "KnownAP2",
      "security": "wpa2",
      "password": "Password2"
    }
  ],
  "last_connected": "KnownAP1"   # <-- Don't change that...
}
```

---

### Field Description

| Field          | Description                       |
| -------------- | --------------------------------- |
| ssid           | WiFi network name                 |
| security       | open, wep, wpa, wpa2, wpa3        |
| password       | Network password (empty for open) |
| last_connected | Used by Connect Last              |

---

### Manual Profile Editing

You can manually add or modify known networks by editing `profiles.json`.

Rules:

* WPA/WPA2/WPA3 → password required
* Open → password can be empty
* `last_connected` must match an existing SSID or be null

---

## Troubleshooting

### Python3 Missing

If payload shows:

```
PYTHON3 REQUIRED
```

Install manually:

```bash
ssh root@172.16.52.1
opkg update
opkg -d mmc install python3 python3-ctypes
```

---

### Cannot Connect to Network

Possible causes:

* Wrong password
* Wrong security type
* Network out of range
* wlan0cli misconfiguration

Diagnostics:

```bash
ssh root@172.16.52.1
iwinfo wlan0cli info
uci show wireless
```

---

## UCI Reference

```bash
uci set wireless.wlan0cli.ssid=NetworkName
uci set wireless.wlan0cli.encryption=psk2
uci set wireless.wlan0cli.key=Password
uci commit wireless
wifi reload
```

---

## Technical Architecture

WiFMan uses a **Shadow Config Model**:

```
profiles.json  →  wireless.wlan0cli  →  runtime connection
```

Verification:

```
uci get wireless.wlan0cli.ssid
iw dev phy0-sta0 link
```

---

## License

MIT License

---

## Author

LOCOSP

---

## Acknowledgements

* Hak5 – WiFi Pineapple Pager
* pagerctl – display control library

---
