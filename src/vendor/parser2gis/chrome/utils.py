from __future__ import annotations

import functools
import os
import shutil
import socket
import subprocess

from ..common import running_mac, running_windows


def chrome_candidate_paths() -> list[str]:
    """Return the list of well-known Chrome executable paths for the current OS.

    Used both for automatic location and for diagnostics.
    """
    paths: list[str] = []

    if running_windows():
        env_dirs = [
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PROGRAMW6432",
            "LOCALAPPDATA",
        ]
        for d in env_dirs:
            if d in os.environ and os.environ[d]:
                paths.append(
                    os.path.join(os.environ[d], "Google", "Chrome", "Application", "chrome.exe")
                )

    elif running_mac():
        paths.extend(
            [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
                os.path.expanduser(
                    "~/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
                ),
                "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                "/Applications/Google Chrome Dev.app/Contents/MacOS/Google Chrome Dev",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
            ]
        )

    else:
        app_dirs = [
            "/usr/bin",
            "/usr/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
            "/sbin",
            "/opt/google/chrome",
        ]
        browser_executables = [
            "google-chrome",
            "chrome",
            "chrome-browser",
            "google-chrome-stable",
        ]
        for d in app_dirs:
            for f in browser_executables:
                paths.append(os.path.join(d, f))

    return paths


@functools.lru_cache
def locate_chrome_path() -> str | None:
    """Locate Chrome's executable path."""
    if running_windows():
        # Standard installation locations
        for binary_path in chrome_candidate_paths():
            if os.path.isfile(binary_path):
                return binary_path

        # We also could try to use Windows registry to find out Chrome's path
        import winreg

        reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        for install_type in winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE:  # type: ignore
            try:
                with winreg.OpenKey(install_type, reg_path, 0, winreg.KEY_READ) as reg_key:  # type: ignore
                    binary_path = winreg.QueryValue(reg_key, None)  # type: ignore
                    if os.path.isfile(binary_path):
                        return binary_path
            except OSError:  # type: ignore
                continue

    elif running_mac():
        binary_path = _locate_chrome_mac()
        if binary_path:
            return binary_path

    else:
        # Standard installation locations
        for binary_path in chrome_candidate_paths():
            if os.path.isfile(binary_path):
                return binary_path

        # We also could use 'which' to locate Chrome executable
        for f in ("google-chrome", "chrome", "chrome-browser", "google-chrome-stable"):
            binary_path = shutil.which(f)
            if binary_path and os.path.isfile(binary_path):
                return binary_path

    return None


def _locate_chrome_mac() -> str | None:
    """Locate Chrome's executable on macOS using several lookup strategies."""
    # Standard installation locations
    for binary_path in chrome_candidate_paths():
        if os.path.isfile(binary_path):
            return binary_path

    # The binary is rarely on PATH, but a symlink could be installed
    for executable in ("google-chrome", "google-chrome-stable", "chromium"):
        binary_path = shutil.which(executable)
        if binary_path and os.path.isfile(binary_path):
            return binary_path

    # Ask macOS where the app lives (Spotlight, then Launch Services) and
    # resolve the executable inside the returned `.app` bundle
    lookups = [
        ["mdfind", "-onlyin", "/", "kMDItemCFBundleIdentifier == 'com.google.Chrome'"],
        ["mdfind", "-onlyin", "/", "kMDItemCFBundleIdentifier == 'com.google.Chrome.canary'"],
        ["mdfind", "-onlyin", "/", "kMDItemCFBundleIdentifier == 'org.chromium.Chromium'"],
        ["osascript", "-e", 'POSIX path of (path to application id "com.google.Chrome")'],
        ["osascript", "-e", 'POSIX path of (path to application id "com.google.Chrome.canary")'],
        ["osascript", "-e", 'POSIX path of (path to application id "org.chromium.Chromium")'],
    ]
    for cmd in lookups:
        binary_path = _resolve_mac_app_binary(cmd)
        if binary_path:
            return binary_path

    return None


def _resolve_mac_app_binary(cmd: list[str]) -> str | None:
    """Run a lookup command and return the executable inside the `.app` it points to."""
    try:
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None

    for line in output.stdout.splitlines():
        app_dir = line.strip().rstrip("/")
        if not app_dir:
            continue

        exec_dir = os.path.join(app_dir, "Contents", "MacOS")
        exec_name = os.path.basename(app_dir).replace(".app", "")
        if exec_name:
            binary_path = os.path.join(exec_dir, exec_name)
            if os.path.isfile(binary_path):
                return binary_path

        # Last resort: any executable file inside Contents/MacOS
        try:
            for entry in os.listdir(exec_dir):
                binary_path = os.path.join(exec_dir, entry)
                if os.path.isfile(binary_path):
                    return binary_path
        except OSError:
            continue

    return None


def free_port() -> int:
    """Get free port using sockets.

    Returns:
        Free port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as free_socket:
        free_socket.bind(("127.0.0.1", 0))
        free_socket.listen(5)
        return free_socket.getsockname()[1]
