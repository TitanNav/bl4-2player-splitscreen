"""Local players: finding them, adding/removing Player 2, controller detection and the platform-user swap."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import TYPE_CHECKING

import unrealsdk
from unrealsdk import logging

if TYPE_CHECKING:
    from unrealsdk.unreal import UObject

LOG_PREFIX = "[BL4SS]"
P2_CONTROLLER_ID = 1
RF_CLASS_DEFAULT_OBJECT = 0x10
PAD_TYPES = ("Gamepad", "Unspecified")
MOUSEEVENTF_MOVE = 0x0001
MOUSE_NUDGE_PIXELS = 12


def _statics(class_name: str) -> UObject:
    return unrealsdk.find_class(class_name).ClassDefaultObject


def _is_cdo(obj: UObject) -> bool:
    return bool(obj.ObjectFlags & RF_CLASS_DEFAULT_OBJECT) or obj.Name.startswith("Default__")


def game_instance() -> UObject | None:
    return next((o for o in unrealsdk.find_all("OakGameInstance", False) if not _is_cdo(o)), None)


def local_players() -> list[UObject]:
    gi = game_instance()
    return list(gi.LocalPlayers) if gi is not None else []


def controllers() -> list[UObject]:
    return [lp.PlayerController for lp in local_players() if lp.PlayerController is not None]


def index_of(controller: UObject) -> int | None:
    address = controller._get_address()
    return next((i for i, pc in enumerate(controllers()) if pc._get_address() == address), None)


def on_main_menu() -> bool:
    """P1 exists and has no pawn — the front end (menus run inside a world, so the map name can't tell)."""
    pcs = controllers()
    return bool(pcs) and pcs[0].Pawn is None


def second_gamepad_connected() -> bool:
    """
    A connected gamepad mapped to a platform user other than the primary one (pad 1 shares device 0 with KBM).

    The game only fills in a device's hardware type once the device has sent input, so a pad that hasn't been touched
    since launch reads as Unspecified — accepted too.
    """
    lib = _statics("InputDeviceLibrary")
    subsystem = next((o for o in unrealsdk.find_all("InputDeviceSubsystem", False) if not _is_cdo(o)), None)
    if subsystem is None:
        return False
    primary = lib.GetPrimaryPlatformUser().InternalId
    result = lib.GetAllConnectedInputDevices([])
    devices = result[-1] if isinstance(result, tuple) else result
    for device in devices:
        hardware = subsystem.GetInputDeviceHardwareIdentifier(device)
        kind = getattr(hardware.PrimaryDeviceType, "name", str(hardware.PrimaryDeviceType))
        if kind in PAD_TYPES and lib.GetUserForInputDevice(device).InternalId != primary:
            return True
    return False


def add_p2() -> bool:
    pcs = controllers()
    if not pcs or any(lp.ControllerId == P2_CONTROLLER_ID for lp in local_players()):
        return False
    _statics("GameplayStatics").CreatePlayer(pcs[0], P2_CONTROLLER_ID, True)
    added = len(local_players()) >= 2
    logging.info(f"{LOG_PREFIX} Player 2 {'added' if added else 'could not be added'}")
    return added


def remove_p2() -> bool:
    extras = [lp.PlayerController for lp in local_players()[1:] if lp.PlayerController is not None]
    for pc in extras:
        _statics("GameplayStatics").RemovePlayer(pc, True)  # takes the PlayerController, not the LocalPlayer
    if extras:
        logging.info(f"{LOG_PREFIX} Player 2 removed")
    return bool(extras)


def keep_mouse_look(index: int) -> bool:
    """
    Re-applies game-only input mode for this player (permanent mouse capture on the shared viewport). Skipped while
    the player has its own mouse cursor on, i.e. its own menu is open. True if applied.
    """
    pcs = controllers()
    if index >= len(pcs) or pcs[index].Pawn is None or pcs[index].bShowMouseCursor:
        return False
    _statics("WidgetBlueprintLibrary").SetInputMode_GameOnly(pcs[index], False)
    return True


def nudge_mouse(direction: int) -> None:
    """Moves the OS mouse a few pixels (relative); a real mouse event, routed to whoever owns the mouse."""
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, direction * MOUSE_NUDGE_PIXELS, 0, 0, 0)


def pointer_position() -> tuple[int, int]:
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def set_pointer_position(x: int, y: int) -> None:
    ctypes.windll.user32.SetCursorPos(x, y)


def p2_half_centre() -> tuple[int, int]:
    """Screen position of the centre of P2's half of the game window (bottom half, or right half if split vertically)."""
    user32 = ctypes.windll.user32
    window = user32.GetForegroundWindow()
    client = wintypes.RECT()
    user32.GetClientRect(window, ctypes.byref(client))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(window, ctypes.byref(origin))
    settings = next((o for o in unrealsdk.find_all("OakUIGameUserSettings", False) if not _is_cdo(o)), None)
    layout = getattr(settings.SplitscreenLayout, "name", "") if settings is not None else ""
    if layout == "vertical":
        return origin.x + client.right * 3 // 4, origin.y + client.bottom // 2
    return origin.x + client.right // 2, origin.y + client.bottom * 3 // 4


def frame_count() -> int:
    return _statics("KismetSystemLibrary").GetFrameCount()


def platform_users() -> tuple[int, ...]:
    return tuple(pc.GetPlatformUserId().InternalId for pc in controllers()[:2])


def set_platform_users(p1_user: int, p2_user: int) -> None:
    gs = _statics("GameplayStatics")
    pcs = controllers()
    for pc, user in ((pcs[0], p1_user), (pcs[1], p2_user)):
        gs.SetPlayerPlatformUserId(pc, unrealsdk.make_struct("PlatformUserId", InternalId=user))
