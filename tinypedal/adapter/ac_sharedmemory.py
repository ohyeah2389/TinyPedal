#  TinyPedal is an open-source overlay application for racing simulation.
#  Copyright (C) 2022-2026 TinyPedal developers, see contributors.md file
#
#  This file is part of TinyPedal.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
AC sharedmemory API connector
"""

from __future__ import annotations

import logging
import threading
from time import monotonic, sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # for type checker only
    from thirdparty.pyACSharedMemory import ac_data
    from thirdparty.pyACSharedMemory.ac_mmap import INVALID_INDEX, MAX_VEHICLES, MMapControl
else:  # run time only
    from pyACSharedMemory import ac_data
    from pyACSharedMemory.ac_mmap import INVALID_INDEX, MAX_VEHICLES, MMapControl

logger = logging.getLogger(__name__)


class MMapDataSet:
    """Create mmap data set"""

    __slots__ = ("shmm",)

    def __init__(self) -> None:
        self.shmm = MMapControl(ac_data.ACConstants.AC_SHARED_MEMORY_FILE, ac_data.ACTelemetry)

    def create_mmap(self, access_mode: int) -> None:
        self.shmm.create(access_mode)

    def close_mmap(self) -> None:
        self.shmm.close()

    def update_mmap(self) -> None:
        self.shmm.update()


class SyncData:
    """Synchronize AC data"""

    __slots__ = (
        "_updating",
        "_update_thread",
        "_event",
        "_last_packet",
        "paused",
        "synced",
        "override_player_index",
        "player_index",
        "dataset",
    )

    def __init__(self) -> None:
        self._updating = False
        self._update_thread = None
        self._event = threading.Event()
        self._last_packet = 0

        self.paused = False
        self.synced = False
        self.override_player_index = False
        self.player_index = INVALID_INDEX
        self.dataset = MMapDataSet()

    def start(self, access_mode: int) -> None:
        if self._updating:
            logger.warning("sharedmemory: UPDATING: already started")
            return
        self._updating = True
        self.dataset.create_mmap(access_mode)
        self._event.clear()
        self._update_thread = threading.Thread(target=self.__update, daemon=True)
        self._update_thread.start()
        logger.info("sharedmemory: UPDATING: thread started")
        logger.info("sharedmemory: player index override: %s", self.override_player_index)

    def stop(self) -> None:
        if not self._updating:
            logger.warning("sharedmemory: UPDATING: already stopped")
            return
        self._event.set()
        self._updating = False
        self._update_thread.join()
        self.dataset.close_mmap()

    def __update(self) -> None:
        self.paused = False
        self.synced = False
        event_wait = self._event.wait
        update_delay = 0.5
        last_update_time = monotonic()

        while not event_wait(update_delay):
            self.dataset.update_mmap()
            data = self.dataset.shmm.data

            is_valid = (
                data.magic == ac_data.ACConstants.MAGIC
                and data.versionMajor == ac_data.ACConstants.VERSION_MAJOR
                and data.versionMinor >= ac_data.ACConstants.VERSION_MINOR
            )
            if is_valid and self._last_packet != data.packetId:
                self._last_packet = data.packetId
                self.synced = True
                self.paused = False
                update_delay = 0.01
                last_update_time = monotonic()

                if self.override_player_index:
                    self.player_index = min(max(self.player_index, 0), MAX_VEHICLES - 1)
                else:
                    idx = data.playerCar
                    self.player_index = idx if 0 <= idx < data.carsCount else 0
                continue

            if monotonic() - last_update_time > 2:
                self.paused = True
                self.synced = False
                update_delay = 0.5

        logger.info("sharedmemory: UPDATING: thread stopped")


class ACInfo:
    """AC shared memory data output"""

    __slots__ = (
        "_sync",
        "_access_mode",
        "_state_override",
        "_active_state",
        "_shmm",
    )

    def __init__(self) -> None:
        self._sync = SyncData()
        self._access_mode = 0
        self._state_override = False
        self._active_state = False
        self._shmm = self._sync.dataset.shmm

    def start(self) -> None:
        self._sync.start(self._access_mode)
        sleep(0.05)

    def stop(self) -> None:
        self._sync.stop()

    def setMode(self, mode: int = 0) -> None:
        self._access_mode = mode

    def setStateOverride(self, state: bool = False) -> None:
        self._state_override = state

    def setActiveState(self, state: bool = False) -> None:
        self._active_state = state

    def setPlayerOverride(self, state: bool = False) -> None:
        self._sync.override_player_index = state

    def setPlayerIndex(self, index: int = INVALID_INDEX) -> None:
        self._sync.player_index = min(max(index, INVALID_INDEX), MAX_VEHICLES - 1)

    @property
    def acData(self) -> ac_data.ACTelemetry:
        return self._shmm.data

    @property
    def playerIndex(self) -> int:
        return self._sync.player_index

    @property
    def isPaused(self) -> bool:
        return self._sync.paused

    @property
    def isActive(self) -> bool:
        if self._state_override:
            return self._active_state
        data = self.acData
        return self._sync.synced and self.playerIndex >= 0 and data.status == 2
