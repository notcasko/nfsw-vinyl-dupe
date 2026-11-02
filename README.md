# Need for Speed: World — Vinyl Duplication Mod

## How to Install

### Full Mode (Recommended for Offline / Local / Unrestricted Servers)
1. Place **`VinylDuplicate.asi`** into your game's `scripts/` folder.
2. Place the patched **`VinylShop.gfx`** into your game's `GFX/` folder (or run `python patch.py` in your game folder).

### ASI-Only Mode (For Servers Overwriting `.gfx`)
1. Place **`VinylDuplicate.asi`** into your game's `scripts/` folder.

---

## How to Use

1. Enter **Safehouse** -> **Customize Car** -> **Vinyl Shop**.
2. Select any vinyl layer on the car.
3. Press **`D`** on your keyboard:
   - **With Patched GFX**: The layer clones instantly with identical transforms, the counter increments, the new layer is added to the palette, and you can immediately drag, scale, or recolor it.
   - **With ASI-Only**: The vinyl clones visibly on the car with identical transforms. Click **Save**, exit the Vinyl Shop, and re-enter to adjust the new copy independently.
   
---

### How to Patch `VinylShop.gfx` Using the Python Script

1. Download [JPEXS Free Flash Decompiler](https://github.com/jindrapetrik/jpexs-decompiler)
2. **Prepare the files in a single folder**:
   - Copy the stock **`VinylShop.gfx`** from your game's `GFX/` folder into your working folder.
   - Place **`patch.py`** and the **`FFDec/`** folder alongside it.
3. **Run the script**:
   ```bash
   python patch.py
   ```
   *(The script renames the old GFX to _old.gfx and keeps the original name for the new GFX.).*
4. **Deploy the upgraded file**:
   - Copy the upgraded **`VinylShop.gfx`** back into your game's `GFX/` folder (overwrite when prompted).
---

## What Everything Does

- **`VinylDuplicate.asi` (Native C++ Plugin)**:
  Hooks `nfsw.exe`. Registers the native `VinylShopDuplicateVinyl` engine command, clones the active 52-byte vinyl struct (transforms, UV projection, color zones, and mirror bitflags) in car memory, and refreshes the 3D render pipeline. Also provides a native message hook (`PeekMessageW`) as a fallback hotkey listener when running without a patched GFX.
- **`VinylShop.gfx` (Scaleform UI Asset)**:
  Patched Flash interface. Listens for the `D` key in ActionScript, dispatches `VinylShopDuplicateVinyl` to the ASI, and immediately calls `RefreshCurrentLayers()` so the UI counter (`6/31`) and layer palette update instantly without saving.
- **`patch.py`**:
  A standalone Python utility using the bundled FFDec decompiler. Decompiles stock `VinylShop.gfx`, patches the 3 ActionScript files (`Command.as`, `VinylShopKeyboard.as`, `VinylLayerManager.as`), and recompiles a clean, modded `.gfx` without touching any unrelated assets.
- **`build.bat`**:
  One-click MSVC compiler script that builds `VinylDuplicate.asi`.

---

## Why It Cannot Be Built With Just `.gfx` (Without `.asi`)

1. **Spatial Transforms Are Completely Opaque to Flash**:
   The `com.ea.gameapi.data.VinylShopVinyl` class only exposes metadata (`id`, `bMirrored`, `name`, `cashCost`). The 16-byte transform block (X/Y position, scale X/Y, rotation, and skew) lives strictly in native C++ memory. There are no `GetTransform` or `SetTransform` functions in the game's API.
2. **The GFX-Only Ceiling**:
   Using only built-in `.gfx` commands, the most an ActionScript script could do is call `VinylShopAddVinyl()`, copy the mirror flag (`VinylShopToggleMirrorVinyl`), and copy the 4 HSV color zones (`VinylShopSetVinylPaint`). Because transforms cannot be read or set from Flash, the duplicated vinyl would always reset to default spawn parameters: centered at `(0, 0)`, `scale = 1.0`, `rotation = 0°`, and `skew = 0°`.
3. **No Native Duplication Routine**:
   The vanilla game engine only knows how to create default vinyls from scratch or delete them. Native C++ (`.asi`) is strictly required to clone the active 52-byte memory record and update the DirectX render pipeline.

---

## Server `.gfx` Overwrites & ASI-Only Fallback

> [!WARNING]
> Certain online servers automatically re-download stock `.gfx` files or load UI files directly from server cache folders (e.g. `MODS/<hash>/GFX/`). On those servers, your local `VinylShop.gfx` will be ignored or overwritten.

When that happens, you are restricted to **ASI-Only Mode**:

| Feature | Full Setup (`.asi` + patched `.gfx`) | ASI-Only Fallback (Server Overwrites `.gfx`) |
| :--- | :--- | :--- |
| **Duplication Hotkey** | `D` (Handled via Scaleform UI) | `D` (Handled via native window message hook) |
| **In-Shop UI Counter** | Updates immediately (`6/31` -> `7/31`) | Does **not** update during current shop session |
| **Layer Movement** | Immediate independent movement | **"Glued"** to original layer until saved |
| **Independent Editing** | Immediately upon duplication | **After saving and re-entering the Vinyl Shop** |

### Why Layers Are "Glued" in ASI-Only Mode
Flash maintains its own copy of the layer stack. If Flash is not patched to reload that stack, mouse manipulation inputs in 3D space are sent only to the original layer index Flash knows about. The duplicated layers share those transforms until you save your car and re-enter the shop, forcing Flash to reload the car state from the server/engine.
