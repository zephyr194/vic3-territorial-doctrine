#!/usr/bin/env python3
"""VTD local test installer. Run without arguments for an interactive menu."""
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import traceback


class Tee:
    """Keep console input/output interactive while recording UTF-8 diagnostics."""

    def __init__(self, console, log):
        self.console, self.log = console, log

    def write(self, value):
        self.log.write(value)
        self.log.flush()
        return self.console.write(value)

    def flush(self):
        self.log.flush()
        self.console.flush()

    def __getattr__(self, name):
        return getattr(self.console, name)


def run():
    # Bootstrap logging before importing the installer, including import failures.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='backslashreplace')
    try:
        configured = os.environ.get('VTD_LOG_FILE')
        if configured:
            path = Path(configured).expanduser()
            log = path.open('a', encoding='utf-8')
        else:
            handle, name = tempfile.mkstemp(prefix='vtd-installer-', suffix='.log')
            path = Path(name)
            log = os.fdopen(handle, 'w', encoding='utf-8')
    except OSError as exc:
        print('VTD: cannot open diagnostic log: {}'.format(exc), file=sys.stderr)
        return 1
    with log, redirect_stdout(Tee(sys.stdout, log)), redirect_stderr(Tee(sys.stderr, log)):
        print('VTD installer | {}'.format(datetime.now(timezone.utc).isoformat()))
        print('Log file: {}'.format(path.resolve()))
        print('Python: {} ({})'.format(sys.version.split()[0], sys.executable))
        code = 1
        try:
            if sys.version_info < (3, 10):
                print('VTD installer requires Python 3.10 or later.', file=sys.stderr)
            else:
                from tools.install import main
                code = main()
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if exc.code and not isinstance(exc.code, int):
                print(exc.code, file=sys.stderr)
        except KeyboardInterrupt:
            print('VTD: cancelled.', file=sys.stderr)
            code = 130
        except Exception:
            traceback.print_exc()
        finally:
            print('VTD exit code: {}'.format(code))
        return code

if __name__ == '__main__':
    raise SystemExit(run())
