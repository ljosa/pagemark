from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--probe", action="store_true", help="Run all noninteractive bundle checks")
    modes.add_argument("--probe-runtime", action="store_true", help="Check runtime and sandbox without a window")
    modes.add_argument("--probe-editor", action="store_true", help="Check the native editor in a hidden window")
    parser.add_argument("--denied-file", help="A disposable fixture outside the app sandbox")
    args = parser.parse_args()
    if args.probe or args.probe_runtime or args.probe_editor:
        import faulthandler
        faulthandler.enable()
    import objc
    # Drain Cocoa objects while their Python callbacks can still run, including
    # when a probe exits or raises. Py_RunMain finalizes Python after we return.
    with objc.autorelease_pool():
        if args.probe_editor:
            from .probe import run_editor
            raise SystemExit(run_editor())
        if args.probe or args.probe_runtime:
            from .probe import run
            raise SystemExit(run(args.denied_file, include_editor=args.probe))
        from .application import run
        run()


if __name__ == "__main__":
    main()

