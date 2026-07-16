"""
AC API data reader
"""

from __future__ import annotations

from math import radians

from ..calculation import lap_progress_distance, mean, vel2speed
from ..const_common import STINT_USAGE_DEFAULT
from ..formatter import strip_invalid_char
from ..process.weather import WeatherNode
from ..validator import bytes_to_str as tostr
from ..validator import infnan_to_zero as rmnan
from . import _reader
from .ac_connector import ACInfo

G_ACCEL = 9.80665

class DataAdapter:
    __slots__ = ("shmm", "rest")

    def __init__(self, shmm: ACInfo, rest=None) -> None:
        self.shmm = shmm
        self.rest = rest

    def _d(self):
        return self.shmm.acData

    def _i(self, index: int | None = None) -> int:
        data = self._d()
        if index is None:
            index = self.shmm.playerIndex
        return min(max(index, 0), max(data.carsCount - 1, 0))

    def _player(self, index: int | None = None) -> bool:
        return self._i(index) == self._i(None)

    def _meta(self, index: int | None = None):
        return self._d().carMeta[self._i(index)]

    @staticmethod
    def _zero4() -> tuple[float, float, float, float]:
        return (0.0, 0.0, 0.0, 0.0)

#MARK: State
class State(_reader.State, DataAdapter):
    __slots__ = ()

    def active(self) -> bool:
        return self.shmm.isActive

    def paused(self) -> bool:
        return self.shmm.isPaused

    def desynced(self, index: int | None = None) -> bool:
        data = self._d()
        i = self._i(index)
        p = self._i(None)
        return abs(data.carLapTimeMs[p] - data.carLapTimeMs[i]) >= 10

    def version(self) -> str:
        data = self._d()
        return f"{data.versionMajor}.{data.versionMinor}"

#MARK: Brake
class Brake(_reader.Brake, DataAdapter):
    __slots__ = ()

    def bias_front(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.5
        return rmnan(self._d().playerBrakeBias)

    def migration(self, index: int | None = None) -> float:
        return 0.0

    def pressure(self, index: int | None = None, scale: float = 1) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        d = self._d()
        return tuple(rmnan(x) * scale for x in d.wheelPressure)

    def temperature(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) for x in self._d().brakeTemperature)

    def wear(self, index: int | None = None) -> tuple[float, ...]:
        return self._zero4()

#MARK: ElectricMotor
class ElectricMotor(_reader.ElectricMotor, DataAdapter):
    __slots__ = ()

    def state(self, index: int | None = None) -> int:
        if self._player(index):
            if self._d().playerKersInput > 0:
                return 2
            if self._d().playerKersCharge > 0:
                return 1
        return 0

    def battery_charge(self, index: int | None = None) -> float:
        return rmnan(self._d().playerKersCharge if self._player(index) else 0.0)

    def rpm(self, index: int | None = None) -> float:
        return 0.0

    def torque(self, index: int | None = None) -> float:
        return 0.0

    def motor_temperature(self, index: int | None = None) -> float:
        return 0.0

    def water_temperature(self, index: int | None = None) -> float:
        return rmnan(self._d().playerWaterTemp if self._player(index) else 0.0)

    def regeneration_level(self, index: int | None = None) -> float:
        return rmnan((self._d().playerMgukRecovery / 10) if self._player(index) else 0.0)

