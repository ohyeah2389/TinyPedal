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
AC API connector
"""

from ..constant import API
from ..validator import string_converter
from . import ac_reader, ac_sharedmemory
from ._connector import APIDataReader, Connector


class SimAC(Connector):
    """AC/CSP Shared Memory API"""

    NAME = API.NAME_AC
    LEGACY = False
    __slots__ = (
        # Primary API
        "_shmmapi",
    )

    def __init__(self):
        self._shmmapi = ac_sharedmemory.ACInfo()

    def start(self):
        self._shmmapi.start()

    def stop(self):
        self._shmmapi.stop()

    def reader(self) -> APIDataReader:
        shmm = self._shmmapi
        return APIDataReader(
            ac_reader.State(shmm),
            ac_reader.Brake(shmm),
            ac_reader.ElectricMotor(shmm),
            ac_reader.Engine(shmm),
            ac_reader.Inputs(shmm),
            ac_reader.Lap(shmm),
            ac_reader.Session(shmm),
            ac_reader.Switch(shmm),
            ac_reader.Timing(shmm),
            ac_reader.Tyre(shmm),
            ac_reader.Vehicle(shmm),
            ac_reader.Wheel(shmm),
        )

    def setup(self, config: dict):
        self._shmmapi.setMode(config["access_mode"])
        self._shmmapi.setStateOverride(config["enable_active_state_override"])
        self._shmmapi.setActiveState(config["active_state"])
        self._shmmapi.setPlayerOverride(config["enable_player_index_override"])
        self._shmmapi.setPlayerIndex(config["player_index"])
        ac_reader.tostr = string_converter(config["character_encoding"])
