"""Snapshot building and resume-data persistence for the torrent engine.

Extracted from engine.py to keep individual modules under 300 lines.
"""

import os

import libtorrent as lt

from core import partfile
from core.queue import STATE_NAMES


def snapshot(torrents, lock):
    """Build a list of status dicts for all tracked torrents."""
    snap = []
    with lock:
        entries = list(torrents.values())
    for entry in entries:
        try:
            st = entry.handle.status()
        except RuntimeError:
            continue
        state = STATE_NAMES.get(st.state, "Idle")
        if st.paused:
            state = "Paused"
        total = st.total_wanted or st.total
        done = st.total_wanted_done
        progress = st.progress
        if total and done >= total:
            state = "Completed"
        if entry.queued:
            state = "Queued"
        if st.total_wanted:
            eta_secs = eta(st)
        else:
            eta_secs = 0
        snap.append(
            {
                "id": entry.id,
                "name": entry.name or st.name,
                "size": total,
                "done": done,
                "progress": progress,
                "download_rate": st.download_rate,
                "upload_rate": st.upload_payload_rate,
                "peers": st.num_peers,
                "seeds": st.num_seeds,
                "state": state,
                "eta": eta_secs,
                "error": entry.error,
                "save_path": entry.save_path,
            }
        )
    return snap


def eta(st):
    """Estimate time remaining in seconds for a torrent status."""
    rate = st.download_rate
    if rate <= 0:
        return 0
    remaining = st.total_wanted - st.total_wanted_done
    return remaining / rate


def persist_resume(alert, resume_dir, torrents, lock, orphan_parts):
    """Write resume data to disk and queue part-file cleanup."""
    if not hasattr(alert, "resume_data"):
        return
    ih = str(alert.handle.info_hash())
    target = os.path.join(resume_dir, "%s.fastresume" % ih)
    data = lt.bencode(alert.resume_data)
    with open(target, "wb") as f:
        f.write(data)
    with lock:
        entry = torrents.get(ih)
    if entry:
        with lock:
            partfile.queue_cleanup(orphan_parts, entry.handle, entry.save_path)


def save_all_resume_data(torrents, lock):
    """Request resume-data save for every tracked torrent."""
    with lock:
        handles = [e.handle for e in torrents.values()]
    for h in handles:
        h.save_resume_data()