#MARK: Engine
class Engine(_reader.Engine, DataAdapter):
    __slots__ = ()

    def gear(self, index: int | None = None) -> int:
        d = self._d()
        return int(d.playerGear if self._player(index) else d.carGear[self._i(index)])

    def gear_max(self, index: int | None = None) -> int:
        return int(self._d().playerGearCount if self._player(index) else 0)

    def rpm(self, index: int | None = None) -> float:
        d = self._d()
        return rmnan(d.playerRpm if self._player(index) else d.carRpm[self._i(index)])

    def rpm_max(self, index: int | None = None) -> float:
        if self._player(index):
            limiter = rmnan(self._d().playerRpmLimiter)
            if limiter > 1000:
                return limiter
        rpm_now = self.rpm(index)
        return max(rpm_now * 1.15, 6000.0)

    def torque(self, index: int | None = None) -> float:
        return rmnan(self._d().playerDrivetrainTorque if self._player(index) else 0.0)

    def turbo(self, index: int | None = None) -> float:
        return rmnan(self._d().playerTurboBoost if self._player(index) else 0.0)

    def oil_temperature(self, index: int | None = None) -> float:
        return rmnan(self._d().playerOilTemp if self._player(index) else 0.0)

    def water_temperature(self, index: int | None = None) -> float:
        return rmnan(self._d().playerWaterTemp if self._player(index) else 0.0)

    def lift_and_coast_progress(self, index: int | None = None) -> float:
        return 0.0

    def fuel(self, index: int | None = None) -> float:
        d = self._d()
        return rmnan(d.playerFuel if self._player(index) else d.carFuel[self._i(index)])

    def fuel_fraction(self, index: int | None = None) -> float:
        d = self._d()
        if self._player(index) and d.playerMaxFuel > 0:
            return rmnan(d.playerFuel / d.playerMaxFuel)
        return 0.0

    def tank_capacity(self, index: int | None = None) -> float:
        return rmnan(self._d().playerMaxFuel if self._player(index) else 0.0)

    def virtual_energy(self, index: int | None = None) -> float:
        return 0.0

    def max_virtual_energy(self) -> float:
        return 0.0

#MARK: Inputs
class Inputs(_reader.Inputs, DataAdapter):
    __slots__ = ()

    def throttle(self, index: int | None = None) -> float:
        return rmnan(self._d().playerGas if self._player(index) else 0.0)

    def throttle_raw(self, index: int | None = None) -> float:
        return self.throttle(index)

    def brake(self, index: int | None = None) -> float:
        return rmnan(self._d().playerBrake if self._player(index) else 0.0)

    def brake_raw(self, index: int | None = None) -> float:
        return self.brake(index)

    def clutch(self, index: int | None = None) -> float:
        return rmnan(self._d().playerClutch if self._player(index) else 0.0)

    def clutch_raw(self, index: int | None = None) -> float:
        return self.clutch(index)

    def steering(self, index: int | None = None) -> float:
        return rmnan(self._d().playerSteerDeg if self._player(index) else 0.0) / 540.0

    def steering_raw(self, index: int | None = None) -> float:
        return self.steering(index)

    def steering_shaft_torque(self, index: int | None = None) -> float:
        return rmnan(self._d().playerSteerTorque if self._player(index) else 0.0)

    def steering_range_physical(self, index: int | None = None) -> float:
        if not self._player(index):
            return 540.0
        lock = rmnan(self._d().playerSteerLock)
        return max(lock * 2.0, 90.0)

    def steering_range_visual(self, index: int | None = None) -> float:
        return self.steering_range_physical(index)

    def force_feedback(self) -> float:
        return rmnan(self._d().playerFfbFinal)

