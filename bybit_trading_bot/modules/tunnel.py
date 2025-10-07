import logging
import os
import re
import subprocess
import threading
import time
from typing import Optional


PUBLIC_URL_REGEX = re.compile(r"https?://[\w.-]*trycloudflare\.com")


class CloudflareTunnel:
    def __init__(
        self,
        bin_path: str,
        local_url: str,
        logger: logging.Logger,
        on_url: Optional[callable] = None,
    ) -> None:
        self.bin_path = bin_path
        self.local_url = local_url
        self.logger = logger
        self.on_url = on_url
        self.process: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        def run():
            try:
                cmd = [
                    self.bin_path,
                    "tunnel",
                    "--url",
                    self.local_url,
                    "--no-autoupdate",
                ]
                self.logger.info(f"Starting Cloudflare Tunnel: {' '.join(cmd)}")
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    universal_newlines=True,
                )
                assert self.process.stdout is not None
                for line in self.process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    self.logger.info(f"cloudflared: {line}")
                    if self.public_url is None:
                        m = PUBLIC_URL_REGEX.search(line)
                        if m:
                            self.public_url = m.group(0)
                            self.logger.info(f"Tunnel URL: {self.public_url}")
                            if self.on_url:
                                try:
                                    self.on_url(self.public_url)
                                except Exception:
                                    self.logger.exception("on_url callback failed")
                rc = self.process.wait()
                self.logger.warning(f"cloudflared exited with code {rc}")
            except FileNotFoundError:
                self.logger.error("cloudflared binary not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
            except Exception:
                self.logger.exception("cloudflared crashed")

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        try:
            if self.process and self.process.poll() is None:
                self.logger.info("Stopping cloudflared...")
                self.process.terminate()
        except Exception:
            self.logger.exception("Failed to stop cloudflared")


