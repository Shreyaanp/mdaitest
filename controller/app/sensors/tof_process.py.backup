"""Async wrapper around the compiled tof-reader utility."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ToFReaderProcess:
    """Spawns the C++ tof-reader binary and streams distance measurements."""

    def __init__(
        self,
        *,
        binary_path: str,
        i2c_bus: str,
        i2c_address: int,
        xshut_path: Optional[str],
        output_hz: int,
    ) -> None:
        self.binary_path = binary_path
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.xshut_path = xshut_path
        self.output_hz = output_hz

        self._proc: Optional[asyncio.subprocess.Process] = None
        self._stdout_task: Optional[asyncio.Task[None]] = None
        self._stderr_task: Optional[asyncio.Task[None]] = None
        self._latest_distance: Optional[int] = None
        self._ready_event = asyncio.Event()
        self._restart_lock = asyncio.Lock()

    async def start(self) -> None:
        """Launch the reader process if it is not already running."""

        if self._proc and self._proc.returncode is None:
            return

        async with self._restart_lock:
            if self._proc and self._proc.returncode is None:
                return

            path = Path(self.binary_path)
            if not path.exists():
                raise FileNotFoundError(f"ToF reader binary not found: {path}")

            cmd = [
                str(path),
                "--bus",
                self.i2c_bus,
                "--addr",
                hex(self.i2c_address),
                "--hz",
                str(max(1, self.output_hz)),
            ]
            if self.xshut_path:
                cmd.extend(["--xshut", self.xshut_path])

            logger.info("ToF reader starting on %s @ %dHz", self.i2c_bus, self.output_hz)
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._ready_event.clear()
            self._stdout_task = asyncio.create_task(self._consume_stdout(), name="tof-reader-stdout")
            if self._proc.stderr:
                self._stderr_task = asyncio.create_task(self._consume_stderr(), name="tof-reader-stderr")

    async def stop(self) -> None:
        """Stop the reader process and clean up tasks."""

        tasks: list[asyncio.Task[None]] = []
        if self._stdout_task:
            self._stdout_task.cancel()
            tasks.append(self._stdout_task)
            self._stdout_task = None
        if self._stderr_task:
            self._stderr_task.cancel()
            tasks.append(self._stderr_task)
            self._stderr_task = None

        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
        self._proc = None

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._latest_distance = None
        self._ready_event.clear()

    async def get_distance(self) -> Optional[int]:
        """Return the most recent distance measurement from the process."""

        if not self._proc or self._proc.returncode is not None:
            # Process died; attempt a restart on the next loop.
            await self.start()

        if not self._ready_event.is_set():
            try:
                await asyncio.wait_for(self._ready_event.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                return None

        return self._latest_distance

    async def _consume_stdout(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            while True:
                raw_line = await self._proc.stdout.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", "ignore").strip()
                if not line:
                    continue
                distance = self._parse_distance(line)
                if distance is not None:
                    self._latest_distance = distance
                    self._ready_event.set()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed while reading tof-reader output: %s", exc)
        finally:
            if self._proc:
                returncode = await self._proc.wait()
                if returncode != 0:
                    logger.error("ToF reader crashed (exit code %d)", returncode)
            self._ready_event.clear()
            self._latest_distance = None

    async def _consume_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        try:
            while True:
                raw_line = await self._proc.stderr.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", "ignore").strip()
                if line:
                    logger.error("ToF sensor error: %s", line)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed while reading tof-reader stderr: %s", exc)

    @staticmethod
    def _parse_distance(line: str) -> Optional[int]:
        if not line:
            return None
        if line.startswith("{"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return None
            try:
                distance = int(payload.get("distance_mm"))
            except (TypeError, ValueError):
                return None
            return distance
        try:
            return int(float(line))
        except ValueError:
            return None
