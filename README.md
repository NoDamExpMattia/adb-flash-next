# ADB Flash Next

A Windows desktop application (Python + PySide6) that guides the installation of Android custom ROMs using **Fastboot** and **ADB sideload**.

> \*\*Status: early development.\*\* Device detection works in early form; image mapping, flashing and sideload are still being built. Do not rely on it yet.

## Goals

* Detect connected devices through ADB and Fastboot and show only information the device actually reports ("Not available" otherwise).
* Let you choose individual `.img` files and **manually confirm** which partition each one is flashed to.
* Handle A/B and A-only devices without guessing partition names or slots.
* Flash sequentially, stop on the first failure, and offer a dry-run preview.
* Guide the manual recovery steps, then install a ROM ZIP with `adb sideload`.
* Show 100% only after Android has actually booted.

## Safety and disclaimer

Flashing images can make a device unbootable and can erase data. This software is provided **as is, without warranty**. You are responsible for following your ROM's official installation instructions and for backing up your data. A filename or basic header check can never prove that an image is compatible with your device.

Samsung devices are outside the intended scope.

## Requirements

* Windows 10 or 11
* Python 3.11 or newer (developed on 3.14)
* [PySide6](https://pypi.org/project/PySide6/)
* Google's official Android SDK Platform-Tools (**not bundled**): download them from
[https://developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools) and select the folder in the app's Settings page.
* A USB driver for your device if Windows does not detect it.

## Run from source

```powershell
git clone https://github.com/NoDamExpMattia/adb-flash-next.git
cd adb-flash-next
py -3.14 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Run the tests

```powershell
python -m unittest discover -s tests -t .
```

## Roadmap

* \[x] Project foundation and UI
* \[x] Device detection (ADB / Fastboot, slot detection)
* \[ ] Image selection, partition mapping, validation and flash-plan preview
* \[ ] Fastboot flashing
* \[ ] Recovery guidance and ADB sideload
* \[ ] Boot completion verification
* \[ ] Tests and Windows executable packaging

## License

No license has been chosen yet.

