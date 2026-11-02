#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

typedef BOOL (WINAPI *PeekMessageW_t)(LPMSG lpMsg, HWND hWnd, UINT wMsgFilterMin, UINT wMsgFilterMax, UINT wRemoveMsg);
static PeekMessageW_t s_origPeekMessageW = NULL;
static DWORD s_lastGlobalDupTick = 0;

static void PerformDuplicate(int sourceLayer = -1)
{
    uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
    if (!base) return;
    uintptr_t delta = base - 0x00400000;

    // Check if player is currently in Vinyl Shop
    uintptr_t* pUIHelperPtr = (uintptr_t*)(0x00CE3328 + delta);
    if (IsBadReadPtr(pUIHelperPtr, sizeof(uintptr_t)) || !*pUIHelperPtr)
    {
        return;
    }
    uintptr_t pUIHelper = *pUIHelperPtr;

    // Check vehicle vinyl interface
    uintptr_t* pVinylPtr = (uintptr_t*)(0x00D10D40 + delta);
    if (IsBadReadPtr(pVinylPtr, sizeof(uintptr_t)) || !*pVinylPtr)
    {
        return;
    }
    uintptr_t pVinyl = *pVinylPtr;

    uintptr_t real_buf = *(uintptr_t*)(pVinyl + 4);
    if (!real_buf || IsBadReadPtr((void*)real_buf, 0x1200))
    {
        return;
    }

    uint8_t total_layers = *(uint8_t*)(real_buf + 0x11C4);
    // NFSW engine supports maximum 31 vinyl layers per vehicle
    if (total_layers == 0 || total_layers >= 31)
    {
        return;
    }

    // If sourceLayer not explicitly specified, read active layer from UI Helper
    if (sourceLayer < 0 || sourceLayer >= (int)total_layers)
    {
        sourceLayer = *(int*)(pUIHelper + 0x38);
        if (sourceLayer < 0 || sourceLayer >= (int)total_layers)
        {
            sourceLayer = (int)total_layers - 1; // Fallback to topmost layer
        }
    }

    // Verify source layer pointer
    uintptr_t pSourceLayer = *(uintptr_t*)(pVinyl + 8 + sourceLayer * 4);
    if (!pSourceLayer || IsBadReadPtr((void*)pSourceLayer, 16))
    {
        return;
    }

    // 1. Extract Vinyl ID
    uint32_t vinylId = *(uint32_t*)(pSourceLayer + 8);

    // 2. Extract 52-byte record from vehicle buffer (real_buf + 0xB78 + layerIndex * 0x34)
    uint8_t* pSrcRec = (uint8_t*)(real_buf + 0xB78 + sourceLayer * 0x34);

    // Mirror bitmask
    uint32_t mirror_mask = *(uint32_t*)(real_buf + 0x11C0);
    bool bMirrored = ((mirror_mask >> sourceLayer) & 1) != 0;

    // 16-byte packed transform vector
    uint64_t tf_part1 = *(uint64_t*)(pSrcRec + 0x20);
    uint64_t tf_part2 = *(uint64_t*)(pSrcRec + 0x28);

    // 32-byte color zones
    uint8_t zone_data[32];
    memcpy(zone_data, pSrcRec, 32);

    // 3. Add layer action via Call_AddVinylAction (0x0045B070)
    uint32_t newLayer = (uint32_t)total_layers;
    uint32_t addArgs[2] = { vinylId, newLayer };

    typedef void (__cdecl *Call_AddVinylAction_t)(uint32_t* args, void* pContext);
    Call_AddVinylAction_t Call_AddVinylAction = (Call_AddVinylAction_t)(0x0045B070 + delta);
    Call_AddVinylAction(addArgs, NULL);

    // 4. Set 16-byte packed transform (0x0070C070)
    typedef void (__thiscall *Vinyl_SetTransform_t)(uintptr_t pBuf, uint8_t layerIdx, uint64_t p1, uint64_t p2);
    Vinyl_SetTransform_t Vinyl_SetTransform = (Vinyl_SetTransform_t)(0x0070C070 + delta);
    Vinyl_SetTransform(real_buf, (uint8_t)newLayer, tf_part1, tf_part2);

    // 5. Copy all 32 bytes of color zones to the new layer record
    uint8_t* pDstRec = (uint8_t*)(real_buf + 0xB78 + newLayer * 0x34);
    memcpy(pDstRec, zone_data, 32);

    // 6. Set mirror state if the source layer was mirrored (0x0070C0B0)
    if (bMirrored)
    {
        typedef void (__thiscall *Vinyl_SetMirror_t)(uintptr_t pBuf, uint8_t layerIdx, uint8_t bMirror);
        Vinyl_SetMirror_t Vinyl_SetMirror = (Vinyl_SetMirror_t)(0x0070C0B0 + delta);
        Vinyl_SetMirror(real_buf, (uint8_t)newLayer, 1);
    }

    // 7. Update 3D vehicle rendering / ride info (0x00678BC0)
    typedef void (__thiscall *Vinyl_UpdateRideInfo_t)(uintptr_t pVinyl);
    Vinyl_UpdateRideInfo_t Vinyl_UpdateRideInfo = (Vinyl_UpdateRideInfo_t)(0x00678BC0 + delta);
    Vinyl_UpdateRideInfo(pVinyl);

    // 8. Update UI layer selection
    typedef void (__cdecl *Call_SetActiveLayer_t)(uint32_t* layerIdx, void* pContext);
    Call_SetActiveLayer_t Call_SetActiveLayer = (Call_SetActiveLayer_t)(0x0045B020 + delta);
    Call_SetActiveLayer(&newLayer, NULL);
}

