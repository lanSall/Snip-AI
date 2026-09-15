/* Windows double-click launcher for snip-ai.
 *
 * Finds this .exe's folder, then runs scripts\ensure_and_run.py with Python.
 * After the venv exists, it starts hidden (no console). The first install
 * opens a console so pip progress is visible.
 *
 * Build (from the repo root, Linux or Windows with MinGW):
 *   ./scripts/build-windows-exe.sh
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#include <string.h>

static void dir_of_exe(WCHAR *out, DWORD n) {
    DWORD len = GetModuleFileNameW(NULL, out, n);
    if (len == 0 || len >= n) {
        out[0] = 0;
        return;
    }
    WCHAR *slash = wcsrchr(out, L'\\');
    if (slash) {
        *slash = 0;
    }
}

static int file_exists(const WCHAR *path) {
    DWORD attr = GetFileAttributesW(path);
    return attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY);
}

static int join(WCHAR *out, DWORD n, const WCHAR *a, const WCHAR *b) {
    if (_snwprintf(out, n, L"%s\\%s", a, b) < 0) {
        return 0;
    }
    out[n - 1] = 0;
    return 1;
}

static int spawn(const WCHAR *cwd, const WCHAR *cmdline, BOOL hidden, BOOL wait) {
    WCHAR cmd[4096];
    wcsncpy(cmd, cmdline, 4095);
    cmd[4095] = 0;

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));
    si.cb = sizeof(si);
    if (hidden) {
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;
    }

    DWORD flags = hidden ? CREATE_NO_WINDOW : CREATE_NEW_CONSOLE;
    if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, flags, NULL, cwd, &si, &pi)) {
        return 0;
    }
    DWORD code = 0;
    if (wait) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        GetExitCodeProcess(pi.hProcess, &code);
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return code == 0 ? 1 : 0;
}

static int find_on_path(const WCHAR *name, WCHAR *out, DWORD n) {
    DWORD got = SearchPathW(NULL, name, NULL, n, out, NULL);
    return got > 0 && got < n;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, LPWSTR cmd_line, int show) {
    (void)inst;
    (void)prev;
    (void)cmd_line;
    (void)show;

    WCHAR root[MAX_PATH];
    dir_of_exe(root, MAX_PATH);
    if (!root[0]) {
        MessageBoxW(NULL, L"Could not find the snip-ai folder.", L"snip-ai", MB_OK | MB_ICONERROR);
        return 1;
    }
    SetCurrentDirectoryW(root);

    WCHAR script[MAX_PATH];
    if (!join(script, MAX_PATH, root, L"scripts\\ensure_and_run.py") || !file_exists(script)) {
        MessageBoxW(
            NULL,
            L"Keep snip-ai.exe in the Snip-AI folder (next to Start.bat and the scripts folder).",
            L"snip-ai",
            MB_OK | MB_ICONERROR
        );
        return 1;
    }

    WCHAR cmdline[4096];
    WCHAR pythonw[MAX_PATH];
    if (join(pythonw, MAX_PATH, root, L".venv\\Scripts\\pythonw.exe") && file_exists(pythonw)) {
        _snwprintf(cmdline, 4096, L"\"%s\" \"%s\"", pythonw, script);
        cmdline[4095] = 0;
        if (spawn(root, cmdline, TRUE, TRUE)) {
            return 0;
        }
    }

    WCHAR py[MAX_PATH];
    if (find_on_path(L"py.exe", py, MAX_PATH)) {
        _snwprintf(cmdline, 4096, L"\"%s\" -3 \"%s\"", py, script);
        cmdline[4095] = 0;
        if (spawn(root, cmdline, FALSE, TRUE)) {
            return 0;
        }
    }
    if (find_on_path(L"python.exe", py, MAX_PATH)) {
        _snwprintf(cmdline, 4096, L"\"%s\" \"%s\"", py, script);
        cmdline[4095] = 0;
        if (spawn(root, cmdline, FALSE, TRUE)) {
            return 0;
        }
    }

    MessageBoxW(
        NULL,
        L"snip-ai needs Python 3.10 or newer.\n\n"
        L"1. Install Python from python.org\n"
        L"2. CHECK the box \"Add python.exe to PATH\"\n"
        L"3. Double-click snip-ai.exe again.",
        L"snip-ai",
        MB_OK | MB_ICONINFORMATION
    );
    ShellExecuteW(NULL, L"open", L"https://www.python.org/downloads/", NULL, NULL, SW_SHOWNORMAL);
    return 1;
}
