"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from enum import StrEnum

from opendbc.car import Bus, create_button_events, structs
from opendbc.can.parser import CANParser
from opendbc.car.common.conversions import Conversions as CV
from opendbc.car.tesla.values import DBC, CANBUS
from opendbc.sunnypilot.car.tesla.values import TeslaFlagsSP

ButtonType = structs.CarState.ButtonEvent.Type


class CarStateExt:
  def __init__(self, CP: structs.CarParams, CP_SP: structs.CarParamsSP):
    self.CP = CP
    self.CP_SP = CP_SP

    self.active_touch_points = 0

  def update(self, ret: structs.CarState, ret_sp: structs.CarStateSP, can_parsers: dict[StrEnum, CANParser]) -> None:
    if self.CP_SP.flags & TeslaFlagsSP.HAS_VEHICLE_BUS:
      cp_adas = can_parsers[Bus.adas]

      prev_active_touch_points = self.active_touch_points
      self.active_touch_points = int(cp_adas.vl["UI_status2"]["UI_activeTouchPoints"])

      finger_count = None
      if self.CP_SP.flags & TeslaFlagsSP.MADS_SCREEN_BUTTON_3_FINGER:
        finger_count = 3
      elif self.CP_SP.flags & TeslaFlagsSP.MADS_SCREEN_BUTTON_4_FINGER:
        finger_count = 4
      elif self.CP_SP.flags & TeslaFlagsSP.MADS_SCREEN_BUTTON_5_FINGER:
        finger_count = 5

      if finger_count is not None:
        ret.buttonEvents = [*create_button_events(self.active_touch_points, prev_active_touch_points,
                                                  {finger_count: ButtonType.lkas})]
    cp_party = can_parsers[Bus.party]

    cp_ap_party = can_parsers[Bus.ap_party]

    # legacy S/X cars read DI_state from the chassis bus and TESLA_MODEL_S_HW3 uses the Raven DBC,
    # which has no DI_state at all - so look the signal up defensively in both the define map and
    # the parser that actually carries it.
    # The speed limit signal is called DAS_status on the Model 3/Y CAN database and AutopilotStatus
    # on the legacy S/X one, and the Raven database carries it in neither - so both the message name
    # and the DI_state speed unit are looked up defensively.
    defines = getattr(self, "can_defines", None) or self.can_define.dv
    cp_di_state = can_parsers.get(Bus.chassis, cp_party)
    for speed_limit_msg in ("DAS_status", "AutopilotStatus"):
      try:
        speed_units = defines["DI_state"]["DI_speedUnits"].get(int(cp_di_state.vl["DI_state"]["DI_speedUnits"]), None)
        speed_limit = cp_ap_party.vl[speed_limit_msg]["DAS_fusedSpeedLimit"]
        if defines[speed_limit_msg]["DAS_fusedSpeedLimit"].get(int(speed_limit), None) in ["NONE", "UNKNOWN_SNA"]:
          ret_sp.speedLimit = 0
        elif speed_units == "KPH":
          ret_sp.speedLimit = speed_limit * CV.KPH_TO_MS
        elif speed_units == "MPH":
          ret_sp.speedLimit = speed_limit * CV.MPH_TO_MS
        break
      except (AssertionError, KeyError):
        continue

  @staticmethod
  def get_parser(CP: structs.CarParams, CP_SP: structs.CarParamsSP) -> dict[StrEnum, CANParser]:
    messages = {}

    if CP_SP.flags & TeslaFlagsSP.HAS_VEHICLE_BUS:
      messages[Bus.adas] = CANParser(DBC[CP.carFingerprint][Bus.adas], [], CANBUS.vehicle)

    return messages
