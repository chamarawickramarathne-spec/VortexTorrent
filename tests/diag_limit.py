import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import libtorrent as lt

from core.engine import TorrentEngine

PIECE = 128 * 1024
SIZE = 200000
SEED_PORT = 6985


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


def main():
    tmp = tempfile.mkdtemp(prefix="vortex_diag_")
    config = os.path.join(tmp, "config")
    os.makedirs(config)
    torrents = []
    for index in range(3):
        seed = os.path.join(tmp, "seed%d" % index)
        os.makedirs(seed)
        make_payload(seed)
        torrents.append(make_torrent(seed))

    seeder = lt.session(
        {
            "listen_interfaces": "127.0.0.1:%d" % SEED_PORT,
            "enable_upnp": False,
            "enable_natpmp": False,
            "alert_mask": lt.alert.category_t.error_notification,
        }
    )
    for path in torrents:
        params = lt.add_torrent_params()
        params.ti = lt.torrent_info(path)
        params.save_path = os.path.dirname(path[: -len(".torrent")])
        params.flags &= ~lt.torrent_flags.paused
        seeder.add_torrent(params)

    engine = TorrentEngine(config)
    engine.start(port=SEED_PORT + 1, max_active_downloads=1)
    entries = []
    try:
        for i, path in enumerate(torrents):
            e = engine.add_torrent_file(path, os.path.join(tmp, "dl%d" % i))
            entries.append(e)
        entries[0].handle.connect_peer(("127.0.0.1", SEED_PORT))
        deadline = time.time() + 8.0
        while time.time() < deadline:
            with engine.lock:
                rows = []
                for e in entries:
                    try:
                        st = e.handle.status()
                        info = "q=%s af=%s paused=%s state=%d done=%d/%d err=%s" % (
                            e.queued, e.awaiting_files, st.paused, st.state,
                            st.total_wanted_done, st.total_wanted, e.error,
                        )
                    except RuntimeError as exc:
                        info = "HANDLE DEAD: %s" % exc
                    rows.append("%s %s" % (e.name[:12], info))
            print(" | ".join(rows))
            time.sleep(0.5)
    finally:
        engine.stop()
        seeder.pause()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
