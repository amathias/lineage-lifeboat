from __future__ import annotations

import uvicorn

from lineage_lifeboat.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "lineage_lifeboat.api:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()