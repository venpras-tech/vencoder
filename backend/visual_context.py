import base64
import json
import logging
from typing import Any, Optional

log = logging.getLogger("visual_context")


def build_visual_instruction(
    user_prompt: str,
    image_b64: Optional[str] = None,
    interactions: Optional[list[dict[str, Any]]] = None,
) -> str:
    parts = []
    if interactions:
        for i, act in enumerate(interactions, 1):
            t = act.get("type", "click")
            x = act.get("x", 0)
            y = act.get("y", 0)
            w = act.get("w")
            h = act.get("h")
            elem = act.get("element")
            color = act.get("color")
            if t == "click":
                parts.append(f"Interaction {i}: User clicked at position ({x}, {y})" + (f" on element: {elem}" if elem else ""))
            elif t == "highlight":
                parts.append(f"Interaction {i}: User highlighted region at ({x}, {y})" + (f" size {w}x{h}" if w and h else "") + (f", element: {elem}" if elem else ""))
            elif t == "drag":
                x2 = act.get("x2", x)
                y2 = act.get("y2", y)
                parts.append(f"Interaction {i}: User dragged from ({x}, {y}) to ({x2}, {y2})" + (f", element: {elem}" if elem else ""))
            if color:
                parts[-1] += f", color hint: {color}"
    if parts:
        instruction = "[Visual context - user interactions on the image]\n" + "\n".join(parts) + "\n\n"
    else:
        instruction = "[Visual context - user is referring to the attached image]\n\n"
    return instruction + "User instruction: " + (user_prompt or "")


def build_visual_message_content(
    user_prompt: str,
    image_b64: Optional[str] = None,
    interactions: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    text = build_visual_instruction(user_prompt, image_b64, interactions)
    content = []
    if image_b64:
        url = f"data:image/png;base64,{image_b64}" if not image_b64.startswith("data:") else image_b64
        content.append({"type": "image_url", "image_url": {"url": url}})
    content.append({"type": "text", "text": text})
    return content
