import time


class TorrentEntry:
    def __init__(self, handle, name, info_hash, save_path, source):
        self.handle = handle
        self.name = name
        self.info_hash = info_hash
        self.save_path = save_path
        self.source = source
        self.added_at = time.time()
        self.error = None

    @property
    def id(self):
        return str(self.info_hash)
