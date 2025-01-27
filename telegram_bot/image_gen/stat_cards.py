from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
import logging

logger = logging.getLogger(__name__)

TICKERBIT_FONT_PATH = os.path.abspath("fonts/Tickerbit-regular.otf")


@dataclass
class StatCardData:
    name: str
    avatar_path: str | None
    stat_value: int
    stat_name: str
    subtitle: str | None = None

@dataclass
class PlayerStatCardData:
    name: str
    avatar_path: str | None
    avatar_url: str | None
    stats: dict[str, float | int]
    decorative_stat_value: int
    decorative_stat_name: str
    subtitle: str | None

def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    start_x: int,
    start_y: int,
    line_spacing: int,
    fill=(255, 255, 255, 255),
):
    """
    Wrap `text` so it doesn't exceed `max_width`.
    Draw each wrapped line starting at (start_x, start_y),
    moving down by line_spacing each time.
    """
    # Use textwrap to break the text into a list of lines
    wrapped_lines = []
    # You can tune width=XX or use a function to guess how many chars fit in max_width.
    # Or measure each chunk to see if it fits.
    # For simplicity, let's do an approximate wrap with textwrap.
    # We'll do a big width=999 and then manually measure each line.
    candidate_lines = textwrap.wrap(text, width=999)

    for line in candidate_lines:
        # We'll keep splitting the line until it fits within max_width
        current_line = line
        while True:
            bbox = font.getbbox(current_line)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if w <= max_width:
                # Fits in the available width
                wrapped_lines.append(current_line)
                break
            else:
                # Find a break point
                # We'll manually reduce the line until it fits
                # (A naive approach is to reduce by one word at a time)
                # This approach is simplistic but works for demonstration.
                # A more robust approach would do binary search or measure words.
                last_space = current_line.rfind(" ")
                if last_space == -1:
                    # No space found, force break (long single word)
                    # We'll just take the chunk that fits, if possible
                    # or forcibly break the word. This is more advanced logic.
                    # For demonstration, let's just forcibly break
                    current_line = current_line[:-1]  # remove last char
                    continue
                else:
                    # remove last word
                    current_line = current_line[:last_space]

    # Now draw each line
    y = start_y
    for line in wrapped_lines:
        draw.text((start_x, y), line, font=font, fill=fill)
        bbox = font.getbbox(line)
        line_height = bbox[3] - bbox[1]
        y += line_height + line_spacing

    # Return how far down we ended, in case you need to continue drawing below
    return y


def draw_text_with_stroke(
    draw: ImageDraw.Draw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 255),
    stroke_width: int = 1,
):
    """Draw text with a stroke (outline)."""
    x, y = xy
    # Draw stroke by offsetting text around original pos
    for offset_x in range(-stroke_width, stroke_width + 1):
        for offset_y in range(-stroke_width, stroke_width + 1):
            draw.text((x + offset_x, y + offset_y), text, font=font, fill=stroke_fill)
    # Draw main text on top
    draw.text((x, y), text, font=font, fill=fill)


