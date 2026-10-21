"""Unified local entry point for the public query and batch commands."""

import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "batch":
        from src.engine.batch_cli import main as batch_main

        return batch_main(args[1:])
    if args and args[0] == "query":
        args.pop(0)
    from src.engine.query_cli import main as query_main

    return query_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
