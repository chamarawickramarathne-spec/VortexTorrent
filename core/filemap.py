"""Mapping between torrent file selection and libtorrent's storage layout.

Hybrid (v1+v2) torrents insert hidden pad files between payload files to
satisfy BEP 52 alignment. Those pad entries are part of the file_storage,
so they must be hidden from the UI's file lists and skipped when applying
per-file priorities - otherwise a user's selection shifts onto the wrong
files.
"""

import libtorrent as lt


def _is_pad(files, index):
    try:
        return bool(files.file_flags(index) & lt.file_storage.flag_pad_file)
    except RuntimeError:
        return False


def visible_files(files):
    """[(path, size)] for real payload files only (pad files excluded)."""
    return [
        (files.file_path(i), files.file_size(i))
        for i in range(files.num_files())
        if not _is_pad(files, i)
    ]


def expand_priorities(files, priorities):
    """Expand a compact priority list (real files only) to the full storage
    layout, assigning dont-download to pad files."""
    expanded = []
    index = 0
    for i in range(files.num_files()):
        if _is_pad(files, i):
            expanded.append(0)
        else:
            expanded.append(int(priorities[index]) if index < len(priorities) else 1)
            index += 1
    return expanded
