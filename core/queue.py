"""Active-download queue management.

Enforces the max-active-downloads limit by tracking which torrents are
actively downloading and promoting queued torrents when slots free up.
"""

import libtorrent as lt


STATE_NAMES = {
    lt.torrent_status.states.queued_for_checking: "Queued",
    lt.torrent_status.states.checking_files: "Checking",
    lt.torrent_status.states.checking_resume_data: "Checking resume",
    lt.torrent_status.states.downloading_metadata: "Fetching metadata",
    lt.torrent_status.states.downloading: "Downloading",
    lt.torrent_status.states.allocating: "Allocating",
    lt.torrent_status.states.finished: "Finished",
    lt.torrent_status.states.seeding: "Seeding",
}


def count_active(entries):
    """Count torrents that are actively downloading (not queued, not paused,
    not awaiting file selection, not already complete)."""
    active = 0
    for entry in entries:
        if entry.queued:
            continue
        if entry.awaiting_files:
            continue
        try:
            st = entry.handle.status()
        except RuntimeError:
            continue
        if st.paused:
            continue
        total = st.total_wanted or 0
        if total > 0 and st.total_wanted_done >= total:
            continue
        active += 1
    return active


def slot_available(entries, max_active):
    """True when another torrent may start (0 = unlimited)."""
    if max_active <= 0:
        return True
    return count_active(entries) < max_active


def promote_next(entries, max_active):
    """Resume the first queued torrent if a slot is free. Returns True if
    a torrent was promoted."""
    if max_active <= 0:
        return False
    if count_active(entries) >= max_active:
        return False
    for entry in entries:
        if entry.queued:
            entry.queued = False
            entry.handle.resume()
            return True
    return False
