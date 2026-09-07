r"""End-to-end test: max-active-downloads queue.

Run with the app venv:  .venv\Scripts\python.exe tests\test_active_limit.py

Scenario (max_active_downloads=1):
  1. Torrent B and magnet M are seeded by a plain libtorrent session on
     localhost.  Torrent A is intentionally given NO source, so it
     deterministically stays "Downloading" forever until paused/removed -
     an eternally active slot holder that never frees its slot on its own.
  2. Torrent A is added -> starts.  B is added -> stays "Queued" while A
     holds the slot.
  3. Magnet flow (M): metadata arrives while A is still active -> the engine
     pauses it awaiting file selection; activating it while the slot is full
     re-queues it (deterministic because A can never complete).
  4. Pausing A promotes B ("pause frees slot").  Manual resume of A always
     wins (may temporarily exceed the limit).  Removing A after pausing B
     frees the slot and promotes the queued magnet.
  5. The session download throttle keeps B from finishing mid-test, then is
     removed so the remaining downloads complete quickly.

The download-rate throttle makes the queue checks deterministic: A is the
slot holder for the magnet-re-queue check (it never completes), and B cannot
burst-finish between its promotion and the remove() check.
"""

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import libtorrent as lt

from core.engine import TorrentEngine

PIECE = 128 * 1024
SIZE = 8 * 1024 * 1024
SEED_PORT = 6995
DOWNLOAD_LIMIT = 512 * 1024  # 512 KB/s session download cap during the queue phase


def make_payload(base):
    with open(os.path.join(base, "data.bin"), "wb") as handle:
        handle.write(os.urandom(SIZE))


def make_torrent(base):
    fs = lt.file_storage()
    lt.add_files(fs, base)
    ct = lt.create_torrent(fs, PIECE, lt.create_torrent.v1_only)
    lt.set_piece_hashes(ct, os.path.dirname(base), lambda _: None)
    target = base + ".torrent"
    with open(target, "wb") as handle:
        handle.write(lt.bencode(ct.generate()))
    return target


def wait_for(predicate, timeout=120, interval=0.2):
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


def seed(path):
    params = lt.add_torrent_params()
    params.ti = lt.torrent_info(path)
    params.save_path = os.path.dirname(path[: -len(".torrent")])
    params.flags &= ~lt.torrent_flags.paused
    seeder.add_torrent(params)


def main():
    tmp = tempfile.mkdtemp(prefix="vortex_limit_test_")
    config = os.path.join(tmp, "config")
    os.makedirs(config)
    print("payload: creating 3 torrents (%d KB each) ..." % (SIZE // 1024))
    torrents = []
    seed_dirs = []
    for index in range(3):
        seed_dir = os.path.join(tmp, "seed%d" % index)
        os.makedirs(seed_dir)
        make_payload(seed_dir)
        seed_dirs.append(seed_dir)
        torrents.append(make_torrent(seed_dir))

    global seeder
    seeder = lt.session(
        {
            "listen_interfaces": "127.0.0.1:%d" % SEED_PORT,
            "enable_upnp": False,
            "enable_natpmp": False,
            "alert_mask": lt.alert.category_t.error_notification,
        }
    )
    # Seed ONLY torrents[1] and torrents[2].  Torrent A gets no source on
    # purpose: it can never complete, keeping its slot deterministically.
    seed(torrents[1])
    seed(torrents[2])

    engine = TorrentEngine(config)
    engine.start(
        port=SEED_PORT + 1,
        max_active_downloads=1,
        download_rate=DOWNLOAD_LIMIT,
    )
    failures = []

    def check(label, condition, detail=""):
        status = "PASS" if condition else "FAIL"
        print("  [%s] %s%s" % (status, label, (" - " + detail) if detail and not condition else ""))
        if not condition:
            failures.append(label)

    try:
        a = engine.add_torrent_file(torrents[0], os.path.join(tmp, "dl0"))
        b = engine.add_torrent_file(torrents[1], os.path.join(tmp, "dl1"))

        check("first torrent starts", wait_for(lambda: state_of(engine, a.id) == "Downloading"))
        check("second torrent queued", state_of(engine, b.id) == "Queued")
        time.sleep(2.0)
        check("queued torrent stays queued while first downloads",
              state_of(engine, b.id) == "Queued" and state_of(engine, a.id) == "Downloading")

        # --- magnet flow: metadata -> await files -> re-queued while A holds ---
        ih = str(lt.torrent_info(torrents[2]).info_hash())
        m = engine.add_magnet("magnet:?xt=urn:btih:" + ih, os.path.join(tmp, "dlm"))
        try:
            m.handle.connect_peer(("127.0.0.1", SEED_PORT))
        except RuntimeError:
            pass
        check("magnet metadata received",
              wait_for(lambda: engine.file_list(m.id) is not None
                       and state_of(engine, m.id) != "Downloading"))
        engine.activate(m.id)
        check("magnet re-queued while slot full",
              wait_for(lambda: state_of(engine, m.id) == "Queued"))

        # --- pause A frees the slot: first queued (B) is promoted ---
        engine.pause(a.id)
        check("pause frees slot: B promoted", wait_for(lambda: state_of(engine, b.id) == "Downloading"))
        check("paused torrent reported Paused", state_of(engine, a.id) == "Paused")

        # --- manual resume overrides the limit ---
        engine.resume(a.id)
        check("manual resume overrides limit", wait_for(lambda: state_of(engine, a.id) == "Downloading"))

        # --- removing the active torrent promotes the queued magnet ---
        engine.pause(b.id)  # B must not occupy the slot when A is removed
        check("pause B: still one active (A)",
              wait_for(lambda: state_of(engine, a.id) == "Downloading"
                       and state_of(engine, b.id) == "Paused"))
        engine.remove(a.id, delete_files=False)
        check("remove frees slot: magnet promoted",
              wait_for(lambda: state_of(engine, m.id) == "Downloading"))

        # --- remove the throttle and finish ---
        engine.apply_speed_limits(0)
        engine.resume(b.id)
        check("all reach Completed",
              wait_for(lambda: all(state_of(engine, t.id) == "Completed" for t in (b, m))))
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