"""
Flow B topic queue, stored in the dashboard (pipeline.hub).

Status lifecycle: Ready → Producing → Done (sent for review) / Posted
(auto-published) / Failed. "Hold" parks a topic. When nothing is Ready the
writer proposes a new topic, which is added here so it is never repeated.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import hub

READY, PRODUCING, DONE, POSTED, FAILED = "Ready", "Producing", "Done", "Posted", "Failed"


@dataclass
class Topic:
    ref: str | None          # queue id in the dashboard; None for one-off topics
    topic: str
    angle: str = ""
    source: str = "queue"    # queue | auto | cli


def claim() -> tuple[Topic | None, list[str]]:
    """Next Ready topic (now Producing), plus all previous topics when empty."""
    res = hub.claim("story")
    item = res.get("item")
    if item:
        return Topic(ref=item["id"], topic=item["topic"], angle=item.get("angle", "")), []
    return None, list(res.get("previousTopics") or [])


def add_auto(topic: str, angle: str) -> Topic:
    item = hub.create_story(topic, angle, status=PRODUCING, source="auto")
    return Topic(ref=item["id"], topic=topic, angle=angle, source="auto")


def update(ref: str | None, **patch) -> None:
    if ref:
        hub.update("story", ref, **patch)


def start(topic: str, angle: str = "") -> Topic:
    """Make a specific topic now: reuses its queue entry if one exists."""
    item = hub.create_story(topic, angle, status=PRODUCING)
    return Topic(ref=item["id"], topic=item["topic"], angle=item.get("angle", ""), source="cli")
