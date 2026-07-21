# Copyright (C) 2026 Carota-Bunny
# SPDX-License-Identifier: AGPL-3.0-only

import sys


if __name__ == "__main__":
    if "--engine-smoke-test" in sys.argv:
        from metacleaner.selftest import run_engine_smoke_test

        raise SystemExit(run_engine_smoke_test())

    from metacleaner.gui import run_app

    raise SystemExit(run_app(smoke_test="--smoke-test" in sys.argv))
