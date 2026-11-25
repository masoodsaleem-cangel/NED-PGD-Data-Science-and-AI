"""Install this TokenScope update into an existing copy of a supported release."""
import argparse
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

SUPPORTED_HASHES = {
    "bin/TokenScope.exe": (
        "5c56b8209826464f23198726ded95399cbf3c483a4c9ed33f8c290df9a3d7d1f",
        "905a3940591b9b3fb7fa453e40eb4b57c3fad01662edf36031cedbee15d132a7",
        "bab9e7bfcb37bbafa6ad63801a7b186e42aec4bcd29995b3b382c9e100920bdd",
        "53ddc14f1365beaf0ced53d1f0acbb02e13575585628aa40cb380cd91a4b47bf"),
    "bin/Capture.exe": (
        "7096b805746fb016f3f5e29e1a853f992ec0a896d302220d106e328976eb05c9",
        "9a82d32bb7320b0e466ec5770dc936a3a61f4c19ea68871b1ccfa74937960383"),
    "src/capture.cpp": (
        "c67bd07cbc9cc17d1f6f51134e3e3903c72b0d0ba1bc0ab6881a696fb5c0a467",
        "6fe56cdb1ad6cf006d2de4d13897f5491fe8b04e16425bf053a958241a7e54c5"),
    "CMakeLists.txt": ("8a9f285a5a38c47dd095bd481b325045b54eefff0e6ce75386d1932698cfe408",),
    "README.md": (
        "ebe390664096d59ec814ca736279d51c001581e37dad3e6c7f004cfcf059b48e",
        "878de91ddfd1a90bf50cfa2235bf0509f69a0163acaab5cedc000fa8debcc2a5",
        "4f47d0b0e273691d75f1fd4d4420dab12a408e2b5aa4ac0c6728a80882b26c53",
        "4e4c5f585bcedf5cac339d82330aa72f984ac5e89208a26f8c4067937542f171"),
    "src/renderer.hpp": (
        "51239e1960e4f71e20e36a977252bbfe591fa36da836ec10c4cb48c8c6e21133",
        "68993351269f4d039c7cc0777d083ab4de16a0f263b393b16e4c919d687b0ff6",
        "50ab27881f9f8186c39e67948ccb0feddc12441d39f2f50a5efeda585f473768"),
    "src/renderer.cpp": (
        "0368d2a45d8ee7187985f1bb528acfb93b7638586ab5bf4abd23bcf18c028b77",
        "27e37d5e64d62f33b6bc6b39b47bd27166e3b3c4f17edfc0c5d0a3c7041ba189",
        "7af3e8d13b8169329583b635bb78c119733b9d3fb6d15521e2068327bdc01309"),
    "src/viewer.cpp": (
        "e0ad2ea4ec965621a7866560b680158166101e70ea89f46185f7b32fd5165be9",
        "c2985d50abb1a246109cbf068fe42c506a2827d1fa96633166e4494415772f2a",
        "2d7e96d5d1d39c87733a980f827a6d606bc433a34560df18b01f1b195253c622",
        "615fad24685c00d86543642c3dd6c6b6994544ba28b0ca0ae06722edbc6ac751"),
    "src/answer.hpp": (None,"0e97423aecb13ea753ca2b60a69fc5256b16b6f4961fc5ae910308479409f56e"),
    "src/answer.cpp": (None,"3ea02d0afe7c42763924f082799072e009ed024ffc79156c074e5d9174fe01b4"),
    "examples/cashed-cheque.jsonl": (None,),
    "Preview.mp4": (
        "2ea32d5ca48889eec1cd3797f29dec34df0748895edf5ffb59ed0f8ad5cacc43",
        "020ecf83d385e6742fd62530b844980e5217701aaaa530ede558d0345f011442",
        "9b042a5f098b5051a7bc822860ab9d23c26da1726fe88b4f5e12f252334b4731"),
    "tools/apply_update.py": (None,
        "86ffacca2307121f065064d87f801dc279f524e99aaeabf5cc745d5b153471dc",
        "e1bee814afc03c67a331cce082cfcb8260a6e8e7c9d360aee11b69aeac71f911",
        "9679588e306ca2177a081a6ecac30f17d3c47506257e0a948571915a7cb7367d"),
}


def digest(path):
    if not path.exists():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()


def stage_sibling(source, destination, cleanup):
    # Windows carries inherited access rules with a moved file. Stage in its final folder.
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".tokenscope-", delete=False) as temp:
        path = Path(temp.name)
    cleanup.callback(path.unlink, missing_ok=True)
    shutil.copy2(source, path)
    return path


def replace_existing(source, destination):
    if os.name != "nt":
        os.replace(source, destination)
        return
    # Also retain any explicit access rules the user set on the installed file.
    import ctypes
    from ctypes import wintypes

    replace = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                        wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID)
    replace.restype = wintypes.BOOL
    if not replace(str(destination), str(source), None, 0, None, None):
        raise ctypes.WinError(ctypes.get_last_error())


def install(target):
    source = Path(__file__).resolve().parents[1]
    target = target.resolve(strict=True)
    if not (target / "CMakeLists.txt").is_file() or not (target / "bin/TokenScope.exe").is_file():
        raise ValueError(f"Choose the existing TokenScope project folder. Found {target}")
    updates = []
    for name, supported in SUPPORTED_HASHES.items():
        path = target / name
        if path.resolve().parent != path.parent or not path.resolve().is_relative_to(target):
            raise ValueError(f"Unexpected destination for {name}")
        new_hash = digest(source / name)
        if new_hash is None:
            raise ValueError(f"The update is incomplete. Extract the complete ZIP first. Missing {name}")
        old_hash = digest(path)
        if old_hash == new_hash:
            continue
        if old_hash not in supported:
            raise ValueError(f"Local edits found in {name}. The update stopped before changing any files.")
        updates.append((name, old_hash, new_hash))

    if not updates:
        print(f"Already up to date.\n{target}")
        return
    with ExitStack() as cleanup:
        backups = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix=".tokenscope-update-", dir=target)))
        staged = {}
        for name, old_hash, expected in updates:
            fresh = stage_sibling(source / name, target / name, cleanup)
            if digest(fresh) != expected:
                raise OSError(f"Could not stage {name}")
            staged[name] = fresh
            if old_hash is not None:
                backup = backups / name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target / name, backup)
                if digest(backup) != old_hash:
                    raise OSError(f"Destination changed while preparing {name}")
        written = []
        try:
            for name, previous, _ in updates:
                path = target / name
                if digest(path) != previous:
                    raise OSError(f"Destination changed while applying {name}")
                if previous is None:
                    os.rename(staged[name], path)
                else:
                    replace_existing(staged[name], path)
                written.append((name, previous))
        except BaseException:
            for name, previous in reversed(written):
                if previous is None:
                    (target / name).unlink()
                else:
                    path = target / name
                    restore = stage_sibling(backups / name, path, cleanup)
                    replace_existing(restore, path)
            raise
    print(f"Updated {len(updates)} files.\n{target}\nLaunch Replay.cmd or Start_Qwen.cmd in that folder.")


if __name__ == "__main__":
    default = Path.home() / "Documents/GitHub/TokenScope_Windows_x64/TokenScope"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=default)
    args = parser.parse_args()
    try:
        install(args.target)
    except (ValueError, OSError) as error:
        print(f"Update stopped. {error}", file=sys.stderr)
        sys.exit(1)