// Flash command handler
static void __cdecl VinylShopDuplicateVinyl_Handler(void* pContext, void* pArgs, int argc)
{
    DWORD now = GetTickCount();
    // Prevent execution if native hook or a prior Flash event just ran
    if (now - s_lastGlobalDupTick < 400)
    {
        return;
    }
    s_lastGlobalDupTick = now;

    int selIdx = -1;
    if (argc >= 1 && pArgs)
    {
        double val = *(double*)((char*)pArgs + 8);
        selIdx = (int)val;
    }
    PerformDuplicate(selIdx);
}

// Hooked registration call for early boot
static void __fastcall Hooked_RegisterVinylShopEndDrag(void* pCmdMgr, void* edx, const char* name, void* handler)
{
    uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
    uintptr_t delta = base - 0x00400000;

    typedef void (__thiscall *RegCmd_t)(void* this_ptr, const char* name, void* handler);
    RegCmd_t origReg = (RegCmd_t)(0x00524410 + delta);

    // 1. Register VinylShopEndDrag normally
    origReg(pCmdMgr, name, handler);

    // 2. Register VinylShopDuplicateVinyl
    static const char s_dupName[] = "VinylShopDuplicateVinyl";
    origReg(pCmdMgr, s_dupName, (void*)&VinylShopDuplicateVinyl_Handler);
}

static void CheckAndPerformDuplicate()
{
    // If ANY duplication occurred within the last 400ms, abort
    if (GetTickCount() - s_lastGlobalDupTick < 400)
    {
        return;
    }

    // Ensure the game window is currently focused
    HWND hForeground = GetForegroundWindow();
    if (!hForeground) return;

    DWORD fgPid = 0;
    GetWindowThreadProcessId(hForeground, &fgPid);
    if (fgPid != GetCurrentProcessId())
    {
        return;
    }

    // Ignore if Alt key is pressed (e.g. Alt-Tab)
    if (GetAsyncKeyState(VK_MENU) & 0x8000)
    {
        return;
    }

    static bool s_wasKeyDown = false;
    bool isKeyDown = (GetAsyncKeyState('D') & 0x8000) != 0;

    if (isKeyDown && !s_wasKeyDown)
    {
        DWORD now = GetTickCount();
        if (now - s_lastGlobalDupTick > 400)
        {
            s_lastGlobalDupTick = now;
            __try
            {
                PerformDuplicate(-1);
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
            }
        }
    }

    s_wasKeyDown = isKeyDown;
}

