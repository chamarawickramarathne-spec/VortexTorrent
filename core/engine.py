"""libtorrent session wrapper with threaded alert loop.

Core engine that manages the BitTorrent session, torrent lifecycle,
and part-file cleanup orchestration. Queue management is delegated to
core.queue and snapshot/resume logic to core.torrent_ops.
"""

import os
import threading
import time

import libtorrent as lt

from core import filemap
from core import partfile
from core.models import TorrentEntry
from core import queue as q
from core import torrent_ops


class TorrentEngine:
    def __init__(self, config_dir, on_alert=None):
        self.config_dir = config_dir
        self.resume_dir = os.path.join(config_dir, "resume")
        os.makedirs(self.resume_dir, exist_ok=True)
        self.session = None
        self.lock = threading.Lock()
        self.torrents = {}
        self.running = False
        self.on_alert = on_alert
        self._files_ready = []
        self._orphan_parts = []
        self.max_active = 2

    def start(self, port=6881, download_rate=0, upload_rate=0, max_active_downloads=2):
        self.max_active = max(0, int(max_active_downloads))
        settings = {
            "listen_interfaces": "0.0.0.0:%d" % port,
            "enable_dht": True,
            "enable_upnp": True,
            "enable_natpmp": True,
            "active_downloads": 6,
            "active_seeds": 0,
            "unchoke_slots_limit": 0,
            "num_optimistic_unchoke_slots": 0,
            "download_rate_limit": int(download_rate),
            "upload_rate_limit": int(upload_rate),
            "alert_mask": lt.alert.category_t.error_notification
            | lt.alert.category_t.status_notification
            | lt.alert.category_t.storage_notification,
        }
        self.session = lt.session(settings)
        self.running = True
        threading.Thread(target=self._alert_loop, daemon=True).start()

    def _alert_loop(self):
        while self.running:
            for alert in self.session.pop_alerts():
                self._handle_alert(alert)
            with self.lock:
                partfile.drain_orphans(self._orphan_parts)
            self._promote_next()
            time.sleep(0.05)

    def _handle_alert(self, alert):
        if isinstance(alert, lt.metadata_received_alert):
            with self.lock:
                entry = self.torrents.get(str(alert.handle.info_hash()))
                if entry:
                    entry.name = alert.handle.name()
                    entry.awaiting_files = True
                    self._files_ready.append(entry.id)
            alert.handle.pause()
        elif isinstance(alert, lt.torrent_error_alert):
            with self.lock:
                entry = self.torrents.get(str(alert.handle.info_hash()))
                if entry:
                    entry.error = alert.message()
        elif isinstance(alert, lt.save_resume_data_alert):
            torrent_ops.persist_resume(
                alert, self.resume_dir, self.torrents,
                self.lock, self._orphan_parts,
            )
        elif isinstance(alert, lt.cache_flushed_alert):
            with self.lock:
                entry = self.torrents.get(str(alert.handle.info_hash()))
            if entry:
                with self.lock:
                    partfile.queue_cleanup(
                        self._orphan_parts, entry.handle, entry.save_path
                    )
        elif isinstance(alert, lt.torrent_finished_alert):
            alert.handle.pause()
            alert.handle.save_resume_data(lt.torrent_handle.flush_disk_cache)
            self._promote_next()
        if self.on_alert:
            self.on_alert(alert)

    def add_torrent_file(self, path, save_path, priorities=None, paused=False):
        info = lt.torrent_info(path)
        params = self._resume_params(info.info_hash())
        resumed = params is not None
        if params is None:
            params = lt.add_torrent_params()
            params.ti = info
        else:
            params.ti = info
        params.save_path = save_path
        if priorities is not None:
            params.file_priorities = filemap.expand_priorities(info.files(), priorities)
        params.flags &= ~lt.torrent_flags.auto_managed
        queued = not paused and not self._slot_available()
        if queued or paused:
            params.flags |= lt.torrent_flags.paused
        else:
            params.flags &= ~lt.torrent_flags.paused
        handle = self.session.add_torrent(params)
        return self._register(handle, save_path, "file", resumed=resumed,
                              queued=queued)

    def add_magnet(self, uri, save_path, paused=False):
        parsed = lt.parse_magnet_uri(uri)
        params = self._resume_params(parsed.info_hash)
        resumed = params is not None
        if params is None:
            params = parsed
        params.save_path = save_path
        params.flags &= ~lt.torrent_flags.auto_managed
        if not paused:
            params.flags &= ~lt.torrent_flags.paused
        else:
            params.flags |= lt.torrent_flags.paused
        handle = self.session.add_torrent(params)
        return self._register(handle, save_path, "magnet", resumed=resumed)

    def file_list_from_file(self, path):
        info = lt.torrent_info(path)
        return filemap.visible_files(info.files())

    def file_list(self, torrent_id):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if not entry:
            return None
        try:
            tf = entry.handle.torrent_file()
        except RuntimeError:
            return None
        if tf is None:
            return None
        return filemap.visible_files(tf.files())

    def set_file_priorities(self, torrent_id, priorities):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if not entry:
            return
        try:
            tf = entry.handle.torrent_file()
        except RuntimeError:
            return
        if tf is None:
            return
        expanded = filemap.expand_priorities(tf.files(), priorities)
        entry.handle.prioritize_files(expanded)

    def take_files_ready(self):
        with self.lock:
            ready = list(self._files_ready)
            self._files_ready.clear()
        return ready

    def _resume_params(self, info_hash):
        resume_file = os.path.join(self.resume_dir, "%s.fastresume" % str(info_hash))
        if not os.path.exists(resume_file):
            return None
        with open(resume_file, "rb") as f:
            return lt.read_resume_data(f.read())

    def _register(self, handle, save_path, source, resumed=False, queued=False):
        entry = TorrentEntry(
            handle,
            handle.name() or "Fetching metadata...",
            handle.info_hash(),
            save_path,
            source,
        )
        entry.queued = queued
        with self.lock:
            self.torrents[entry.id] = entry
        if resumed:
            partfile.schedule_cleanup(handle)
        return entry

    def remove(self, torrent_id, delete_files=False):
        with self.lock:
            entry = self.torrents.pop(torrent_id, None)
        if entry is None:
            return
        entry.handle.save_resume_data()
        if delete_files:
            self.session.remove_torrent(entry.handle, lt.options_t.delete_files)
        else:
            with self.lock:
                partfile.queue_cleanup(
                    self._orphan_parts, entry.handle, entry.save_path
                )
            self.session.remove_torrent(entry.handle)
        self._promote_next()

    def pause(self, torrent_id):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if entry:
            entry.queued = False
            entry.handle.save_resume_data()
            entry.handle.pause()
            self._promote_next()

    def resume(self, torrent_id):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if entry:
            entry.queued = False
            entry.awaiting_files = False
            entry.handle.resume()

    def activate(self, torrent_id):
        """Resume after file selection unless the active limit is reached."""
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if entry is None:
            return
        entry.awaiting_files = False
        with self.lock:
            others = [e for e in self.torrents.values() if e.id != torrent_id]
            if not q.slot_available(others, self.max_active):
                entry.queued = True
                entry.handle.pause()
                return
            entry.queued = False
            entry.handle.resume()

    def pause_all(self):
        with self.lock:
            handles = [e.handle for e in self.torrents.values()]
        for h in handles:
            h.pause()

    def resume_all(self):
        with self.lock:
            handles = [e.handle for e in self.torrents.values()]
        for h in handles:
            h.resume()

    def set_max_active_downloads(self, n):
        self.max_active = max(0, int(n))
        self._promote_next()

    def _slot_available(self, entries=None):
        """True when another torrent may start (0 = unlimited)."""
        if entries is None:
            with self.lock:
                entries = list(self.torrents.values())
        return q.slot_available(entries, self.max_active)

    def _promote_next(self):
        with self.lock:
            entries = list(self.torrents.values())
        q.promote_next(entries, self.max_active)

    def apply_speed_limits(self, download_rate):
        self.session.apply_settings({"download_rate_limit": int(download_rate)})

    def apply_port(self, port):
        self.session.apply_settings({"listen_interfaces": "0.0.0.0:%d" % port})

    def save_all_resume_data(self):
        torrent_ops.save_all_resume_data(self.torrents, self.lock)

    def snapshot(self):
        return torrent_ops.snapshot(self.torrents, self.lock)

    def stop(self):
        self.running = False
        self.save_all_resume_data()
        time.sleep(0.5)
        with self.lock:
            entries = list(self.torrents.values())
        for e in entries:
            try:
                self.session.remove_torrent(e.handle)
            except RuntimeError:
                pass
        deadline = time.time() + 5.0
        while self._orphan_parts and time.time() < deadline:
            with self.lock:
                partfile.drain_orphans(self._orphan_parts)
            time.sleep(0.1)
