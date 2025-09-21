from typing import Dict, Any, List, Tuple


def parse_data_args(data: Dict[str, Any], args: List[str]) -> List[Any]:
    missing_args = []
    values = []

    for arg in args:
        if arg not in data:
            missing_args.append(arg)
        else:
            values.append(data[arg])

    if missing_args != []:
        raise Exception(f'missing args: {", ".join(missing_args)}')

    return values


def parse_object(obj) -> Any:
    return obj.__dict__


def parse_object_list(objects) -> List[Any]:
    return [obj.__dict__ for obj in list(objects)]


def parse_game_state(state) -> Dict[str, Any]:
    # New tuple: (hands, top_card, current_player_id, current_color, pending_draw_count, pending_for_player_id)
    if len(state) >= 6:
        hands, top_card, current_player_id, current_color, pending_draw_count, pending_for_player_id = state
    elif len(state) == 4:
        hands, top_card, current_player_id, current_color = state
        pending_draw_count = 0
        pending_for_player_id = None
    elif len(state) == 3:
        hands, top_card, current_player_id = state
        current_color = None
        pending_draw_count = 0
        pending_for_player_id = None
    else:
        hands, top_card = state
        current_player_id = None
        current_color = None
        pending_draw_count = 0
        pending_for_player_id = None
    parsed_hands = {key.id: parse_object_list(value) for key, value in hands.items()}
    parsed_top_card = parse_object(top_card)
    result = {
        'hands': parsed_hands,
        'top_card': parsed_top_card
    }
    if current_player_id is not None:
        result['current_player_id'] = current_player_id
    if current_color is not None:
        result['current_color'] = current_color
    result['pending_draw_count'] = pending_draw_count
    result['pending_for_player_id'] = pending_for_player_id
    return result