#MARK: Lap
class Lap(_reader.Lap, DataAdapter):
    __slots__ = ()

    @staticmethod
    def _clamp_progress(value: float) -> float:
        value = rmnan(value)
        if value < 0:
            return 0.0
        if value > 1:
            return 1.0
        return value

    def number(self, index: int | None = None) -> int:
        return self.completed_laps(index) + 1

    def completed_laps(self, index: int | None = None) -> int:
        d = self._d()
        return int(d.playerLapCount if self._player(index) else d.carLapCount[self._i(index)])

    def track_length(self) -> float:
        return rmnan(self._d().trackLengthM)

    def distance(self, index: int | None = None) -> float:
        return self.progress(index) * self.track_length()

    def progress(self, index: int | None = None) -> float:
        d = self._d()
        if self._player(index):
            return self._clamp_progress(d.playerSplinePosition)
        return self._clamp_progress(d.carSplinePosition[self._i(index)])

    def maximum(self) -> int:
        return max(self._d().sessionLaps, 0)

    def remaining(self, index: int | None = None) -> float:
        max_laps = self.maximum()
        if max_laps <= 0:
            return 0.0
        return max(max_laps - self.completed_laps(index) - self.progress(index), 0.0)

    def sector_index(self, index: int | None = None) -> int:
        d = self._d()
        sec = d.playerCurrentSector if self._player(index) else d.carCurrentSector[self._i(index)]
        return min(max(sec, 0), 2)

    def behind_leader(self, index: int | None = None) -> int:
        return max(self._d().leaderCompletedLaps - self.completed_laps(index), 0)

    def behind_next(self, index: int | None = None) -> int:
        return 0

    def safety_car_distance(self) -> float:
        return 0.0

    def safety_car_active(self) -> bool:
        return False

#MARK: Session
class Session(_reader.Session, DataAdapter):
    __slots__ = ()

    def combo_name(self) -> str:
        d = self._d()
        return strip_invalid_char(f"{tostr(d.trackID)} - {tostr(d.playerCarID)}")

    def track_name(self) -> str:
        return strip_invalid_char(tostr(self._d().trackID))

    def identifier(self) -> tuple[int, int, int]:
        d = self._d()
        return (d.sessionType, d.sessionIndex, int(d.sessionTimestamp))

    def elapsed(self) -> float:
        return rmnan(self._d().sessionElapsedMs) / 1000.0

    def start(self) -> float:
        return 0.0

    def end(self) -> float:
        d = self._d()
        return max(rmnan(d.sessionDurationMinutes) * 60.0, 0.0)

    def remaining(self) -> float:
        return max(rmnan(self._d().sessionTimeLeftMs) / 1000.0, 0.0)

    def session_type(self) -> int:
        return min(max(self._d().sessionType, 0), 4)

    def finish_type(self, as_lap: bool | None = None) -> int:
        d = self._d()
        if d.sessionIsTimedRace and d.sessionLaps > 0:
            return 2
        if d.sessionIsTimedRace:
            return 0
        return 1

    def in_race(self) -> bool:
        return self.session_type() == 4

    def private_qualifying(self) -> bool:
        return False

    def pit_open(self) -> bool:
        return True

    def pre_race(self) -> bool:
        return self.in_race() and not self.green_flag()

    def green_flag(self) -> bool:
        return self.in_race() and self._d().raceFlagType == 0 and not self._d().sessionIsOver

    def blue_flag(self, index: int | None = None) -> bool:
        return self._d().raceFlagType == 6

    def yellow_flag(self) -> bool:
        return self._d().raceFlagType in (2, 3)

    def start_lights(self) -> int:
        return 0

    def track_temperature(self) -> float:
        return rmnan(self._d().roadTemp)

    def ambient_temperature(self) -> float:
        return rmnan(self._d().ambientTemp)

    def raininess(self) -> float:
        return rmnan(self._d().rainIntensity)

    def wetness_minimum(self) -> float:
        return rmnan(self._d().rainWetness)

    def wetness_maximum(self) -> float:
        return max(rmnan(self._d().rainWetness), rmnan(self._d().rainWater))

    def wetness_average(self) -> float:
        return mean((self.wetness_minimum(), self.wetness_maximum()))

    def wetness(self) -> tuple[float, float, float]:
        avg = self.wetness_average()
        return (self.wetness_minimum(), self.wetness_maximum(), avg)

    def weather_forecast(self) -> tuple[WeatherNode, ...]:
        return tuple()

    def cloud_coverage(self) -> int:
        return min(max(int(self._d().weatherType), 0), 10)

    def grip_level(self) -> float:
        return rmnan(self._d().roadGrip)

    def track_time(self) -> float:
        return rmnan(self._d().trackTimeSec)

    def time_scale(self) -> int:
        return int(max(self._d().timeMultiplier, 1))

    def limits_points(self) -> float:
        return 0.0

    def cut_points(self, index: int | None = None) -> float:
        return 0.0

