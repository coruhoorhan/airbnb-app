import copy
from typing import Dict, List, Any, Union

class CanvasPatchManagerV5:
    """
    Manages state synchronization between the backend brain and UI canvas
    using standard JSON patch format to optimize websocket state synchronization.
    Inspired by OpenClaw Live Visualization trend.
    """

    @staticmethod
    def generate_patch(old_state: Union[Dict[str, Any], List[Any], Any], new_state: Union[Dict[str, Any], List[Any], Any], path: str = "") -> List[Dict[str, Any]]:
        """
        Generates a list of JSON patches comparing old_state and new_state.

        Args:
            old_state (Union[Dict[str, Any], List[Any], Any]): The previous state.
            new_state (Union[Dict[str, Any], List[Any], Any]): The current state.
            path (str): The current path prefix.

        Returns:
            List[Dict[str, Any]]: A list of JSON patch operations.
        """
        patches = []

        if isinstance(old_state, dict) and isinstance(new_state, dict):
            for key in new_state:
                current_path = f"{path}/{key}"
                if key not in old_state:
                    patches.append({"op": "add", "path": current_path, "value": copy.deepcopy(new_state[key])})
                else:
                    patches.extend(CanvasPatchManagerV5.generate_patch(old_state[key], new_state[key], current_path))

            for key in old_state:
                current_path = f"{path}/{key}"
                if key not in new_state:
                    patches.append({"op": "remove", "path": current_path})
        elif isinstance(old_state, list) and isinstance(new_state, list):
            # For lists, if they are different, we replace the whole list for simplicity
            if old_state != new_state:
                 patches.append({"op": "replace", "path": path if path else "/", "value": copy.deepcopy(new_state)})
        else:
            if old_state != new_state:
                 patches.append({"op": "replace", "path": path if path else "/", "value": copy.deepcopy(new_state)})

        return patches

    @staticmethod
    def apply_patch(state: Union[Dict[str, Any], List[Any]], patch: List[Dict[str, Any]]) -> Union[Dict[str, Any], List[Any]]:
        """
        Applies a list of JSON patch operations to a state.

        Args:
            state (Union[Dict[str, Any], List[Any]]): The state to apply the patch to.
            patch (List[Dict[str, Any]]): The JSON patch operations.

        Returns:
            Union[Dict[str, Any], List[Any]]: The updated state.
        """
        if not patch:
            return copy.deepcopy(state)

        new_state = copy.deepcopy(state)

        for op in patch:
            path_str = op.get("path", "")
            if path_str == "/" or not path_str:
                if op["op"] == "replace":
                    new_state = copy.deepcopy(op.get("value"))
                continue

            path_parts = path_str.strip("/").split("/")

            target = new_state
            for part in path_parts[:-1]:
                if isinstance(target, dict):
                    target = target[part]
                elif isinstance(target, list):
                    target = target[int(part)]

            last_part = path_parts[-1]

            if op["op"] == "add":
                if isinstance(target, dict):
                    target[last_part] = copy.deepcopy(op.get("value"))
                elif isinstance(target, list):
                    target.insert(int(last_part), copy.deepcopy(op.get("value")))
            elif op["op"] == "replace":
                if isinstance(target, dict):
                    target[last_part] = copy.deepcopy(op.get("value"))
                elif isinstance(target, list):
                    target[int(last_part)] = copy.deepcopy(op.get("value"))
            elif op["op"] == "remove":
                if isinstance(target, dict):
                    if last_part in target:
                        del target[last_part]
                elif isinstance(target, list):
                    idx = int(last_part)
                    if 0 <= idx < len(target):
                        target.pop(idx)

        return new_state
