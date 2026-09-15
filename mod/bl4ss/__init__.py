"""
BL4 2-Player Split-Screen Unlocked — two-player local split-screen for Borderlands 4 on PC.

The game already ships couch co-op; on PC it never finishes setting up the second local player. This mod:
- adds Player 2 on the main menu when a second controller is connected (or with a hotkey), so P2 can pick a save
  from the game's own "Load Vault Hunter" menu;
- offers a hotkey that swaps the two players' platform users while a new P2 character is created — the Shared
  Progression screen only accepts the signed-in platform user;
- marks P2 "client ready" when it travels, so it actually arrives in the world (see native.py);
- keeps one player's menu from dropping the other half to 10% render resolution (see render.py);
- keeps P1's mouse look while P2's menu is open, and makes P2's controller cursor visible in menus.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from mods_base import BoolOption, ButtonOption, build_mod, command, hook, keybind
from unrealsdk import logging
from unrealsdk.hooks import Type

from . import native, players, render

if TYPE_CHECKING:
    from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct

__version__ = "0.9.0"
__author__ = "TitanNav"

LOG_PREFIX = "[BL4SS]"
UI_SCRIPT = "/Game/UI/Scripts/ui_script_menu_base.ui_script_menu_base_C"
TITLE_MENU = "def_title_menu_oak"

auto_join = BoolOption(
    "Auto-join Player 2",
    True,
    description="Add Player 2 on the main menu whenever a second controller is connected.",
)

_p2_dismissed = False  # P2 was removed by hotkey or Leave Split Screen; don't auto re-add this session
_had_p2 = False
_swapped = False


def _quoted_name(value: object) -> str:
    """First quoted name in a GbxDefPtr / GameDataHandle repr, e.g. FGameDataHandle(24576, 'World_P.X', None)."""
    text = repr(value)
    return text.split("'")[1] if "'" in text else ""


def _widget_name(args: WrappedStruct) -> str:
    return _quoted_name(args.OwningWidgetDef)


def _same(a: UObject | None, b: UObject | None) -> bool:
    return a is not None and b is not None and a._get_address() == b._get_address()


def _swap_out(reason: str) -> None:
    """Give each player its own platform user back, if a creation swap is in effect."""
    global _swapped
    if _swapped:
        if len(players.controllers()) >= 2:
            players.set_platform_users(0, 1)
        _swapped = False
        logging.info(f"{LOG_PREFIX} control swap ended ({reason})")


def _try_auto_join(reason: str) -> None:
    global _had_p2, _p2_dismissed
    count = len(players.controllers())
    if count >= 2:
        _had_p2 = True
        return
    _swap_out("Player 2 gone")
    if _had_p2:
        # P2 existed earlier this session and is gone now: the players chose Leave Split Screen.
        _p2_dismissed = True
        _had_p2 = False
    if count == 1 and auto_join.value and not _p2_dismissed and players.second_gamepad_connected():
        logging.info(f"{LOG_PREFIX} auto-join ({reason})")
        if players.add_p2():
            _had_p2 = True


@hook("/Script/OakGame.OakPlayerController:ClientNotifyTeleporting", Type.POST)
def on_travel_notice(obj: UObject, args: WrappedStruct, _ret: Any, _func: BoundFunction) -> None:
    try:
        # The creation swap ends on the first notice that names a station: picking the class moves the player to a
        # front-end station ('Intro_P.Intro_P_mainmenu'), so control returns by itself once creation is done — and a
        # swap is never carried into the world. Completion notices (station 'None') are ignored.
        station = _quoted_name(args.station)
        if station not in ("", "None"):
            _swap_out(f"travel to {station}")
            _end_wake(f"cut short by travel to {station}")
        index = players.index_of(obj)
        if index is None:
            return
        if index >= 1 and native.is_ready(obj._get_address()) is False:
            ok = native.mark_ready(obj._get_address())
            logging.info(f"{LOG_PREFIX} Player {index + 1} marked ready for arrival ({'ok' if ok else 'FAILED'})")
        render.lock_render_scale()
    except Exception as e:  # noqa: BLE001 - a hook must never break the game's travel
        logging.error(f"{LOG_PREFIX} travel hook: {type(e).__name__}: {e}")


@hook(f"{UI_SCRIPT}:MenuOpen", Type.POST)
def on_menu_open(_obj: UObject, args: WrappedStruct, _ret: Any, _func: BoundFunction) -> None:
    try:
        pcs = players.controllers()
        if pcs and _widget_name(args) == TITLE_MENU and _same(args.WorldContextObject, pcs[0]):
            _try_auto_join("title menu opened")
        elif len(pcs) >= 2 and pcs[0].Pawn is not None and not _same(args.WorldContextObject, pcs[0]):
            if _same(args.WorldContextObject, pcs[1]):
                _wake_p2_cursor()
            _keep_p1_mouse_look()
    except Exception as e:  # noqa: BLE001
        logging.error(f"{LOG_PREFIX} menu-open hook: {type(e).__name__}: {e}")


# Actions a few frames after a menu opens, driven by a HUD widget tick (two tick per frame).
_scheduled: list[tuple[int, str, Callable[[], None]]] = []  # (ticks left, label, action)


def _schedule(ticks: int, label: str, action: Callable[[], None]) -> None:
    _scheduled.append((ticks, label, action))


@hook("/Script/GbxUIUMG.GbxUIUMGTickWidget:BP_TickWidget", Type.POST)
def on_widget_tick(_obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction) -> None:
    if not _scheduled:
        return
    due = [(label, action) for ticks, label, action in _scheduled if ticks <= 1]
    _scheduled[:] = [(ticks - 1, label, action) for ticks, label, action in _scheduled if ticks > 1]
    for label, action in due:
        try:
            action()
        except Exception as e:  # noqa: BLE001
            logging.error(f"{LOG_PREFIX} {label}: {type(e).__name__}: {e}")


# In the world, another player's menu switches the one shared game viewport into a UI input mode, where the mouse is
# only captured while a button is held: P1's next click releases it and P1 loses mouse look (holding aim keeps it).
# Re-applying P1's game-only input mode restores permanent capture; P2's menu keeps working with its controller.
# Done when the menu opens and again a few frames later, in case the menu applies its mode late.
MOUSE_LOOK_RETRY_TICKS = 40
_mouse_look_logged = False


def _keep_p1_mouse_look() -> None:
    global _mouse_look_logged
    if players.keep_mouse_look(0):
        _schedule(MOUSE_LOOK_RETRY_TICKS, "mouse-look retry", lambda: players.keep_mouse_look(0))
        if not _mouse_look_logged:
            _mouse_look_logged = True
            logging.info(f"{LOG_PREFIX} Player 2 menu opened: keeping Player 1's mouse look")


# P2's controller cursor in menus stays invisible (the menu still follows it) until P2's menu has received real mouse
# movement while P2 owned the mouse. On P2's first menu in the world: swap platform users (P2 gets the mouse) and
# nudge the OS mouse; on the first widget tick of a later frame (the nudge has been read by then) nudge it back, swap
# back and re-apply P1's mouse look. The swap lasts one frame — the menu-open frame. Once per Player 2.
# While P1's own menu is open the mouse isn't captured and the nudge goes to whatever is under the pointer, so for that
# frame the pointer is parked over P2's half and then put back.
WAKE_STALL_SECONDS = 1.0  # the wake takes one frame; longer means the widget ticks stopped
_woken: set[int] = set()  # Player 2 local-player addresses whose cursor was woken
_waking = False
_wake_started = 0.0
_wake_frame = 0
_wake_pointer: tuple[int, int] | None = None  # where to put the pointer back


def _wake_p2_cursor() -> None:
    global _waking, _wake_started, _wake_frame, _wake_pointer
    lps, pcs = players.local_players(), players.controllers()
    if _waking or _swapped or len(lps) < 2 or len(pcs) < 2 or lps[1]._get_address() in _woken:
        return
    _wake_pointer = None
    if pcs[0].bShowMouseCursor:
        _wake_pointer = players.pointer_position()
        players.set_pointer_position(*players.p2_half_centre())
    _woken.add(lps[1]._get_address())
    _waking = True
    _wake_started = time.monotonic()
    _wake_frame = players.frame_count()
    players.set_platform_users(1, 0)
    players.nudge_mouse(1)
    _schedule(1, "cursor wake", _finish_wake)


def _finish_wake() -> None:
    if not _waking:
        return
    if players.frame_count() <= _wake_frame:
        _schedule(1, "cursor wake", _finish_wake)  # still the menu-open frame: the nudge hasn't been read yet
        return
    players.nudge_mouse(-1)
    _end_wake("done")


@hook(f"{UI_SCRIPT}:MenuClose", Type.POST)
def on_menu_close(_obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction) -> None:
    try:
        # Never leave the users swapped if the widget ticks stop. Menus also close while one opens, so only step in
        # once the wake has clearly stalled.
        if _waking and time.monotonic() - _wake_started > WAKE_STALL_SECONDS:
            _end_wake("cut short: a menu closed")
    except Exception as e:  # noqa: BLE001
        logging.error(f"{LOG_PREFIX} menu-close hook: {type(e).__name__}: {e}")


def _end_wake(reason: str) -> None:
    global _waking, _wake_pointer
    if not _waking:
        return
    _waking = False
    _scheduled[:] = [entry for entry in _scheduled if entry[1] != "cursor wake"]
    lps = players.local_players()
    if len(players.controllers()) >= 2:
        players.set_platform_users(0, 1)
    players.keep_mouse_look(0)
    if _wake_pointer is not None:
        players.set_pointer_position(*_wake_pointer)
        _wake_pointer = None
    if reason == "done":
        logging.info(f"{LOG_PREFIX} Player 2 menu cursor enabled")
    else:
        if len(lps) >= 2:
            _woken.discard(lps[1]._get_address())  # try again on P2's next menu
        logging.info(f"{LOG_PREFIX} Player 2 menu cursor wake {reason}")


SWAP_DESCRIPTION = (
    "On the main menu, while creating a new Player 2 character: use on the Shared Progression screen, then choose"
    " On/Off and the class with keyboard/mouse or the first controller. Control returns to normal by itself once the"
    " class is picked; use again to cancel before that."
)


def toggle_p2() -> None:
    """Add Player 2 on the main menu, or remove it if present."""
    global _p2_dismissed, _had_p2
    try:
        if not players.on_main_menu():
            logging.info(f"{LOG_PREFIX} Player 2 can only be added or removed on the main menu")
            return
        if len(players.controllers()) >= 2:
            _swap_out("Player 2 removed")
            players.remove_p2()
            _p2_dismissed = True
            _had_p2 = False
        elif players.add_p2():
            _p2_dismissed = False
            _had_p2 = True
    except Exception as e:  # noqa: BLE001
        logging.error(f"{LOG_PREFIX} add/remove Player 2: {type(e).__name__}: {e}")


def toggle_creation_swap() -> None:
    """Swap the players' platform users for P2 character creation, or cancel the swap."""
    global _swapped
    try:
        if _swapped:
            _swap_out("cancelled")
            return
        if not players.on_main_menu() or len(players.controllers()) < 2:
            logging.info(f"{LOG_PREFIX} control swap needs Player 2 on the main menu")
            return
        players.set_platform_users(1, 0)
        _swapped = True
        logging.info(f"{LOG_PREFIX} control swapped: keyboard/mouse and controller 1 now drive Player 2's menu")
    except Exception as e:  # noqa: BLE001
        logging.error(f"{LOG_PREFIX} control swap: {type(e).__name__}: {e}")


