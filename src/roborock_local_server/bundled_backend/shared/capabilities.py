"""Read what a vacuum and its dock report about themselves, without changing anything.

The Roborock app does not guess which dock options exist. The robot answers ``app_get_init_status``
with feature flags and ``get_status`` with a ``dock_type``, and the app maps those through a built-in
table. This asks the same questions, plus the read-only getters behind the dock and robot settings, so
the real values and units on a given robot can be seen before a setter is written for them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from roborock.roborock_typing import RoborockCommand

from .routine_runner import RoutineExecutionError, get_routine_runner

if TYPE_CHECKING:
    from .context import ServerContext

# Getters only. Every one of these is a read; none takes parameters or changes robot state.
PROBE_COMMANDS: tuple[str, ...] = (
    "app_get_init_status",
    "get_status",
    "get_dust_collection_mode",
    "get_wash_towel_mode",
    "get_smart_wash_params",
    "app_get_dryer_setting",
    "get_valley_electricity_timer",
    "get_wash_water_temperature",
    "get_auto_delivery_cleaning_fluid",
    "get_dust_collection_switch_status",
    "get_carpet_clean_mode",
    "app_get_carpet_deep_clean_status",
    "get_dirty_object_detect_status",
    "get_collision_avoid_status",
    "get_mop_motor_status",
    "get_child_lock_status",
    "get_led_status",
    "get_flow_led_status",
    "get_clean_summary",
)


def _unwrap(result: Any) -> Any:
    return result[0] if isinstance(result, list) and len(result) == 1 else result


def decode_features(init_status: Any) -> dict[str, Any]:
    """The feature flags python-roborock derives from an ``app_get_init_status`` answer.

    Returns ``{"supported": [...names...], "unsupported": [...]}`` for the ``is_*`` flags, or an empty
    result when the answer is not in the expected shape; the raw answer is always shown alongside.
    """
    data = _unwrap(init_status)
    if not isinstance(data, dict):
        return {"supported": [], "unsupported": []}
    try:
        from roborock.device_features import DeviceFeatures

        features = DeviceFeatures.from_feature_flags(
            new_feature_info=int(data.get("new_feature_info") or 0),
            new_feature_info_str=str(data.get("new_feature_info_str") or ""),
            feature_info=[int(v) for v in data.get("feature_info") or []],
            product_nickname=None,
        )
    except Exception:  # noqa: BLE001 - a flag table the installed library cannot read must not hide the raw answer
        return {"supported": [], "unsupported": []}
    supported: list[str] = []
    unsupported: list[str] = []
    for name in sorted(vars(features)):
        if not name.startswith("is_"):
            continue
        value = getattr(features, name)
        if value is True:
            supported.append(name)
        elif value is False:
            unsupported.append(name)
    return {"supported": supported, "unsupported": unsupported}


def decode_dock(status: Any) -> dict[str, Any]:
    """What dock the robot reports and which dock capabilities python-roborock derives for it."""
    data = _unwrap(status)
    if not isinstance(data, dict) or data.get("dock_type") is None:
        return {"dock_type": None, "capabilities": []}
    dock_type = data.get("dock_type")
    try:
        from roborock.data.v1 import RoborockDockTypeCode
        from roborock.device_features import RoborockDockFeatures

        features = RoborockDockFeatures.from_dock_type(
            RoborockDockTypeCode(int(dock_type)), has_am=bool(data.get("has_am"))
        )
    except Exception:  # noqa: BLE001 - an unknown dock code is itself useful to show
        return {"dock_type": dock_type, "capabilities": []}
    capabilities = sorted(
        name for name in dir(type(features)) if name.startswith("is_") and getattr(features, name) is True
    )
    return {"dock_type": dock_type, "name": getattr(features.dock_type, "name", None), "capabilities": capabilities}


async def read_capabilities(
    ctx: ServerContext,
    device_id: str,
    *,
    send: Callable[[RoborockCommand], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """Run every probe and return the raw answers with the decoded feature and dock summaries.

    A robot that does not know a command, or does not answer, gets an entry in ``errors`` and the
    rest still run: which commands a model refuses is part of what this is for.
    """

    async def default_send(command: RoborockCommand) -> Any:
        return await get_routine_runner(ctx).query(device_id, command)

    send = send or default_send
    raw: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name in PROBE_COMMANDS:
        try:
            command = RoborockCommand(name)
        except ValueError:
            errors[name] = "not in the installed python-roborock"
            continue
        try:
            raw[name] = await send(command)
        except RoutineExecutionError as exc:
            errors[name] = str(exc)
    return {
        "features": decode_features(raw.get("app_get_init_status")),
        "dock": decode_dock(raw.get("get_status")),
        "raw": raw,
        "errors": errors,
    }