def create_stat_card(
    data: StatCardData, width: int = 400, height: int = 200
) -> Image.Image:
    """Create a stat card for a player."""

    # Create base card with alpha channel if you want semi-transparency
    # or just use 'RGB' with a black fill if you want it fully opaque.
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    # Rounded black rectangle (slightly lighter black for subtle contrast)
    draw.rounded_rectangle(
        [(0, 0), (width, height)],
        radius=20,
        fill=(30, 30, 30, 220),  # Adjust alpha or remove for fully opaque
    )

    # Attempt to load your Tickerbit font
    try:
        name_font = ImageFont.truetype(TICKERBIT_FONT_PATH, 24)
        stat_font = ImageFont.truetype(TICKERBIT_FONT_PATH, 32)
        subtitle_font = ImageFont.load_default(16)
    except OSError as e:
        logger.error(f"Font not found: {e}")
        # Fallback if not found
        logger.warning("Font not found, using default font.")
        name_font = ImageFont.load_default()
        stat_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    # Avatar
    avatar_size = 80
    avatar_x = 20
    avatar_y = (height - avatar_size) // 2

    def create_circular_mask(size):
        mask = Image.new('L', (size, size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, size-1, size-1), fill=255)
        return mask

    # Create circular mask
    mask = create_circular_mask(avatar_size)

    if data.avatar_path and os.path.exists(data.avatar_path):
        try:
            # Load and resize avatar
            avatar = Image.open(data.avatar_path)
            avatar = avatar.convert('RGBA')
            
            # Calculate resize dimensions to maintain aspect ratio
            ratio = min(avatar_size / avatar.width, avatar_size / avatar.height)
            new_size = (int(avatar.width * ratio), int(avatar.height * ratio))
            
            # Resize maintaining aspect ratio
            avatar = avatar.resize(new_size, Image.Resampling.LANCZOS)
            
            # Create a blank square image
            square_avatar = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
            
            # Calculate position to center the resized image
            paste_x = (avatar_size - new_size[0]) // 2
            paste_y = (avatar_size - new_size[1]) // 2
            
            # Paste the resized image onto the square canvas
            square_avatar.paste(avatar, (paste_x, paste_y))
            
            # Apply circular mask
            square_avatar.putalpha(mask)
            
            # Paste the circular avatar
            card.paste(square_avatar, (avatar_x, avatar_y), square_avatar)
        except Exception as e:
            # If avatar loading fails, draw placeholder circle
            draw.ellipse(
                [avatar_x, avatar_y, avatar_x + avatar_size - 1, avatar_y + avatar_size - 1],
                fill=(128, 128, 128, 180),
            )
    else:
        # try
        try:
            # use avatar_url/telegram photo
            pass
        except Exception:
            # Draw placeholder circle
            draw.ellipse(
                [avatar_x, avatar_y, avatar_x + avatar_size - 1, avatar_y + avatar_size - 1],
                fill=(128, 128, 128, 180),
            )

    # Text positions
    text_start_x = avatar_x + avatar_size + 20
    text_y = 30

    # White text with optional stroke
    text_color = (255, 255, 255, 255)
    stroke_color = (0, 0, 0, 255)

    # Name
    draw_text_with_stroke(
        draw,
        (text_start_x, text_y),
        data.name,
        font=name_font,
        fill=text_color,
        stroke_fill=stroke_color,
        stroke_width=2,
    )

    # Stats
    stat_text = f"{data.stat_value} {data.stat_name}"
    stat_y = height // 2 - 10
    draw_text_with_stroke(
        draw,
        (text_start_x, stat_y),
        stat_text,
        font=stat_font,
        fill=text_color,
        stroke_fill=stroke_color,
        stroke_width=2,
    )

    # Subtitle
    if data.subtitle:
        draw_text_with_stroke(
            draw,
            (text_start_x, stat_y + 40),
            data.subtitle,
            font=subtitle_font,
            fill=(200, 200, 200, 255),
            stroke_fill=(0, 0, 0, 255),
            stroke_width=1,
        )

    return card


