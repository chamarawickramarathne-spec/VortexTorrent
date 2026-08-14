import os
import threading
import time

import libtorrent as lt

from core.models import TorrentEntry

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

    def start(self, port=6881, download_rate=0, upload_rate=0):
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
            time.sleep(0.05)

    def _handle_alert(self, alert):
        if isinstance(alert, lt.metadata_received_alert):
            with self.lock:
                entry = self.torrents.get(str(alert.handle.info_hash()))
                if entry:
                    entry.name = alert.handle.name()
                    self._files_ready.append(entry.id)
        elif isinstance(alert, lt.torrent_error_alert):
            with self.lock:
                entry = self.torrents.get(str(alert.handle.info_hash()))
                if entry:
                    entry.error = alert.message()
        elif isinstance(alert, lt.save_resume_data_alert):
            self._persist_resume(alert)
        elif isinstance(alert, lt.torrent_finished_alert):
            alert.handle.pause()
        if self.on_alert:
            self.on_alert(alert)

    def add_torrent_file(self, path, save_path, priorities=None, paused=False):
        info = lt.torrent_info(path)
        params = self._resume_params(info.info_hash())
        if params is None:
            params = lt.add_torrent_params()
            params.ti = info
        else:
            params.ti = info
        params.save_path = save_path
        if priorities is not None:
            params.file_priorities = list(priorities)
        params.flags &= ~lt.torrent_flags.auto_managed
        if not paused:
            params.flags &= ~lt.torrent_flags.paused
        else:
            params.flags |= lt.torrent_flags.paused
        handle = self.session.add_torrent(params)
        return self._register(handle, save_path, "file")

    def add_magnet(self, uri, save_path, paused=False):
        parsed = lt.parse_magnet_uri(uri)
        params = self._resume_params(parsed.info_hash)
        if params is None:
            params = parsed
        params.save_path = save_path
        params.flags &= ~lt.torrent_flags.auto_managed
        if not paused:
            params.flags &= ~lt.torrent_flags.paused
        else:
            params.flags |= lt.torrent_flags.paused
        handle = self.session.add_torrent(params)
        return self._register(handle, save_path, "magnet")

    def file_list_from_file(self, path):
        info = lt.torrent_info(path)
        return [(info.files().file_path(i), info.files().file_size(i)) for i in range(info.num_files())]

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
        files = tf.files()
        return [(files.file_path(i), files.file_size(i)) for i in range(files.num_files())]

    def set_file_priorities(self, torrent_id, priorities):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if entry:
            entry.handle.prioritize_files([int(p) for p in priorities])

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

    def _register(self, handle, save_path, source):
        entry = TorrentEntry(
            handle,
            handle.name() or "Fetching metadata...",
            handle.info_hash(),
            save_path,
            source,
        )
        with self.lock:
            self.torrents[entry.id] = entry
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
            self.session.remove_torrent(entry.handle)

    def pause(self, torrent_id):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if entry:
            entry.handle.save_resume_data()
            entry.handle.pause()

    def resume(self, torrent_id):
        with self.lock:
            entry = self.torrents.get(torrent_id)
        if entry:
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

    def apply_speed_limits(self, download_rate):
        self.session.apply_settings(
            {
                "download_rate_limit": int(download_rate),
            }
        )

    def apply_port(self, port):
        self.session.apply_settings({"listen_interfaces": "0.0.0.0:%d" % port})

    def save_all_resume_data(self):
        with self.lock:
            handles = [e.handle for e in self.torrents.values()]
        for h in handles:
            h.save_resume_data()

    def _persist_resume(self, alert):
        if not hasattr(alert, "resume_data"):
            return
        ih = str(alert.handle.info_hash())
        target = os.path.join(self.resume_dir, "%s.fastresume" % ih)
        data = lt.bencode(alert.resume_data)
        with open(target, "wb") as f:
            f.write(data)

    def snapshot(self):
        snap = []
        with self.lock:
            entries = list(self.torrents.values())
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
            if st.total_wanted:
                eta_secs = self._eta(st)
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

    def _eta(self, st):
        rate = st.download_rate
        if rate <= 0:
            return 0
        remaining = st.total_wanted - st.total_wanted_done
        return remaining / rate

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
