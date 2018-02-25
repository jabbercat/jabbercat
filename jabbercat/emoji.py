import collections
import json
import logging
import typing
import re


logger = logging.getLogger(__name__)


EmojiInfo = collections.namedtuple(
    "EmojiInfo",
    [
        "emoji",
        "description",
        "aliases",
        "supports_fitzpatrick",
    ]
)


def _info_from_emoji_java(item):
    try:
        return EmojiInfo(
            emoji=item["emoji"],
            description=item["description"],
            aliases=list(item["aliases"]),
            supports_fitzpatrick=item["supports_fitzpatrick"],
        )
    except KeyError:
        return None


def _info_from_gemoji(item):
    try:
        return EmojiInfo(
            emoji=item["emoji"],
            description=item["description"],
            aliases=list(item["aliases"]),
            supports_fitzpatrick=False,  # no info, defaulting
        )
    except KeyError:
        return None


def _generate_gender_substitutes(strs):
    for s in strs:
        yield s
        new = s.replace("♂️", "♂").replace("♀️", "♀")
        if new != s:
            yield new


def _generate_substitutes(s):
    yield from _generate_gender_substitutes([s])


class EmojiDatabase:
    FITZPATRICK_MODIFIERS = [
        "🏻", "🏼", "🏽", "🏾", "🏿"
    ]

    def __init__(self):
        super().__init__()
        self._emoji_re = re.compile(r"")
        self._emoji_or_space_re = re.compile(r"\s")
        self._codepoints_index = {}
        self._emoji = []
        self._alias_index = {}

    def _merge_info(self, info):
        short_modifiers = [""]
        long_modifiers = short_modifiers + self.FITZPATRICK_MODIFIERS

        codepoint_re_parts = [self._emoji_re.pattern]

        for info_item in info:
            try:
                existing, _ = self._codepoints_index[info_item.emoji]
            except KeyError:
                pass
            else:
                # merge?!
                if (not existing.supports_fitzpatrick and
                        info_item.supports_fitzpatrick):
                    # patch info_item and remove old one, this one’s better
                    self._emoji.remove(existing)
                    info_item.aliases.extend(
                        set(existing.aliases) - set(info_item.aliases)
                    )
                else:
                    existing_aliases = set(existing.aliases)
                    new_aliases = set(info_item.aliases) - existing_aliases
                    existing.aliases.extend(new_aliases)
                    for alias in new_aliases:
                        self._alias_index[alias] = existing
                    continue

            self._emoji.append(info_item)

            modifiers = short_modifiers
            if info_item.supports_fitzpatrick:
                modifiers = long_modifiers

            for emoji_subs in _generate_substitutes(info_item.emoji):
                for modifier in modifiers:
                    modified_emoji = emoji_subs + modifier
                    codepoint_re_parts.append(
                        "".join(r"\U{:08x}".format(ord(ch))
                                for ch in modified_emoji)
                    )
                    self._codepoints_index[modified_emoji] = info_item, modifier

            for alias in info_item.aliases:
                self._alias_index[alias] = info_item

        codepoint_re = "|".join(codepoint_re_parts)
        self._emoji_re = re.compile(codepoint_re)
        self._emoji_or_space_re = re.compile(codepoint_re + r"|\s")
        self._emoji_or_space_multi_re = re.compile(r"({0})({0}|\s)*".format(
            codepoint_re,
        ))

    def merge_emoji_java(self, db):
        self._merge_info(filter(
            None,
            map(_info_from_emoji_java, db)
        ))

    def merge_gemoji(self, db):
        self._merge_info(filter(
            None,
            map(_info_from_gemoji, db)
        ))

    def load(self, db):
        self.merge_emoji_java(db)

    def save(self):
        return [
            {
                "emoji": info.emoji,
                "description": info.description,
                "aliases": list(info.aliases),
                "supports_fitzpatrick": info.supports_fitzpatrick,
            }
            for info in self._emoji
        ]

    @property
    def emoji_re(self):
        return self._emoji_re

    @property
    def emoji_or_space_re(self):
        return self._emoji_or_space_re

    @property
    def emoji_or_space_multi_re(self):
        return self._emoji_or_space_multi_re

    def get_by_emoji(self, emoji: str) -> typing.Tuple[EmojiInfo, str]:
        return self._codepoints_index[emoji]

    def get_by_alias(self, alias: str) -> EmojiInfo:
        return self._alias_index[alias]

    @property
    def emoji(self) -> typing.Sequence[EmojiInfo]:
        return self._emoji


DATABASE = EmojiDatabase()

try:
    with open("data/js/emoji.json", "r") as f:
        DATABASE.load(json.load(f))
except OSError:
    logger.warning("failed to load emoji database")
