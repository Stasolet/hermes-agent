"""Regression: a slash-auth import before discord.py was installed poisons every profile.

A plugin hot-mount on a fresh venv imports ``adapter_slash_auth`` before the
dependency installer runs; the swallowed ImportError caches ``discord = None`` in
``sys.modules`` for the process lifetime, and ``adapter.py`` pulls the mixin in by
absolute import, so all multiplexed profile copies share the one poisoned module.
Every slash command then raised ``AttributeError: 'NoneType' object has no
attribute 'DMChannel'`` before the interaction ACK, which Discord surfaces as
«Приложение не отвечает» (seen live on all three profiles 2026-11-03).
"""
import plugins.platforms.discord.adapter_slash_auth as slash_auth
import plugins.platforms.discord.adapter_thread_titles as thread_titles


class _FakeUser:
    id = 371690660279091202


class _FakeChannel:
    id = 1567145989368971335


class _FakeInteraction:
    channel = _FakeChannel()
    channel_id = 1567145989368971335
    user = _FakeUser()
    guild = None


def _slash_mixin():
    mixin = object.__new__(slash_auth.DiscordSlashAuthMixin)
    mixin._discord_channel_keys_from_channel = lambda *a, **k: set()
    mixin._get_allowed_channels = lambda: set()
    mixin._get_ignored_channels = lambda: set()
    mixin._is_allowed_user = lambda *a, **k: True
    return mixin


def test_slash_auth_self_heals_a_discord_cached_as_none(monkeypatch):
    """A None cached at import time must not kill slash dispatch; the entry point re-resolves."""
    monkeypatch.setattr(slash_auth, "discord", None)
    allowed, reason = _slash_mixin()._evaluate_slash_authorization(_FakeInteraction())
    assert (allowed, reason) == (True, None)
    assert slash_auth.discord is not None
    assert hasattr(slash_auth.discord, "DMChannel")


def test_slash_auth_healthy_import_path_unaffected():
    assert _slash_mixin()._evaluate_slash_authorization(_FakeInteraction()) == (True, None)


def test_thread_titles_self_heals_a_discord_cached_as_none(monkeypatch):
    """Same poison class, other mixin: ``discord.Thread`` must not raise on a cached None."""
    monkeypatch.setattr(thread_titles, "discord", None)
    mixin = object.__new__(thread_titles.DiscordThreadTitlesMixin)
    mixin._semantic_thread_renames = thread_titles.SemanticThreadRenames()
    mixin._is_forum_parent = lambda *a, **k: False
    mixin._get_effective_topic = lambda *a, **k: None
    # A non-guild channel object: exercises the non-Thread branch without discord.Thread.
    class _Chan:
        id = 1
        name = "general"
        guild = None
    assert mixin._guild_channel_labels(_Chan()) == ("general", None)
    assert thread_titles.discord is not None
