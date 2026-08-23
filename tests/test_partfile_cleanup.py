"""End-to-end test: '.parts' part-file cleanup after download completes.

Run with the app venv:  .venv\\Scripts\\python.exe tests\\test_partfile_cleanup.py

Scenario:
  1. Two local torrents (3 unaligned-size files each so pieces span file
     boundaries) are seeded by a plain libtorrent session on localhost.
  2. TorrentEngine downloads torrent 1 with file priorities [1,0,0]
     (selective - forces libtorrent part-file usage) and torrent 2 fully.
  3. After completion both download folders must contain NO .parts file and
     the selected files must match the seeded originals (checked after a
     short quiesce, because 'Completed' can appear before the last async
     disk writes land).
     Skipped files may exist as 0-byte placeholders (libtorrent behaviour).
  4. Legacy leftovers: a fake .parts file placed next to a completed torrent
     must be removed on next startup (resume-data load path).
  5. Removing a completed torrent (keeping its data) must also remove its
     leftover .parts file (orphan queue path).
"""

import hashlib
import os
import shutil
import sys
import tempfile
import time
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import libtorrent as lt

from core.engine import TorrentEngine

PIECE = 256 * 1024
SIZES = [700000, 1100000, 900000]
T3_SIZES = [300000, 500000, 200000]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_payload(base, sizes=None):
    sizes = sizes or SIZES
    names = []
    for index, size in enumerate(sizes):
        name = "f%d.bin" % index
        with open(os.path.join(base, name), "wb") as handle:
            handle.write(os.urandom(size))
        names.append(name)
    return names


def make_torrent(base, v1_only=False):
    fs = lt.file_storage()
    lt.add_files(fs, base)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if v1_only:
            ct = lt.create_torrent(fs, PIECE, lt.create_torrent.v1_only)
        else:
            ct = lt.create_torrent(fs, PIECE)
    lt.set_piece_hashes(ct, os.path.dirname(base), lambda _: None)
    target = base + ".torrent"
    with open(target, "wb") as handle:
        handle.write(lt.bencode(ct.generate()))
    return target


def find_parts(root):
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        hits.extend(os.path.join(dirpath, name) for name in files if name.endswith(".parts"))
    return hits


