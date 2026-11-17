"""Supply Python 3.11's Windows version probe before bundled imports run."""
import sys


if sys.platform == "win32" and sys.version_info[:2] == (3, 11):
    import platform

    def _native_windows_version(system="", release="", version="", supported_platforms=("win32", "win16", "dos")):
        if sys.platform not in supported_platforms:
            return system, release, version
        winver = sys.getwindowsversion()
        native = winver.platform_version or winver[:3]
        return system or "Windows", release, ".".join(map(str, native))

    # CPython 3.11's helper otherwise calls cmd.exe /c ver. Keep the public
    # platform API and replace only that Windows shell fallback.
    platform._syscmd_ver = _native_windows_version
