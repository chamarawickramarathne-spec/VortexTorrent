"""Cleanup helpers for libtorrent '.parts' part-files.

When a torrent contains skipped (priority 0) files, libtorrent stores the
portions of shared pieces belonging to those files in a hidden
'<save_path>\\.<info-hash-hex>.parts' file. libtorrent never deletes this
file when it becomes redundant, so finished torrents would leave it behind
forever. These helpers delete it once a torrent is fully complete and its
disk state has settled.
"""

import os

import libtorrent as lt

MAX_ORPHAN_TRIES = 200

_SETTLED_STATES = (
    lt.torrent_status.states.finished,
    lt.torrent_status.states.seeding,
)


def hash_hexes(handle):
    """Deduplicated hex strings of the handle's v1/v2/best info-hashes."""
    hexes = []
    try:
        ih = handle.info_hashes()
        candidates = (ih.v1, ih.v2, ih.get_best())
    except RuntimeError:
        return hexes
    for value in candidates:
        text = str(value)
        if text.strip("0") and text not in hexes:
            hexes.append(text)
    return hexes


def part_paths(save_path, hexes):
    """Existing '<save_path>\\.<hex>.parts' paths for the given hashes."""
    paths = []
    for text in hexes:
        path = os.path.join(save_path, ".%s.parts" % text)
        if os.path.isfile(path):
            paths.append(path)
    return paths


def is_complete(status):
    """True when every wanted byte of the torrent is on disk."""
    total = status.total_wanted or 0
    return total > 0 and status.total_wanted_done >= total


def ready_for_cleanup(status):
    """Complete AND no disk activity pending (paused/finished/seeding)."""
    if not is_complete(status):
        return False
    return bool(status.paused) or status.state in _SETTLED_STATES


def remove_parts(paths):
    removed = 0
    for path in paths:
        try:
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed


def cleanup_torrent(handle, save_path):
    """Delete a fully-downloaded torrent's part-file now. Returns count removed."""
    try:
        status = handle.status()
    except RuntimeError:
        return 0
    if not ready_for_cleanup(status):
        return 0
    return remove_parts(part_paths(save_path, hash_hexes(handle)))


def schedule_cleanup(handle):
    """Request flushed resume data so the engine can clean up when it arrives."""
    try:
        if ready_for_cleanup(handle.status()):
            handle.save_resume_data(lt.torrent_handle.flush_disk_cache)
    except RuntimeError:
        pass


def queue_cleanup(queue, handle, save_path):
    """Queue retry-based deletion of a complete torrent's part-file.

    Paths are queued whether or not they exist yet: libtorrent writes the
    part-file lazily (and rewrites it from cache after external deletion),
    so deletion must be retried across ticks until it survives.
    """
    try:
        if not ready_for_cleanup(handle.status()):
            return
        hexes = hash_hexes(handle)
    except RuntimeError:
        return
    paths = [os.path.join(save_path, ".%s.parts" % text) for text in hexes]
    if not paths:
        return
    for item in queue:
        if item[0] == paths:
            return
    queue.append([paths, MAX_ORPHAN_TRIES])


def drain_orphans(queue):
    """Retry queued deletions every tick until the retry budget runs out.

    Items are never dropped early: libtorrent may recreate the part-file
    from its write-back cache shortly after a successful deletion, so the
    retries must continue past the first removal.
    """
    for item in queue[:]:
        remove_parts(item[0])
        item[1] -= 1
        if item[1] <= 0:
            queue.remove(item)