def create_leaderboard_image(
    stat_cards: list[StatCardData],
    title: str,
    width: int = 400,
    card_height: int = 200,
    spacing: int = 20,
) -> Image.Image:
    """Create a leaderboard image from multiple stat cards."""

    title_height = 60
    total_height = (
        title_height
        + (len(stat_cards) * card_height)
        + ((len(stat_cards) - 1) * spacing)
        + spacing * 2  # top and bottom padding
    )
    total_width = width + 2 * spacing

    # Create black background (RGB or RGBA)
    # If you want the entire background to be black, just do:
    image = Image.new("RGB", (total_width, total_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Load title font
    # choose font size for title based on length; or wrap text if needed
    font_size = 24 if len(title) < 20 else 18
    try:
        title_font = ImageFont.truetype(TICKERBIT_FONT_PATH, font_size)
    except OSError:
        title_font = ImageFont.load_default()

    # Title with stroke or just center it plainly
    title_x = total_width // 2
    title_y = spacing
    title_color = (255, 255, 255, 255)

    draw.text(
        (title_x, title_y),
        title,
        font=title_font,
        fill=title_color,
        anchor="mt",  # Middle-top
    )

    # Generate and paste cards
    y_offset = title_height + spacing
    for card_data in stat_cards:
        card = create_stat_card(card_data, width=width, height=card_height)
        (
        image.alpha_composite(card, (spacing, y_offset))
            if image.mode == "RGBA"
            else image.paste(card, (spacing, y_offset), card)
        )
        y_offset += card_height + spacing

    return image


def create_player_stat_card(
    data: PlayerStatCardData,
    width: int = 450,
    height: int = 280,
) -> Image.Image:
    """
    Create a more detailed stat card, preserving the old implementation.
    This version shows multiple stats and includes a decorative stat/badge
    in the top-right corner.
    """
    # 1. Create the base card (RGBA if you want semi-transparency)
    card = Image.new("RGBA", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(card)

    # 2. Draw the background rectangle
    # draw.rounded_rectangle(
    #     [(0, 0), (width, height)],
    #     radius=20,
    #     fill=(30, 30, 30, 220),  # a slightly transparent dark background
    # )

    # 3. Load fonts
    try:
        name_font = ImageFont.truetype(TICKERBIT_FONT_PATH, 24)
        stat_font = ImageFont.truetype(TICKERBIT_FONT_PATH, 20)
        badge_font = ImageFont.truetype(TICKERBIT_FONT_PATH, 14)
        subtitle_font = ImageFont.load_default(12)
    except OSError:
        # fallback to default if Tickerbit isn't found
        name_font = ImageFont.load_default()
        stat_font = ImageFont.load_default()
        badge_font = ImageFont.load_default()

    # 4. Place the avatar on the left side
    avatar_size = 80
    avatar_x = 20
    avatar_y = 60

    def create_circular_mask(size):
        mask = Image.new('L', (size, size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, size-1, size-1), fill=255)
        return mask

    # Create circular mask
    mask = create_circular_mask(avatar_size)

    if data.avatar_path and os.path.exists(data.avatar_path):
        try:
            # Load and resize avatar
            avatar = Image.open(data.avatar_path)
            avatar = avatar.convert('RGBA')
            
            # Calculate resize dimensions to maintain aspect ratio
            ratio = min(avatar_size / avatar.width, avatar_size / avatar.height)
            new_size = (int(avatar.width * ratio), int(avatar.height * ratio))
            
            # Resize maintaining aspect ratio
            avatar = avatar.resize(new_size, Image.Resampling.LANCZOS)
            
            # Create a blank square image
            square_avatar = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
            
            # Calculate position to center the resized image
            paste_x = (avatar_size - new_size[0]) // 2
            paste_y = (avatar_size - new_size[1]) // 2
            
            # Paste the resized image onto the square canvas
            square_avatar.paste(avatar, (paste_x, paste_y))
            
            # Apply circular mask
            square_avatar.putalpha(mask)
            
            # Paste the circular avatar
            card.paste(square_avatar, (avatar_x, avatar_y), square_avatar)
        except Exception as e:
            # If avatar loading fails, draw placeholder circle
            draw.ellipse(
                [avatar_x, avatar_y, avatar_x + avatar_size - 1, avatar_y + avatar_size - 1],
                fill=(128, 128, 128, 180),
            )
    else:
        # try
        try:
            # use avatar_url/telegram photo
            pass
        except Exception:
            # Draw placeholder circle
            draw.ellipse(
                [avatar_x, avatar_y, avatar_x + avatar_size - 1, avatar_y + avatar_size - 1],
                fill=(128, 128, 128, 180),
            )

    # 5. Define a helper to draw text with a stroke (outline)
    def draw_text_with_stroke(
        xy: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: tuple[int, int, int, int],
        stroke_fill: tuple[int, int, int, int] = (0, 0, 0, 255),
        stroke_width: int = 1,
    ):
        x, y = xy
        for offset_x in range(-stroke_width, stroke_width + 1):
            for offset_y in range(-stroke_width, stroke_width + 1):
                draw.text((x + offset_x, y + offset_y), text, font=font, fill=stroke_fill)
        draw.text((x, y), text, font=font, fill=fill)

    # 6. Draw the player's name near the top
    text_color = (255, 255, 255, 255)
    stroke_color = (0, 0, 0, 255)

    text_start_x = avatar_x + avatar_size + 20
    text_y = 40

    draw_text_with_stroke(
        (text_start_x, text_y),
        data.name,
        font=name_font,
        fill=text_color,
        stroke_fill=stroke_color,
        stroke_width=2,
    )

    # Move down a bit for stats
    text_y += 40

    # 7. Draw the stats (multiple lines)
    # Convert each stat into a formatted string: "• label: value"
    # Example: "• Games Played: 25"
    stats_lines = []
    for label, value in data.stats.items():
        stats_lines.append(f"• {label}: {value}")

    # We'll draw each line with a small line spacing
    line_spacing = 5

    for line in stats_lines:
        draw_text_with_stroke(
            (text_start_x, text_y),
            line,
            font=stat_font,
            fill=text_color,
            stroke_fill=stroke_color,
            stroke_width=1,
        )
        bbox = stat_font.getbbox(line)
        line_height = bbox[3] - bbox[1]
        text_y += line_height + line_spacing

    # 8. Draw an optional subtitle below the stats
    if data.subtitle:
        text_y += 10
        draw_wrapped_text(
            draw,
            data.subtitle,
            font=subtitle_font,
            max_width=width/2,
            start_x=text_start_x,
            start_y=text_y,
            line_spacing=line_spacing,
            fill=(200, 200, 200, 255),
        )

    # 9. Draw the decorative stat text in the top-right corner
    # Center the decorative stat text
    badge_text = str(data.decorative_stat_value)
    bbox = badge_font.getbbox(badge_text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Position in top-right corner with some padding
    text_x = width - text_width - 40
    text_y = 60
    
    draw_text_with_stroke(
        (text_x, text_y),
        badge_text,
        font=badge_font,
        fill=(255, 215, 0, 255),  # Gold color
        stroke_fill=(0, 0, 0, 255),
        stroke_width=2,
    )

    # Draw the decorative stat name under the stat value
    bbox = badge_font.getbbox(data.decorative_stat_name)
    label_width = bbox[2] - bbox[0]
    label_x = text_x + (text_width - label_width) // 2
    label_y = text_y + text_height + 4
    
    draw.text(
        (label_x, label_y),
        data.decorative_stat_name,
        font=badge_font,
        fill=(255, 255, 255, 255),
    )

    return card