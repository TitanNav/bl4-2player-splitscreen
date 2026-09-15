"""
Keeping one player's full-screen menu from blurring the other player's half.

Opening a full-screen menu makes the game set r.ScreenPercentage to 10 — a global setting, so in split-screen the other
half renders at 10%. Console variables keep the priority of whoever last set them, and a console-issued value outranks
the menu's; the in-game Upscaling Quality option still applies afterwards. So re-issuing the current value once from
the console keeps every later menu drop from taking effect.
"""

from __future__ import annotations

import unrealsdk
from unrealsdk import logging

from . import players

LOG_PREFIX = "[BL4SS]"
CVAR = "r.ScreenPercentage"
MENU_DROP = 10.0

_locked = False


def lock_render_scale() -> None:
    """With 2+ local players and no menu drop in effect, re-issue r.ScreenPercentage at console priority (once)."""
    global _locked
    if _locked:
        return
    pcs = players.controllers()
    if len(pcs) < 2:
        return
    ksl = unrealsdk.find_class("KismetSystemLibrary").ClassDefaultObject
    value = ksl.GetConsoleVariableFloatValue(CVAR)
    if value <= MENU_DROP:
        return  # a menu is open right now; try again on the next call
    ksl.ExecuteConsoleCommand(pcs[0], f"{CVAR} {value:g}", pcs[0])
    _locked = True
    logging.info(f"{LOG_PREFIX} split-screen render scale locked at {value:g}%")
