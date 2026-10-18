"""Read what maps and map backups a vacuum holds, without changing anything."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from roborock.roborock_typing import RoborockCommand

from .routine_runner import RoutineExecutionError, get_routine_runner

if TYPE_CHECKING:
    from .context import ServerContext


def _first(info: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in info:
            return info[key]
    return None


def summarize_multi_maps(result: Any) -> dict[str, Any]:
    """The robot's get_multi_maps_list answer, reduced to what the dashboard shows.

    The shape follows python-roborock's MultiMapsList: per map a flag, name, add_time, rooms and a
    ``bak_maps`` list of snapshots (each a map flag and add_time). Anything missing is None or empty,
    so an answer in an unexpected shape produces an empty summary rather than an error.
    """
    data = result[0] if isinstance(result, list) and result else result
    if not isinstance(data, dict):
        return {"max_multi_map": None, "max_bak_map": None, "multi_map_count": None, "maps": []}
    maps: list[dict[str, Any]] = []
    for info in data.get("map_info") or []:
        if not isinstance(info, dict):
            continue
        rooms = info.get("rooms")
        backups = info.get("bak_maps")
        maps.append(
            {
                "map_flag": _first(info, "mapFlag", "map_flag"),
                "name": str(info.get("name") or ""),
                "add_time": info.get("add_time"),
                "room_count": len(rooms) if isinstance(rooms, list) else None,
                "backups": [
                    {"map_flag": _first(backup, "mapFlag", "map_flag"), "add_time": backup.get("add_time")}
                    for backup in backups
                    if isinstance(backup, dict)
                ]
                if isinstance(backups, list)
                else [],
            }
        )
    return {
        "max_multi_map": data.get("max_multi_map"),
        "max_bak_map": data.get("max_bak_map"),
        "multi_map_count": data.get("multi_map_count"),
        "maps": maps,
    }


async def read_map_backups(
    ctx: ServerContext,
    device_id: str,
    *,
    send: Callable[[RoborockCommand], Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """Ask the vacuum for its map list and its recoverable maps. Both are read-only requests.

    ``raw`` carries the unmodified answers, because what ``get_recover_maps`` returns on real
    firmware is not known yet and is the point of looking.
    """

    async def default_send(command: RoborockCommand) -> Any:
        return await get_routine_runner(ctx).query(device_id, command)

    send = send or default_send
    listing = await send(RoborockCommand.GET_MULTI_MAPS_LIST)
    raw: dict[str, Any] = {"get_multi_maps_list": listing}
    try:
        raw["get_recover_maps"] = await send(RoborockCommand.GET_RECOVER_MAPS)
    except RoutineExecutionError as exc:
        # A robot that doesn't have it, or doesn't answer, must not hide the map list above.
        raw["get_recover_maps_error"] = str(exc)
    return {"summary": summarize_multi_maps(listing), "raw": raw}