#MARK: Switch
class Switch(_reader.Switch, DataAdapter):
    __slots__ = ()

    def tc_level(self, index: int | None = None) -> int:
        return int(self._d().playerTCMode if self._player(index) else 0)

    def tc_cut_level(self, index: int | None = None) -> int:
        return int(self._d().playerTC2Mode if self._player(index) else 0)

    def tc_slip_level(self, index: int | None = None) -> int:
        return 0

    def abs_level(self, index: int | None = None) -> int:
        return int(self._d().playerABSMode if self._player(index) else 0)

    def motor_map_level(self, index: int | None = None) -> int:
        if not self._player(index):
            return -1
        d = self._d()
        if not d.playerMgukDeliveryCount:
            return -1
        return int(d.playerMgukDelivery)

    def brake_migration_level(self, index: int | None = None) -> int:
        return 0

    def front_arb_level(self, index: int | None = None) -> int:
        return 0

    def rear_arb_level(self, index: int | None = None) -> int:
        return 0

    def wipers(self, index: int | None = None) -> int:
        return int(self._d().playerWiperMode if self._player(index) else 0)

    def headlights(self, index: int | None = None) -> int:
        return int(self._d().playerHeadlightsActive) if self._player(index) else 0

    def ignition_starter(self, index: int | None = None) -> int:
        return 1 if self.shmm.isActive else 0

    def speed_limiter(self, index: int | None = None) -> int:
        return int(self._d().playerSpeedLimiterInAction) if self._player(index) else 0

    def tc_active(self, index: int | None = None) -> bool:
        return bool(self._d().playerTCInAction) if self._player(index) else False

    def abs_active(self, index: int | None = None) -> bool:
        return bool(self._d().playerABSInAction) if self._player(index) else False

    def drs_status(self, index: int | None = None) -> int:
        if not self._player(index):
            return 0
        d = self._d()
        if d.playerDrsActive:
            return 3
        if d.playerDrsAvailable:
            return 2
        return 0

    def auto_clutch(self) -> bool:
        return False

