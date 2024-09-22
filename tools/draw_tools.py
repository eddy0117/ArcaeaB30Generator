from tools.utils import textsize


def draw_text_with_edge(
    draw, coord, text, font, fill, e_fill=(0, 0, 0), side="left", ew=1, with_edge=True
):
    """
    param ew: edge width
    """
    if side == "right":
        text_width, _ = textsize(text, font)
        coord = (coord[0] - text_width, coord[1])
    elif side == "bottom":
        _, text_height = textsize(text, font)
        coord = (coord[0], coord[1] - text_height)

    if with_edge:
        for dx, dy in [(ew, ew), (-ew, ew), (ew, -ew), (-ew, -ew)]:
            draw.text((coord[0] + dx, coord[1] + dy), text, font=font, fill=e_fill)
    draw.text((coord[0], coord[1]), text, font=font, fill=fill)


def draw_text_with_shadow(draw, coord, text, font, fill, side="left"):
    if side == "right":
        text_width, _ = textsize(text, font)
        coord = (coord[0] - text_width, coord[1])
    elif side == "bottom":
        _, text_height = textsize(text, font)
        coord = (coord[0], coord[1] - text_height)

    for dx, dy in [(3, 2)]:
        draw.text((coord[0] + dx, coord[1] + dy), text, font=font, fill=(0, 0, 0))
    draw.text((coord[0], coord[1]), text, font=font, fill=fill)