# Three ways to trigger each action. Hotkeys don't reach the mod while the title menu has keyboard focus, so the
# console command and the mods-menu button are the reliable routes there.
p2_hotkey = keybind("Add / Remove Player 2", "F7", toggle_p2,
                    description="On the main menu: add Player 2, or remove it if present.")
swap_hotkey = keybind("Swap control for P2 character creation", "F8", toggle_creation_swap,
                      description=SWAP_DESCRIPTION)


@command("bl4ss_p2", description="Add Player 2 on the main menu, or remove it if present.")
def p2_command(_args: argparse.Namespace) -> None:
    toggle_p2()


@command("bl4ss_swap", description=SWAP_DESCRIPTION)
def swap_command(_args: argparse.Namespace) -> None:
    toggle_creation_swap()


p2_button = ButtonOption(
    "Add / Remove Player 2",
    on_press=lambda _: toggle_p2(),
    description="On the main menu: add Player 2, or remove it if present. (Console: bl4ss_p2, hotkey F7)",
)
swap_button = ButtonOption(
    "Swap control for P2 character creation",
    on_press=lambda _: toggle_creation_swap(),
    description=SWAP_DESCRIPTION + " (Console: bl4ss_swap, hotkey F8)",
)


def on_enable() -> None:
    try:
        native.setter()  # scan now (a brief hitch at load), not in the middle of the first travel
        if players.on_main_menu():
            _try_auto_join("mod enabled on the main menu")
    except Exception as e:  # noqa: BLE001
        logging.error(f"{LOG_PREFIX} enable: {type(e).__name__}: {e}")


def on_disable() -> None:
    try:
        _swap_out("mod disabled")
        _end_wake("cut short: mod disabled")
    except Exception as e:  # noqa: BLE001
        logging.error(f"{LOG_PREFIX} disable: {type(e).__name__}: {e}")


mod = build_mod(options=[auto_join, p2_button, swap_button])