#MARK: Timing
class Timing(_reader.Timing, DataAdapter):
    __slots__ = ()

    def start(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerLapStartMs if self._player(index) else d.carLapStartMs[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def elapsed(self, index: int | None = None) -> float:
        d = self._d()
        if self._player(index):
            return rmnan(d.simTimeMs) / 1000.0
        i = self._i(index)
        return max((rmnan(d.carLapStartMs[i]) + rmnan(d.carLapTimeMs[i])) / 1000.0, 0.0)

    def current_laptime(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerLapTimeMs if self._player(index) else d.carLapTimeMs[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def last_laptime(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerPreviousLapTimeMs if self._player(index) else d.carPreviousLapTimeMs[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def best_laptime(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerBestLapTimeMs if self._player(index) else d.carBestLapTimeMs[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def reference_laptime(self, index: int | None = None, laptime: float = 0) -> float:
        best = self.best_laptime(index)
        return best if best > 0 else laptime

    def estimated_laptime(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerEstimatedLapTimeMs if self._player(index) else d.carEstimatedLapTimeMs[self._i(index)]
        estimate = max(rmnan(ms) / 1000.0, 0.0)
        if estimate > 1.0:
            return estimate
        for value in (self.best_laptime(index), self.last_laptime(index)):
            if value > 1.0:
                return value
        return 0.0

    def estimated_time_into(self, index: int | None = None) -> float:
        if self._player(index):
            return self.current_laptime(index)
        d = self._d()
        est_lap = self.estimated_laptime(index)
        if est_lap > 1.0:
            progress = min(max(rmnan(d.carSplinePosition[self._i(index)]), 0.0), 1.0)
            return progress * est_lap
        return self.current_laptime(index)

    def current_sector1(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerCurrentSector1Ms if self._player(index) else d.carCurrentSector1Ms[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def current_sector2(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerCurrentSector2Ms if self._player(index) else d.carCurrentSector2Ms[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def last_sector1(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerLastSector1Ms if self._player(index) else d.carLastSector1Ms[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def last_sector2(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerLastSector2Ms if self._player(index) else d.carLastSector2Ms[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def best_sector1(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerBestSector1Ms if self._player(index) else d.carBestSector1Ms[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def best_sector2(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerBestSector2Ms if self._player(index) else d.carBestSector2Ms[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def behind_leader(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerGapBehindLeaderMs if self._player(index) else d.carGapBehindLeaderMs[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

    def behind_next(self, index: int | None = None) -> float:
        d = self._d()
        ms = d.playerGapBehindNextMs if self._player(index) else d.carGapBehindNextMs[self._i(index)]
        return max(rmnan(ms) / 1000.0, 0.0)

#MARK: Tyre
class Tyre(_reader.Tyre, DataAdapter):
    __slots__ = ()

    def compound_index(self, index: int | None = None) -> tuple[int, ...]:
        if not self._player(index):
            return (0, 0, 0, 0)
        ci = int(self._d().playerCompoundIndex)
        return (ci, ci, ci, ci)

    def compound_name(self, index: int | None = None) -> tuple[str, ...]:
        if not self._player(index):
            return ("", "", "", "")
        name = tostr(self._d().playerTyresName)
        return (name, name, name, name)

    def compound_class(self, index: int | None = None) -> tuple[str, ...]:
        return self.compound_name(index)

    def surface_temperature_avg(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) for x in self._d().tyreTempM)

    def surface_temperature_ico(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return (0.0,) * 12
        d = self._d()
        return (
            rmnan(d.tyreTempI[0]),
            rmnan(d.tyreTempM[0]),
            rmnan(d.tyreTempO[0]),
            rmnan(d.tyreTempI[1]),
            rmnan(d.tyreTempM[1]),
            rmnan(d.tyreTempO[1]),
            rmnan(d.tyreTempI[2]),
            rmnan(d.tyreTempM[2]),
            rmnan(d.tyreTempO[2]),
            rmnan(d.tyreTempI[3]),
            rmnan(d.tyreTempM[3]),
            rmnan(d.tyreTempO[3]),
        )

    def inner_temperature_avg(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) for x in self._d().tyreCoreTemperature)

    def inner_temperature_ico(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return (0.0,) * 12
        d = self._d()
        return (
            rmnan(d.tyreTempI[0]),
            rmnan(d.tyreTempM[0]),
            rmnan(d.tyreTempO[0]),
            rmnan(d.tyreTempI[1]),
            rmnan(d.tyreTempM[1]),
            rmnan(d.tyreTempO[1]),
            rmnan(d.tyreTempI[2]),
            rmnan(d.tyreTempM[2]),
            rmnan(d.tyreTempO[2]),
            rmnan(d.tyreTempI[3]),
            rmnan(d.tyreTempM[3]),
            rmnan(d.tyreTempO[3]),
        )

    def pressure(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) for x in self._d().wheelPressure)

    def load(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) for x in self._d().wheelLoad)

    def wear(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(max(1.0 - rmnan(x), 0.0) for x in self._d().tyreWear)

    def carcass_temperature(self, index: int | None = None) -> tuple[float, ...]:
        return self.inner_temperature_avg(index)

    def vertical_deflection(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) * 1000 for x in self._d().suspensionTravel)

#MARK: Vehicle
class Vehicle(_reader.Vehicle, DataAdapter):
    __slots__ = ()

    def incidents(self, index: int | None = None) -> int:
        return 0

    def is_player(self, index: int = 0) -> bool:
        return self._i(index) == self._i(None)

    def is_driving(self) -> bool:
        return self.shmm.isActive

    def player_index(self) -> int:
        return self._i(None)

    def slot_id(self, index: int | None = None) -> int:
        return int(self._d().carSessionID[self._i(index)])

    def driver_name(self, index: int | None = None) -> str:
        if self._player(index):
            return tostr(self._d().playerDriverName)
        return tostr(self._meta(index).driverName)

    def vehicle_name(self, index: int | None = None) -> str:
        return tostr(self._meta(index).carName)

    def vehicle_model(self, index: int | None = None) -> str:
        return tostr(self._meta(index).carID)

    def class_name(self, index: int | None = None) -> str:
        return tostr(self._meta(index).carID)

    def same_class(self, index: int | None = None) -> bool:
        return self.class_name(index) == self.class_name(None)

    def total_vehicles(self) -> int:
        return int(self._d().carsCount)

    def place(self, index: int | None = None) -> int:
        return int(self._d().carRacePosition[self._i(index)])

    def qualification(self, index: int | None = None) -> int:
        return self.place(index)

    def in_pits(self, index: int | None = None) -> bool:
        return bool(self._d().carInPitlane[self._i(index)])

    def in_garage(self, index: int | None = None) -> bool:
        return bool(self._d().carInPit[self._i(index)])

    def in_paddock(self, index: int | None = None) -> int:
        if self.in_garage(index):
            return 2
        if self.in_pits(index):
            return 1
        return 0

    def number_pitstops(self, index: int | None = None, penalty: int = 0) -> int:
        return 0

    def number_penalties(self, index: int | None = None) -> int:
        return 0

    def pit_request(self, index: int | None = None) -> bool:
        return bool(self._d().carInPitlane[self._i(index)])

    def pit_stop_time(self) -> float:
        return 0.0

    def absolute_refill(self) -> float:
        return 0.0

    def stint_usage(self, driver_name: str) -> tuple[float, float, float, float, int]:
        return STINT_USAGE_DEFAULT

    def finish_state(self, index: int | None = None) -> int:
        return 1 if self._d().sessionIsOver else 0

    def orientation_yaw_radians(self, index: int | None = None) -> float:
        d = self._d()
        deg = d.playerYawAngleDeg if self._player(index) else d.carYawAngleDeg[self._i(index)]
        return radians(rmnan(deg))

    def position_xyz(self, index: int | None = None) -> tuple[float, float, float]:
        d = self._d()
        if self._player(index):
            p = d.playerPosition
        else:
            p = d.carPosition[self._i(index)]
        return (rmnan(p.x), rmnan(p.y), rmnan(p.z))

    def position_longitudinal(self, index: int | None = None) -> float:
        return self.position_xyz(index)[0]

    def position_lateral(self, index: int | None = None) -> float:
        return self.position_xyz(index)[2]

    def position_vertical(self, index: int | None = None) -> float:
        return self.position_xyz(index)[1]

    def accel_lateral(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return rmnan(self._d().playerAcceleration.x) * G_ACCEL

    def accel_longitudinal(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return -rmnan(self._d().playerAcceleration.z) * G_ACCEL

    def accel_vertical(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return rmnan(self._d().playerAcceleration.y) * G_ACCEL

    def velocity_lateral(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return rmnan(self._d().playerLocalVelocity.x)

    def velocity_longitudinal(self, index: int | None = None) -> float:
        if not self._player(index):
            return rmnan(self._d().carSpeedKmh[self._i(index)]) / 3.6
        return rmnan(self._d().playerLocalVelocity.z)

    def velocity_vertical(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return rmnan(self._d().playerLocalVelocity.y)

    def speed(self, index: int | None = None) -> float:
        d = self._d()
        kmh = d.playerSpeedKmh if self._player(index) else d.carSpeedKmh[self._i(index)]
        return rmnan(kmh) / 3.6

    def downforce_front(self, index: int | None = None) -> float:
        return 0.0

    def downforce_rear(self, index: int | None = None) -> float:
        return 0.0

    def damage_severity(self, index: int | None = None) -> tuple[int, int, int, int, int, int, int, int]:
        if not self._player(index):
            return (0, 0, 0, 0, 0, 0, 0, 0)
        dmg = self._d().playerDamage
        return (
            int(dmg[0] * 2),
            int(dmg[1] * 2),
            int(dmg[2] * 2),
            int(dmg[3] * 2),
            int(dmg[4] * 2),
            0, 0, 0,
        )

    def aero_damage(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return rmnan(self._d().playerDamage[4])

    def integrity(self, index: int | None = None) -> float:
        if not self._player(index):
            return 1.0
        return max(1.0 - max(self._d().playerDamage), 0.0)

    def is_detached(self, index: int | None = None) -> bool:
        return False

    def impact_time(self, index: int | None = None) -> float:
        if not self._player(index):
            return 0.0
        return max(rmnan(self._d().playerLastImpactMs) / 1000.0, 0.0)

    def impact_magnitude(self, index: int | None = None) -> float:
        return 0.0

    def impact_position(self, index: int | None = None) -> tuple[float, float]:
        return (0.0, 0.0)

    def setup(self) -> tuple[str, ...]:
        return tuple()

#MARK: Wheel
class Wheel(_reader.Wheel, DataAdapter):
    __slots__ = ()

    def camber(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(radians(rmnan(x)) for x in self._d().camberDeg)

    def toe(self, index: int | None = None) -> tuple[float, ...]:
        return self._zero4()

    def toe_symmetric(self, index: int | None = None) -> tuple[float, ...]:
        return self.toe(index)

    def rotation(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(-abs(rmnan(x)) for x in self._d().wheelAngularSpeed)

    def velocity_lateral(self, index: int | None = None) -> tuple[float, ...]:
        return self._zero4()

    def velocity_longitudinal(self, index: int | None = None) -> tuple[float, ...]:
        return self._zero4()

    def slip_angle_fl(self, index: int | None = None) -> float:
        return rmnan(self._d().wheelSlipAngleRad[0]) if self._player(index) else 0.0

    def slip_angle_fr(self, index: int | None = None) -> float:
        return rmnan(self._d().wheelSlipAngleRad[1]) if self._player(index) else 0.0

    def slip_angle_rl(self, index: int | None = None) -> float:
        return rmnan(self._d().wheelSlipAngleRad[2]) if self._player(index) else 0.0

    def slip_angle_rr(self, index: int | None = None) -> float:
        return rmnan(self._d().wheelSlipAngleRad[3]) if self._player(index) else 0.0

    def ride_height(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        d = self._d().suspensionTravel
        return (d[0] * 1000, d[1] * 1000, d[2] * 1000, d[3] * 1000)

    def third_spring_deflection(self, index: int | None = None) -> tuple[float, ...]:
        return (0.0, 0.0)

    def suspension_deflection(self, index: int | None = None) -> tuple[float, ...]:
        return self.ride_height(index)

    def suspension_force(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        return tuple(rmnan(x) for x in self._d().wheelLoad)

    def suspension_damage(self, index: int | None = None) -> tuple[float, ...]:
        return self._zero4()

    def position_vertical(self, index: int | None = None) -> tuple[float, ...]:
        if not self._player(index):
            return self._zero4()
        pts = self._d().tyreContactPoint
        return (pts[0].y * 1000, pts[1].y * 1000, pts[2].y * 1000, pts[3].y * 1000)

    def is_detached(self, index: int | None = None) -> tuple[bool, ...]:
        return (False, False, False, False)

    def offroad(self, index: int | None = None) -> int:
        return int(self._d().playerWheelsOutside if self._player(index) else 0)

