# ADB Flash Next (Soon getting a new name...)

ADB Flash Next is an experimental Windows desktop app built with Python and PySide6. It provides a graphical workflow for Android device detection, manually mapped Fastboot image flashing, reboot commands, Fastboot utilities, and recovery ADB sideload.

## Project status

Currently the program is in a very good phase! Everything is confirmed to work and probably will in future updates!
## Safety

- Flashing the wrong image can make a device fail to boot or require a full recovery.
- The app checks basic image headers and, when Fastboot reports it, partition sizes. These checks cannot establish device or ROM compatibility.
- Read the ROM maintainer's installation instructions and back up important data before using the app.
- Erasing `userdata`, `metadata`, or `frp` is destructive. Use these actions only when the official instructions for your device require them.
- The app does not unlock bootloaders or format data for you.
- Samsung devices are outside the intended support scope.

## Requirements

- Windows 10 or 11
- Python 3.11 or newer
- Google Android SDK Platform-Tools (`adb` and `fastboot`), installed separately and selected in Settings
- A suitable Windows USB driver for your device, if required

Platform-Tools are not included in this repository. Download them from [Google's Platform-Tools page](https://developer.android.com/tools/releases/platform-tools).

## Run from source

In PowerShell, from the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

On first launch, use **Settings → Auto-detect** or **Browse…** to select the extracted `platform-tools` folder.

## Flashing workflow

1. Connect the device and select it on the Dashboard. Use **Refresh** after changing its mode.
2. Open **Images** and select an image for each partition you intend to flash.
3. Every partition row starts included. Untick every unused row; a checked row without an image blocks the plan.
4. On A/B devices, review the slot choice for each selected partition.
5. Press **Flash partitions**, inspect the exact commands and device details, acknowledge the review, then start.

The app performs preflight checks, executes one Fastboot command at a time, and stops after the first failed step. Do not disconnect the device during a flash.

## Run the test suite

```powershell
python -m unittest discover -s tests -t .
```

The visual smoke test is separate and saves screenshots under `screenshots/`:

```powershell
python tools/smoke_test.py
```

## License

No license has been selected yet. Until a license is added, default copyright rules apply; a public GitHub repository is not automatically open-source software. See [GitHub's licensing guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
