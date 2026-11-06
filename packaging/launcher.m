/* CPython's isolated configuration prevents environment and user-site imports.
 * The executable is signed with App Sandbox before any Python code executes.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#import <AppKit/AppKit.h>

static void checked(PyStatus status, PyConfig *config) {
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(config);
        Py_ExitStatusException(status);
    }
}

static void add_path(PyConfig *config, const char *path) {
    wchar_t *wide = Py_DecodeLocale(path, NULL);
    if (!wide) { fprintf(stderr, "Unable to decode runtime path\n"); exit(1); }
    PyStatus status = PyWideStringList_Append(&config->module_search_paths, wide);
    PyMem_RawFree(wide);
    checked(status, config);
}

static void make_path(char *result, size_t size, const char *root, const char *suffix) {
    if (snprintf(result, size, "%s/%s", root, suffix) >= (int)size) {
        fprintf(stderr, "Application path is too long\n"); exit(1);
    }
}

static int run_python(int argc, char **argv, int diagnostics) {
    char executable[PATH_MAX], resolved[PATH_MAX], contents[PATH_MAX], path[PATH_MAX];
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size) || !realpath(executable, resolved)) {
        perror("Unable to locate application"); return 1;
    }
    strcpy(contents, resolved);
    for (int i = 0; i < 2; ++i) {
        char *slash = strrchr(contents, '/');
        if (!slash) { fprintf(stderr, "Invalid application path\n"); return 1; }
        *slash = '\0';
    }

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.site_import = 0;
    config.write_bytecode = 0;
    config.parse_argv = 0;
    config.module_search_paths_set = 1;
    checked(PyConfig_SetBytesString(&config, &config.program_name, resolved), &config);
    checked(PyConfig_SetBytesArgv(&config, argc, argv), &config);
    make_path(path, sizeof(path), contents, "Frameworks/Python.framework/Versions/3.12");
    checked(PyConfig_SetBytesString(&config, &config.home, path), &config);
    make_path(path, sizeof(path), contents, "Frameworks/Python.framework/Versions/3.12/lib/python3.12");
    add_path(&config, path);
    make_path(path, sizeof(path), contents, "Frameworks/Python.framework/Versions/3.12/lib/python3.12/lib-dynload");
    add_path(&config, path);
    make_path(path, sizeof(path), contents, "Resources/python");
    add_path(&config, path);
    checked(PyConfig_SetString(&config, &config.run_module, L"pagemark_app"), &config);
    if (diagnostics) {
        fprintf(stderr, "launcher: initializing isolated Python\n");
        fflush(stderr);
    }
    checked(Py_InitializeFromConfig(&config), &config);
    PyConfig_Clear(&config);
    return Py_RunMain();
}

int main(int argc, char **argv) {
    int diagnostics = 0, runtime_only = 0;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--probe") == 0 ||
            strcmp(argv[i], "--probe-editor") == 0 ||
            strcmp(argv[i], "--probe-runtime") == 0) {
            diagnostics = 1;
        }
        if (strcmp(argv[i], "--probe-runtime") == 0) {
            runtime_only = 1;
        }
    }
    @autoreleasepool {
        /* App Sandbox is already active when main is entered. Load AppKit as
         * a native dependency and establish the application before starting
         * the embedded interpreter, just as a native Cocoa host would. */
        if (!runtime_only) {
            if (diagnostics) {
                fprintf(stderr, "launcher: initializing native AppKit application\n");
                fflush(stderr);
            }
            [NSApplication sharedApplication];
            if (diagnostics) {
                fprintf(stderr, "launcher: native AppKit application ready\n");
                fflush(stderr);
            }
        }
    }
    /* Py_RunMain finalizes Python. A native pool surrounding it would release
     * Python-backed Cocoa objects after their interpreter has gone away.
     * The Python entry point owns the pool for all bridged application work. */
    return run_python(argc, argv, diagnostics);
}