def wait_for(predicate, timeout=180, interval=0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def state_of(engine, torrent_id):
    for row in engine.snapshot():
        if row["id"] == torrent_id:
            return row["state"]
    return None


def add_seed(session, torrent_path):
    params = lt.add_torrent_params()
    params.ti = lt.torrent_info(torrent_path)
    # add_files() prefixes file paths with the payload folder name, so the
    # seeder's save path must be that folder's parent.
    params.save_path = os.path.dirname(torrent_path[: -len(".torrent")])
    params.flags &= ~lt.torrent_flags.paused
    session.add_torrent(params)


def main():
    tmp = tempfile.mkdtemp(prefix="vortex_parts_test_")
    seed1 = os.path.join(tmp, "seed1")
    seed2 = os.path.join(tmp, "seed2")
    seed3 = os.path.join(tmp, "seed3")
    leech1 = os.path.join(tmp, "leech1")
    leech2 = os.path.join(tmp, "leech2")
    leech3 = os.path.join(tmp, "leech3")
    config = os.path.join(tmp, "config")
    for folder in (seed1, seed2, seed3, leech1, leech2, leech3, config):
        os.makedirs(folder)

    print("payload: creating 3 torrents ...")
    names1 = make_payload(seed1)
    names2 = make_payload(seed2)
    names3 = make_payload(os.path.join(tmp, "seed3"), T3_SIZES)
    seed3 = os.path.join(tmp, "seed3")
    t1 = make_torrent(seed1, v1_only=True)
    t2 = make_torrent(seed2, v1_only=True)
    t3 = make_torrent(seed3)
    name1 = lt.torrent_info(t1).name()
    name2 = lt.torrent_info(t2).name()
    name3 = lt.torrent_info(t3).name()
    hash2 = str(lt.torrent_info(t2).info_hash())

    seeder = lt.session(
        {
            "listen_interfaces": "127.0.0.1:6990",
            "enable_upnp": False,
            "enable_natpmp": False,
            "alert_mask": lt.alert.category_t.error_notification,
        }
    )
    add_seed(seeder, t1)
    add_seed(seeder, t2)
    add_seed(seeder, t3)

    engine = TorrentEngine(config)
    engine.start(port=6991)
    failures = []

    def check(label, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        print("  [%s] %s%s" % (status, label, (" - " + detail) if detail and not condition else ""))
        if not condition:
            failures.append(label)

    try:
        entry1 = engine.add_torrent_file(t1, leech1, priorities=[1, 0, 0])
        entry2 = engine.add_torrent_file(t2, leech2)
        entry3 = engine.add_torrent_file(t3, leech3, priorities=[0, 1, 0])
        for entry in (entry1, entry2, entry3):
            for _ in range(30):
                try:
                    entry.handle.connect_peer(("127.0.0.1", 6990))
                    break
                except RuntimeError:
                    time.sleep(0.2)

        check("file list hides pad files (hybrid torrent)",
              engine.file_list_from_file(t3) is not None
              and len(engine.file_list_from_file(t3)) == len(T3_SIZES))

        check("all torrents reached Completed",
              wait_for(lambda: all(state_of(engine, e.id) == "Completed"
                                   for e in (entry1, entry2, entry3))))

        # 'Completed' can appear before the final async writes settle.
        time.sleep(2.0)

        selected = os.path.join(leech1, name1, names1[0])
        check("selected file intact",
              os.path.isfile(selected) and sha256(selected) == sha256(os.path.join(seed1, names1[0])))
        for name in names1[1:]:
            skipped = os.path.join(leech1, name1, name)
            ok = not os.path.exists(skipped) or os.path.getsize(skipped) == 0
            check("skipped file not downloaded (%s)" % name, ok)
        check("no .parts left in torrent 1 folder", not find_parts(leech1), ", ".join(find_parts(leech1)))
        check("no .parts left in torrent 2 folder", not find_parts(leech2), ", ".join(find_parts(leech2)))

        for name in names2:
            downloaded = os.path.join(leech2, name2, name)
            check("full download intact (%s)" % name,
                  os.path.isfile(downloaded) and sha256(downloaded) == sha256(os.path.join(seed2, name)))

        # --- hybrid (v1+v2) torrent: pad files must not shift selections ---
        middle = os.path.join(leech3, name3, names3[1])
        check("hybrid torrent: selected middle file intact",
              os.path.isfile(middle) and sha256(middle) == sha256(os.path.join(seed3, names3[1])))
        for index in (0, 2):
            skipped = os.path.join(leech3, name3, "f%d.bin" % index)
            ok = not os.path.exists(skipped) or os.path.getsize(skipped) == 0
            check("hybrid torrent: unselected file empty (%d)" % index, ok)
        check("no .parts left in torrent 3 folder", not find_parts(leech3), ", ".join(find_parts(leech3)))

        # --- legacy leftover cleanup on startup (resume-data load path) ---
        engine.stop()
        dummy = os.path.join(leech2, ".%s.parts" % hash2)
        with open(dummy, "wb") as handle:
            handle.write(b"stale-partfile-data")

        engine = TorrentEngine(config)
        engine.start(port=6991)
        entry2b = engine.add_torrent_file(t2, leech2)
        gone = wait_for(lambda: not os.path.exists(dummy), timeout=20, interval=0.1)
        check("legacy .parts removed on startup", gone)

        # --- orphan cleanup when removing a completed torrent (keep data) ---
        with open(dummy, "wb") as handle:
            handle.write(b"stale-partfile-data")
        engine.remove(entry2b.id, delete_files=False)
        gone = wait_for(lambda: not os.path.exists(dummy), timeout=25, interval=0.1)
        check(".parts removed when torrent removed (data kept)", gone)
    finally:
        try:
            engine.stop()
        except Exception:
            pass
        seeder.pause()
        shutil.rmtree(tmp, ignore_errors=True)

    print("")
    if failures:
        print("FAILED (%d): %s" % (len(failures), ", ".join(failures)))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
