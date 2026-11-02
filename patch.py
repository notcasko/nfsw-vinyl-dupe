#!/usr/bin/env python3

import sys
import os
import shutil
import subprocess
import tempfile
import re


def find_ffdec(base_dir):
    """Locate the FFDec CLI executable or jar."""
    candidates = [
        # In FFDec subfolder
        os.path.join(base_dir, "FFDec", "ffdec-cli.exe"),
        os.path.join(base_dir, "FFDec", "ffdec.bat"),
        os.path.join(base_dir, "FFDec", "ffdec.jar"),
        # In current folder
        os.path.join(base_dir, "ffdec-cli.exe"),
        os.path.join(base_dir, "ffdec.bat"),
        os.path.join(base_dir, "ffdec.jar"),
    ]

    for c in candidates:
        if os.path.isfile(c):
            if c.endswith(".jar"):
                # verify java is available
                if shutil.which("java"):
                    return ["java", "-jar", os.path.abspath(c)]
            else:
                return [os.path.abspath(c)]

    # Check PATH for ffdec-cli or ffdec
    for cmd in ["ffdec-cli", "ffdec"]:
        path = shutil.which(cmd)
        if path:
            return [path]

    return None


def patch_actionscript(scripts_root):
    """
    Applies the exact vinyl duplication modifications to the 3 relevant ActionScript 2 files.
    Returns a list of relative paths that were modified.
    """
    modified_files = []

    # -------------------------------------------------------------------------
    # 1. Command.as
    # -------------------------------------------------------------------------
    cmd_rel = os.path.join("__Packages", "com", "ea", "gameapi", "command", "Command.as")
    cmd_path = os.path.join(scripts_root, cmd_rel)
    if not os.path.isfile(cmd_path):
        raise FileNotFoundError(f"Missing expected script: {cmd_rel}")

    with open(cmd_path, "r", encoding="utf-8", errors="replace") as f:
        cmd_content = f.read()

    if "VinylShopDuplicateVinyl" in cmd_content:
        print("  [*] Command.as already contains VinylShopDuplicateVinyl.")
    else:
        target_anchor = "   static function VinylShopGetCurrentLayers()"
        if target_anchor not in cmd_content:
            # Fallback to regex with flexible whitespace
            m = re.search(r"(\n\s*static\s+function\s+VinylShopGetCurrentLayers\s*\(\s*\))", cmd_content)
            if not m:
                raise ValueError("Could not find VinylShopGetCurrentLayers() in Command.as")
            target_anchor = m.group(1)
            replacement = (
                "\n   static function VinylShopDuplicateVinyl(layerIndex)\n"
                "   {\n"
                '      flash.external.ExternalInterface.call("Request","VinylShopDuplicateVinyl",layerIndex);\n'
                "   }" + target_anchor
            )
            cmd_content = cmd_content[:m.start()] + replacement + cmd_content[m.end():]
        else:
            replacement = (
                "   static function VinylShopDuplicateVinyl(layerIndex)\n"
                "   {\n"
                '      flash.external.ExternalInterface.call("Request","VinylShopDuplicateVinyl",layerIndex);\n'
                "   }\n"
                "   static function VinylShopGetCurrentLayers()"
            )
            cmd_content = cmd_content.replace(target_anchor, replacement, 1)

        with open(cmd_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(cmd_content)
        modified_files.append(cmd_rel)
        print("  [+] Patched Command.as: added VinylShopDuplicateVinyl()")

    # -------------------------------------------------------------------------
    # 2. VinylShopKeyboard.as
    # -------------------------------------------------------------------------
    kbd_rel = os.path.join("__Packages", "com", "ea", "SafeHouse", "VinylShop_Util", "VinylShopKeyboard.as")
    kbd_path = os.path.join(scripts_root, kbd_rel)
    if not os.path.isfile(kbd_path):
        raise FileNotFoundError(f"Missing expected script: {kbd_rel}")

    with open(kbd_path, "r", encoding="utf-8", errors="replace") as f:
        kbd_content = f.read()

    if "KEY_DUPLICATE" in kbd_content:
        print("  [*] VinylShopKeyboard.as already contains KEY_DUPLICATE.")
    else:
        # Add KEY_DUPLICATE constant
        mirror_const = 'static var KEY_MIRROR = "M";'
        if mirror_const not in kbd_content:
            m = re.search(r"(static\s+var\s+KEY_MIRROR\s*=\s*\"M\";)", kbd_content)
            if not m:
                raise ValueError("Could not find KEY_MIRROR constant in VinylShopKeyboard.as")
            kbd_content = kbd_content[:m.end()] + '\n   static var KEY_DUPLICATE = "D";' + kbd_content[m.end():]
        else:
            kbd_content = kbd_content.replace(
                mirror_const,
                mirror_const + '\n   static var KEY_DUPLICATE = "D";',
                1
            )

        # Add key handler branch in onKeyDown()
        pattern = (
            r"(else\s+if\s*\(\s*com\.ea\.SafeHouse\.VinylShop_Util\.VinylShopKeyboard\.KEY_MIRROR\s*==\s*(\w+)\s*\)\s*\{"
            r"\s*this\.mLayerManager\.MirrorCurrent\(\);\s*\})"
        )
        m = re.search(pattern, kbd_content)
        if not m:
            raise ValueError("Could not find KEY_MIRROR handler in VinylShopKeyboard.as")

        key_var = m.group(2)
        kbd_branch = (
            f"{m.group(1)}\n"
            f"      else if(com.ea.SafeHouse.VinylShop_Util.VinylShopKeyboard.KEY_DUPLICATE == {key_var})\n"
            f"      {{\n"
            f"         this.mLayerManager.DuplicateCurrent();\n"
            f"      }}"
        )
        kbd_content = kbd_content[:m.start()] + kbd_branch + kbd_content[m.end():]

        with open(kbd_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(kbd_content)
        modified_files.append(kbd_rel)
        print("  [+] Patched VinylShopKeyboard.as: added KEY_DUPLICATE ('D') handler")

    # -------------------------------------------------------------------------
    # 3. VinylLayerManager.as
    # -------------------------------------------------------------------------
    vlm_rel = os.path.join("__Packages", "com", "ea", "SafeHouse", "VinylShop_Util", "VinylLayerManager.as")
    vlm_path = os.path.join(scripts_root, vlm_rel)
    if not os.path.isfile(vlm_path):
        raise FileNotFoundError(f"Missing expected script: {vlm_rel}")

    with open(vlm_path, "r", encoding="utf-8", errors="replace") as f:
        vlm_content = f.read()

    if "DuplicateCurrent" in vlm_content:
        print("  [*] VinylLayerManager.as already contains DuplicateCurrent().")
    else:
        dupe_method = (
            "   function DuplicateCurrent()\n"
            "   {\n"
            "      if(this.m_LayersPalette.GetList().length == 0)\n"
            "      {\n"
            "         return undefined;\n"
            "      }\n"
            '      flash.external.ExternalInterface.call("Request","VinylShopGetMaxVinyls");\n'
            "      var _loc3_ = _global.mVinylShopMaxVinyls.maxVinyls;\n"
            "      if(this.GetVinylCount() >= _loc3_)\n"
            "      {\n"
            "         return undefined;\n"
            "      }\n"
            "      var _loc4_ = this.GetSelectedLayerIndex();\n"
            "      if(_loc4_ < 0)\n"
            "      {\n"
            "         return undefined;\n"
            "      }\n"
            "      com.ea.gameapi.command.Command.VinylShopDuplicateVinyl(_loc4_);\n"
            "      this.RefreshCurrentLayers();\n"
            "      this.m_LayersPalette.SetSelected(0);\n"
            "   }\n"
        )

        anchor = "function ShowNoActionCursorCheck()"
        m = re.search(r"(\n\s*function\s+ShowNoActionCursorCheck\s*\(\s*\))", vlm_content)
        if not m:
            raise ValueError("Could not find ShowNoActionCursorCheck() anchor in VinylLayerManager.as")

        vlm_content = vlm_content[:m.start()] + "\n" + dupe_method + vlm_content[m.start():]

        with open(vlm_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(vlm_content)
        modified_files.append(vlm_rel)
        print("  [+] Patched VinylLayerManager.as: added DuplicateCurrent()")

    return modified_files


def update_gfx(input_gfx, output_gfx, ffdec_cmd):
    """
    Decompiles input_gfx using FFDec, patches the scripts, and compiles
    into output_gfx while keeping all other assets/tags untouched.
    """
    input_gfx = os.path.abspath(input_gfx)
    output_gfx = os.path.abspath(output_gfx)

    if not os.path.isfile(input_gfx):
        raise FileNotFoundError(f"Input GFX file not found: {input_gfx}")

    temp_dir = tempfile.mkdtemp(prefix="ffdec_vinyl_")
    try:
        export_dir = os.path.join(temp_dir, "export")
        os.makedirs(export_dir, exist_ok=True)

        print(f"[*] Decompiling ActionScript from {os.path.basename(input_gfx)} using FFDec...")
        cmd_export = ffdec_cmd + ["-export", "script", export_dir, input_gfx]
        res = subprocess.run(cmd_export, capture_output=True, text=True)
        if res.returncode != 0:
            print("FFDec export error output:\n", res.stderr)
            raise RuntimeError(f"FFDec failed to export scripts (exit code {res.returncode})")

        scripts_dir = os.path.join(export_dir, "scripts")
        if not os.path.isdir(scripts_dir):
            raise RuntimeError("Scripts directory not found after FFDec export.")

        print("[*] Applying Vinyl Duplication ActionScript patches...")
        modified_files = patch_actionscript(scripts_dir)

        if not modified_files:
            print("[*] All scripts already contain the updates. Nothing to patch.")
            if input_gfx != output_gfx:
                shutil.copy2(input_gfx, output_gfx)
            return

        # Prepare clean import folder with ONLY modified files
        import_dir = os.path.join(temp_dir, "import", "scripts")
        for rel in modified_files:
            src = os.path.join(scripts_dir, rel)
            dst = os.path.join(import_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        temp_out = os.path.join(temp_dir, "recompiled.gfx")
        print("[*] Recompiling updated ActionScript into GFX using FFDec...")
        cmd_import = ffdec_cmd + ["-importScript", input_gfx, temp_out, import_dir]
        res = subprocess.run(cmd_import, capture_output=True, text=True)
        if res.returncode != 0:
            print("FFDec import error output:\n", res.stderr)
            raise RuntimeError(f"FFDec failed to import scripts (exit code {res.returncode})")

        if not os.path.isfile(temp_out) or os.path.getsize(temp_out) == 0:
            raise RuntimeError("FFDec did not generate output file or file is empty.")

        # Rename the existing file so it is preserved (e.g., VinylShop_old.gfx)
        if os.path.exists(output_gfx):
            base, ext = os.path.splitext(output_gfx)
            old_file = f"{base}_old{ext}"
            counter = 1
            while os.path.exists(old_file):
                old_file = f"{base}_old_{counter}{ext}"
                counter += 1

            shutil.move(output_gfx, old_file)
            print(f"[*] Preserved old file as: {os.path.basename(old_file)}")

        # Write the new file to the desired output name
        os.makedirs(os.path.dirname(output_gfx), exist_ok=True)
        shutil.copy2(temp_out, output_gfx)
        print(f"[+] Successfully wrote new GFX to: {output_gfx} ({os.path.getsize(output_gfx):,} bytes)")

    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    base_dir = os.getcwd()

    input_gfx = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base_dir, "VinylShop.gfx")
    output_gfx = sys.argv[2] if len(sys.argv) > 2 else input_gfx

    ffdec_cmd = find_ffdec(base_dir)
    if not ffdec_cmd:
        print("[!] Error: Could not find FFDec executable or jar.")
        print("    Ensure the 'FFDec' folder is located in the same directory as this script.")
        sys.exit(1)

    print(f"FFDec found: {' '.join(ffdec_cmd)}")

    try:
        update_gfx(input_gfx, output_gfx, ffdec_cmd)
        print("\nThe updated VinylShop.gfx is ready for use.")
    except Exception as e:
        print(f"\n[!] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()