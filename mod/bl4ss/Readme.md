# BL4 2-Player Split-Screen Unlocked

Two-player local split-screen for Borderlands 4 on PC, as an [Oak2 SDK](https://bl-sdk.github.io/oak2-mod-db/) mod.

## Requirements

- Steam build **25234898** is the tested version. On other builds the mod locates what it needs by signature and
  refuses (with a log message) if it can't do so safely.
- Oak2 Mod Manager (SDK) installed.
- **Two controllers connected before launching the game.** Player 1 can use keyboard/mouse or the first controller;
  Player 2 uses the second controller.

## Install

Copy `bl4ss.sdkmod` into the game's `sdk_mods` folder, launch, and make sure the mod is enabled (console: `mods`).

## Playing

1. On the main menu, Player 2 is added automatically when a second controller is connected
   (turn this off with the **Auto-join Player 2** option). To add or remove Player 2 by hand on the main menu, use
   **F7**, the console command `bl4ss_p2`, or the button on the mod's page in the `mods` menu.
2. Player 2 comes in with its most recently played character. To pick a different one, Player 2 presses **A** →
   **Swap Player** to bring up its own menu, then **Load Vault Hunter**.
3. Player 1 presses **Continue**. Both players arrive in the world in split-screen.
4. To end split-screen, quit to the main menu and remove Player 2 (`bl4ss_p2` / the `mods` button). A Player 2
   removed by hand isn't re-added automatically until the next launch.

**Creating a new Player 2 character.** The game's Shared Progression screen only accepts the signed-in player, so:
Player 2 picks **Create Vault Hunter** → Yes → difficulty. On the **Shared Progression** screen press **F8** (or console `bl4ss_swap`), then
choose On/Off and the class **with keyboard/mouse or the first controller** (they drive Player 2's menu while
swapped; the mouse cursor may be hidden — use the first controller). **Control returns to normal by itself as soon
as the class is picked**; then Player 2 presses **B** back to its menu. (Press **F8** again only to cancel before
picking a class.) The new character is saved once you're in the world.

**DLC Vault Hunters.** Player 2 can pick C4SH or Loveless if the account running the game owns them: DLC ownership
is per player and Player 2 has no account of its own, so the mod gives Player 2 Player 1's DLC.

Player 2's characters are saved separately, under `Saved\SaveGames\Profiles\client_0_user_1\`.

## Known issues

- Hotkeys (F7/F8) may not register while the title menu has keyboard focus. The console commands and the
  `mods` menu buttons always work.
- **Leave Split Screen** in Player 2's pause menu does nothing (see Troubleshooting).
- Player 2 spawns on top of Player 1 on arrival. Walk apart.
- The first time Player 2 opens a menu in the world, the two players' controls are swapped for a single frame (see
  "How it works"); input in that frame goes to the other player.
- A new Player 2 character starts at level 1 without an action skill and has to level up to unlock it; there is no
  "skip prologue" for Player 2.
- Don't start the Prologue with two players — you get stuck on the character selection screen. Remove Player 2 on
  the main menu first, finish the Prologue, then add Player 2 back.
- **Pink sparkles over Player 2's first-person arms on the Badass graphics preset.** A Borderlands 4 rendering
  problem in the second split-screen view, not caused by the mod (Player 1 is never affected). Use Very High or
  lower. Unrelated to DLSS, upscaling, anti-aliasing, frame generation, depth of field, reflections, the shader
  cache, drivers and the DLC.

## Troubleshooting

- **Player 2 isn't added on the main menu** even though two controllers are connected: add Player 2 by hand with
  the **Add / Remove Player 2** button on the mod's page in the `mods` console menu, or the console command
  `bl4ss_p2`. Auto-join has occasionally not fired on a launch; the manual add works.
- **A controller cursor is invisible in a menu** (the highlight still follows the stick, with a slight lag): move the
  **mouse** inside that menu once, then use the stick again — the cursor shows and stays visible. This has been seen
  on Player 1's menu. For Player 2 the mod does the equivalent automatically the first time Player 2 opens a menu; if
  Player 2's cursor is still invisible, please report it.
- **An action seems to do nothing:** open the console (`~`). The mod's messages start with `[BL4SS]` and errors are
  shown there (they may not appear in `unrealsdk.log`). Please include those lines when reporting a problem.
- **"DLL load failed while importing keybinds"** in the console at startup: this comes from the SDK itself, before
  any mod loads; relaunching the game has fixed it.
- **Leave Split Screen does nothing:** quit to the main menu and remove Player 2 with `bl4ss_p2` or the `mods` button.

## How it works

- **Player 2** is created with the game's own `GameplayStatics.CreatePlayer`.
- **Shared Progression** only accepts the signed-in platform user, so F8 swaps the two players' platform users
  (and with them, which input devices drive which player) until the class pick moves Player 2 to its menu station, or
  F8 is pressed again. Swapping only for the instant of Player 2's click was tried and crashed the game.
- **Arrival**: a local split-screen player has no online ID, so the game never marks it "client ready" and its
  arrival waits forever. The mod calls the game's ready setter for Player 2 when it travels. The setter is found by a
  code signature (cross-checked against a second function that reads the same flag); on build 25234898 only, a known
  address is used as a fallback if the signature ever fails — and only after verifying the bytes there.
- **Mouse look**: opening Player 2's menu puts the shared game window into menu input mode, where a mouse click
  releases the mouse and Player 1 loses mouse look. The mod switches Player 1 back to game input whenever Player 2
  opens a menu (unless Player 1's own menu is open); Player 2's menu keeps working with its controller.
- **Player 2's menu cursor**: Player 2's controller cursor stays invisible until Player 2's menu has seen real mouse
  movement from the player that owns the mouse. On Player 2's first menu, the mod gives Player 2 the mouse for one
  frame, moves it a few pixels there and back, and gives it back. If Player 1's own menu is open at that moment, the
  mouse pointer is also placed over Player 2's half for that frame (a barely visible flicker).
- **Menu blur**: a full-screen menu lowers the global render scale to 10%, which would blur the other player's half;
  the mod re-issues the current render scale once at console priority, which the menu can't override. The in-game
  Upscaling Quality option still works.
