"""ProjectRio tag lookups for the validator.

A match's stat file records a ``TagSetID``; the gecko-code mods active for that
match are the tags in that tag set. This resolves TagSetID -> tag names via the
ProjectRio API, caching the whole tag-set list in memory so a large-dataset
validation run makes a single API call rather than one per file.
"""

import json
import urllib.request

_BASE = "https://api.projectrio.app"
_TAGSET_LIST = "/tag_set/list"  # POST; returns {"Tag Sets": [...]}

# Cache: {tag_set_id: frozenset(tag_name, ...)}. Populated once per process.
_tag_sets_by_id = None


def _load_tag_sets():
    global _tag_sets_by_id
    if _tag_sets_by_id is not None:
        return _tag_sets_by_id
    req = urllib.request.Request(_BASE + _TAGSET_LIST, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    _tag_sets_by_id = {
        entry["id"]: frozenset(t["name"] for t in entry.get("tags", []))
        for entry in payload.get("Tag Sets", [])
    }
    return _tag_sets_by_id


def tags_for_tag_set(tag_set_id):
    """Frozenset of gecko-mod tag names for a TagSetID (cached).

    Returns an empty set for a missing/unknown id (e.g. local games).
    """
    if tag_set_id is None:
        return frozenset()
    return _load_tag_sets().get(tag_set_id, frozenset())


def active_tags_for_stat(stat):
    """Active gecko-mod tag names for a parsed stat file, via its TagSetID."""
    return tags_for_tag_set(stat.statJson.get("TagSetID"))


def clear_cache():
    """Drop the cached tag-set list (forces a refetch on next lookup)."""
    global _tag_sets_by_id
    _tag_sets_by_id = None
