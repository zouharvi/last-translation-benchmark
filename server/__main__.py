import argparse
import os

import uvicorn

args = argparse.ArgumentParser()
args.add_argument("--port", type=int, default=8000)
args.add_argument("--host", type=str, default="127.0.0.1")
args.add_argument("--host-public", type=str, default="http://127.0.0.1:8000")
args.add_argument(
    "--public-dashboard-source",
    type=str,
    default=None,
    help="Read dashboard records from this public API URL instead of the local database",
)
args = args.parse_args()

os.environ["HOST_PUBLIC"] = args.host_public
if args.public_dashboard_source:
    os.environ["PUBLIC_DASHBOARD_SOURCE_URL"] = args.public_dashboard_source

uvicorn.run(
    "last_translation_benchmark.__init__:app",
    host=args.host,
    port=args.port,
    reload=True,
)

"""
alternatively run:

uvicorn server:app --reload
"""