static BOOL WINAPI Hooked_PeekMessageW(LPMSG lpMsg, HWND hWnd, UINT wMsgFilterMin, UINT wMsgFilterMax, UINT wRemoveMsg)
{
    BOOL result = FALSE;
    if (s_origPeekMessageW)
    {
        result = s_origPeekMessageW(lpMsg, hWnd, wMsgFilterMin, wMsgFilterMax, wRemoveMsg);
    }
    else
    {
        result = PeekMessageW(lpMsg, hWnd, wMsgFilterMin, wMsgFilterMax, wRemoveMsg);
    }

    CheckAndPerformDuplicate();

    return result;
}

static void InstallHooks()
{
    uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
    if (!base) return;
    uintptr_t delta = base - 0x00400000;

    // 1. IAT Hook on USER32.dll!PeekMessageW (RVA 0x0071D7E4, VA 0x00B1D7E4)
    uintptr_t* pIAT_PeekMessageW = (uintptr_t*)(0x00B1D7E4 + delta);
    DWORD oldProtect = 0;
    if (VirtualProtect(pIAT_PeekMessageW, sizeof(uintptr_t), PAGE_EXECUTE_READWRITE, &oldProtect))
    {
        s_origPeekMessageW = (PeekMessageW_t)*pIAT_PeekMessageW;
        *pIAT_PeekMessageW = (uintptr_t)&Hooked_PeekMessageW;
        VirtualProtect(pIAT_PeekMessageW, sizeof(uintptr_t), oldProtect, &oldProtect);
    }

    // 2. Hook registration site at 0x004C6638 for early boot
    uint8_t* pCallSite = (uint8_t*)(0x004C6638 + delta);
    if (VirtualProtect(pCallSite, 5, PAGE_EXECUTE_READWRITE, &oldProtect))
    {
        uintptr_t target = (uintptr_t)&Hooked_RegisterVinylShopEndDrag;
        uint32_t rel = (uint32_t)(target - ((uintptr_t)pCallSite + 5));
        pCallSite[0] = 0xE8; // call
        *(uint32_t*)(pCallSite + 1) = rel;
        VirtualProtect(pCallSite, 5, oldProtect, &oldProtect);
    }

    // 3. Register VinylShopDuplicateVinyl directly if CommandManager already initialized
    uintptr_t* pCmdMgrPtr = (uintptr_t*)(0x00CEA7A4 + delta);
    if (pCmdMgrPtr && *pCmdMgrPtr)
    {
        typedef void (__thiscall *RegCmd_t)(void* this_ptr, const char* name, void* handler);
        RegCmd_t origReg = (RegCmd_t)(0x00524410 + delta);
        static const char s_dupName[] = "VinylShopDuplicateVinyl";
        origReg((void*)*pCmdMgrPtr, s_dupName, (void*)&VinylShopDuplicateVinyl_Handler);
    }
}

static void UninstallHooks()
{
    uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
    if (!base) return;
    uintptr_t delta = base - 0x00400000;

    if (s_origPeekMessageW)
    {
        uintptr_t* pIAT_PeekMessageW = (uintptr_t*)(0x00B1D7E4 + delta);
        DWORD oldProtect = 0;
        if (VirtualProtect(pIAT_PeekMessageW, sizeof(uintptr_t), PAGE_EXECUTE_READWRITE, &oldProtect))
        {
            *pIAT_PeekMessageW = (uintptr_t)s_origPeekMessageW;
            VirtualProtect(pIAT_PeekMessageW, sizeof(uintptr_t), oldProtect, &oldProtect);
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
    switch (fdwReason)
    {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(hinstDLL);
        InstallHooks();
        break;
    case DLL_PROCESS_DETACH:
        UninstallHooks();
        break;
    }
    return TRUE;
}
