"""
Giving Player 2 the same DLC as Player 1.

DLC ownership is per player, not per game: when the game asks a player's client what it owns
(`OakPlayerController:Client_RequestDLCEntitlements`), the client answers with an encoded list
(`GbxPlayerController:ServerRefreshPlayerEntitlementFacts`). Player 1's lists the DLC the account owns; Player 2 has
no account, so its list is empty and DLC Vault Hunters show a padlock in Player 2's character select.

So whenever Player 2 sends its list, send Player 1's instead. The list is plain text with no account id in it, and
the DLC still has to be installed and owned — this only stops the second player on the same screen from being
treated as a different customer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from unrealsdk import logging

from . import players

if TYPE_CHECKING:
    from unrealsdk.unreal import UObject, WrappedStruct

LOG_PREFIX = "[BL4SS]"

_p1_snapshot: str | None = None  # Player 1's most recent entitlement list
_requesting = False  # asking P1's client for its list, which comes back through this same hook
_shared_logged = False
_push_logged = False


def on_refresh(pc: UObject, args: WrappedStruct) -> None:
    """Called for every ServerRefreshPlayerEntitlementFacts: remember Player 1's list, substitute it for the others'."""
    global _p1_snapshot, _shared_logged
    index = players.index_of(pc)
    if index is None:
        return
    if index == 0:
        _p1_snapshot = args.EncodedSnapshot
        return
    snapshot = _p1_snapshot if _p1_snapshot is not None else _ask_p1()
    if not snapshot or snapshot == args.EncodedSnapshot:
        return
    args.EncodedSnapshot = snapshot
    if not _shared_logged:
        _shared_logged = True
        logging.info(f"{LOG_PREFIX} Player {index + 1} given Player 1's DLC entitlements")


def _ask_p1() -> str | None:
    """Player 2 refreshed first: ask Player 1's client for its list now (it answers through on_refresh)."""
    global _requesting
    if _requesting:
        return None
    pcs = players.controllers()
    if not pcs:
        return None
    _requesting = True
    try:
        pcs[0].Client_RequestDLCEntitlements()
    finally:
        _requesting = False
    return _p1_snapshot


def share_with_p2() -> None:
    """
    Push Player 1's entitlements to Player 2 now.

    Called when Player 2 joins and again whenever a menu opens: at join Player 1's client may not have answered yet
    (the store query is asynchronous), and the game refreshes Player 2's own entitlements again later. Pushing again
    before each menu is cheap — a local call — and leaves the character select reading Player 1's DLC.
    """
    global _push_logged
    pcs = players.controllers()
    if len(pcs) < 2:
        return
    snapshot = _p1_snapshot if _p1_snapshot is not None else _ask_p1()
    if not snapshot:
        return  # Player 1's client hasn't answered yet; try again on the next menu
    pcs[1].ServerRefreshPlayerEntitlementFacts(snapshot)
    if not _push_logged:
        _push_logged = True
        logging.info(f"{LOG_PREFIX} Player 2 given Player 1's DLC entitlements")


def reset() -> None:
    """Player 2 left: log the next push again (Player 1's list is still valid and is kept)."""
    global _push_logged, _shared_logged
    _push_logged = False
    _shared_logged = False
