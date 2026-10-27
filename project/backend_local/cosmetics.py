"""Cosmetic equipment: avatar, head frame, chat bubble, battle scene and player card.

Client facts (observed in the client code; see ECS_InformationOpr 159):
- Info_ChangeHeadIcon sends CS_InformationOpr{OprType, iParam = item id}.
- E_INFO_OPR_CHANGE_HEADICON (1): HeadIcon, item type HeadIcon (9). The client keeps the item id as text.
- E_INFO_OPR_CHANGE_HEAD_FRAME (24): item type HeadFrame (26) -> BaseInfo.HeadFrame,
  or chat bubble (37) -> BaseInfo.BubbleFrame. The chat screen uses the same operation for both.
- E_INFO_OPR_CHANGE_BATTLE_SCENE (25): item type Scene (27) -> BaseInfo.CurScene.
- E_INFO_OPR_CHANGE_ITEM (30): the player card skin (item type PlayerCard 38) -> BaseInfo.PlayerCard.
- Result codes: E_OPR_SUCCEED = 1, E_OPR_FAILED = 0, E_OPR_ITEM_NOT_ENOUGH = 2.
- Chat messages carry headId, headBoxId and talkBoxId; the server fills them from the sender's
  profile, so nobody can post with another player's cosmetics.

Inferred, not verified in game: how other players see a scene or card skin (only the chat fields are relayed).
"""

from __future__ import annotations

OPR_CHANGE_HEADICON = 1
OPR_CHANGE_HEAD_FRAME = 24
OPR_CHANGE_BATTLE_SCENE = 25
OPR_CHANGE_ITEM = 30
COSMETIC_OPRS = (OPR_CHANGE_HEADICON, OPR_CHANGE_HEAD_FRAME, OPR_CHANGE_BATTLE_SCENE, OPR_CHANGE_ITEM)

TYPE_HEAD_ICON = 9
TYPE_HEAD_FRAME = 26
TYPE_SCENE = 27
TYPE_BUBBLE = 37
TYPE_PLAYER_CARD = 38

RESULT_FAILED = 0
RESULT_SUCCEED = 1
RESULT_ITEM_NOT_ENOUGH = 2

FIELDS = ("head_icon", "head_frame", "bubble_frame", "battle_scene", "player_card")


def default_cosmetics() -> dict[str, int]:
    return {field: 0 for field in FIELDS}


def normalize_cosmetics(raw: object) -> dict[str, int]:
    state = default_cosmetics()
    if isinstance(raw, dict):
        for field in FIELDS:
            state[field] = max(0, int(raw.get(field, 0) or 0))
    return state


def target_field(opr: int, item_type: int) -> str | None:
    """Which cosmetic slot an operation fills for an item type, or None when the pair is invalid."""
    if opr == OPR_CHANGE_HEADICON and item_type == TYPE_HEAD_ICON:
        return "head_icon"
    if opr == OPR_CHANGE_HEAD_FRAME and item_type == TYPE_HEAD_FRAME:
        return "head_frame"
    if opr == OPR_CHANGE_HEAD_FRAME and item_type == TYPE_BUBBLE:
        return "bubble_frame"
    if opr == OPR_CHANGE_BATTLE_SCENE and item_type == TYPE_SCENE:
        return "battle_scene"
    if opr == OPR_CHANGE_ITEM and item_type == TYPE_PLAYER_CARD:
        return "player_card"
    return None


def equip(state: dict[str, int], opr: int, item_id: int, item_type: int, owned: int) -> int:
    """Apply one equip request to the cosmetics state. Returns the result code."""
    if int(item_id) <= 0:
        return RESULT_FAILED
    field = target_field(int(opr), int(item_type))
    if field is None:
        return RESULT_FAILED
    if int(owned) <= 0:
        return RESULT_ITEM_NOT_ENOUGH
    state[field] = int(item_id)
    return RESULT_SUCCEED
