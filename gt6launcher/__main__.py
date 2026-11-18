"""Entry point.  `gt6-launcher` opens the GUI; sub-commands allow scripted use:

  gt6-launcher status
  gt6-launcher add-game <iso|folder>
  gt6-launcher firmware [PUP]
  gt6-launcher updates [TITLE] [--target 01.22]
  gt6-launcher prepare [TITLE]          write RPCS3 config + patches only
  gt6-launcher play [TITLE]
  gt6-launcher mod-import <zip|folder> | mod-install [TITLE] | mod-uninstall [TITLE]
"""
from __future__ import annotations

import argparse
import os
import sys


def _progress(label: str, done: int, total: int) -> None:
    if total:
        sys.stdout.write(f"\r{label}: {100 * done / total:5.1f}%   ")
    else:
        sys.stdout.write(f"\r{label}...   ")
    sys.stdout.flush()


def cli(argv: list[str]) -> int:
    from . import mods
    from .core import Core
    from .rpcs3 import STOCK_BUILD_WARNING, is_patched_build

    ap = argparse.ArgumentParser(prog="gt6-launcher")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("add-game"); p.add_argument("path")
    p = sub.add_parser("firmware"); p.add_argument("pup", nargs="?")
    p = sub.add_parser("updates"); p.add_argument("title", nargs="?"); p.add_argument("--target")
    for c in ("prepare", "play", "mod-install", "mod-uninstall"):
        p = sub.add_parser(c); p.add_argument("title", nargs="?")
    p = sub.add_parser("mod-import"); p.add_argument("path")
    sub.add_parser("diag-dlldir")  # Windows CI: emulator child must not inherit our DLL dir
    a = ap.parse_args(argv)
    if a.cmd == "diag-dlldir":
        return _diag_dlldir()
    core = Core()

    def entry(tid):
        games = core.games()
        g = next((g for g in games if g.title_id == tid), None) if tid else core.active()
        if not g:
            raise SystemExit("no such game - use add-game first")
        return g

    if a.cmd == "status":
        rp = core.rpcs3_path()
        print("RPCS3:", rp or "not found", "" if not rp or is_patched_build(rp) else f"\n  ! {STOCK_BUILD_WARNING}")
        if rp:
            print("Firmware:", core.rpcs3().firmware_version() or "not installed")
        from . import gamepad
        pads = gamepad.list_gamepads()
        print("Gamepads:", "detection unavailable" if pads is None else (", ".join(pads) or "none connected"))
        for g in core.games():
            print(f"{g.label}: {g.image.path}\n  installed {g.installed or '01.00'}, target {core.target_version(g.title_id)}, "
                  f"mods {mods.installed_stack(g.title_id) or '-'}")
    elif a.cmd == "add-game":
        print(core.add_game(a.path).label)
    elif a.cmd == "firmware":
        if a.pup:
            core.data["firmware_path"] = a.pup
        core.ensure_firmware(_progress)
        print("\nfirmware", core.rpcs3().firmware_version())
    elif a.cmd == "updates":
        g = entry(a.title)
        if a.target:
            core.set_target_version(g.title_id, a.target)
        print("\nnow at", core.install_updates(g.title_id, _progress))
    elif a.cmd == "prepare":
        print("\n".join(core.prepare(entry(a.title))))
    elif a.cmd == "play":
        return core.launch(entry(a.title)).wait()
    elif a.cmd == "mod-import":
        print(mods.stage_download(a.path, _progress))
    elif a.cmd == "mod-install":
        g = entry(a.title)
        for m in mods.KNOWN_MODS:
            if mods.staged(m.id) and m.id not in mods.installed_stack(g.title_id):
                print(f"\n{m.name}: {mods.install(g.title_id, m.id, _progress)} files")
    elif a.cmd == "mod-uninstall":
        g = entry(a.title)
        while mods.installed_stack(g.title_id):
            print("removed", mods.uninstall_top(g.title_id))
    return 0


def _diag_dlldir() -> int:
    """Start a child the way RPCS3 is started and print the DLL directory it inherited.

    Exit 1 if it is the launcher's _internal folder (RPCS3 would then load our old
    VCRUNTIME140.dll and stop with "module ... was incorrectly installed")."""
    import subprocess
    from .rpcs3 import _popen
    ps = ("Add-Type -Name K -Namespace W -MemberDefinition '[DllImport(\"kernel32.dll\", CharSet=CharSet.Unicode)]"
          " public static extern uint GetDllDirectoryW(uint n, System.Text.StringBuilder b);';"
          " $b = New-Object System.Text.StringBuilder 1024; [void][W.K]::GetDllDirectoryW(1024, $b);"
          " Write-Output (\"DLLDIR=\" + $b.ToString())")
    out = _popen(["powershell", "-NoProfile", "-Command", ps], stdout=subprocess.PIPE,
                 stderr=subprocess.STDOUT, text=True).communicate(timeout=120)[0]
    print(out.strip())
    base = getattr(sys, "_MEIPASS", "") or ""
    line = next((l for l in out.splitlines() if l.startswith("DLLDIR=")), None)
    if line is None:
        print("diag-dlldir: no result")
        return 2
    leaked = bool(base) and line[7:].strip().lower().rstrip("\\") == base.lower().rstrip("\\")
    print("LEAKED" if leaked else "OK")
    return 1 if leaked else 0


_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",                 # Debian/Ubuntu, Arch, SteamOS
    "/etc/pki/tls/certs/ca-bundle.crt",                   # Fedora/RHEL
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora/RHEL
    "/etc/ssl/ca-bundle.pem",                             # openSUSE
    "/etc/ssl/cert.pem",                                  # Alpine, Arch
)


def _ensure_ca_bundle() -> None:
    """The AppImage's bundled OpenSSL looks for CA certificates where its build distro keeps them
    (/usr/lib/ssl on Ubuntu). SteamOS and other distros keep them elsewhere, so every HTTPS request
    failed with CERTIFICATE_VERIFY_FAILED (no game patches, no update check, no downloads - #54)."""
    if sys.platform.startswith("win") or sys.platform == "darwin" or os.environ.get("SSL_CERT_FILE"):
        return
    import ssl
    default = ssl.get_default_verify_paths()
    if default.cafile and os.path.isfile(default.cafile):
        return
    for path in _CA_BUNDLES:
        if os.path.isfile(path):
            os.environ["SSL_CERT_FILE"] = path
            return
    try:
        import certifi  # optional fallback when present
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except Exception:
        pass


def main() -> int:
    _ensure_ca_bundle()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-psn"):
        return cli(sys.argv[1:])
    from .ui import main as gui_main
    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
