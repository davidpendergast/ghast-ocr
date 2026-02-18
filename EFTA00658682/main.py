import pygame
import warp
import typing


class Alignment:

    def __init__(self, xy, scale=(1, 1)):
        self.xy = xy
        self.scale = scale


class Template:

    def __init__(self, surf: pygame.Surface, identifier=None):
        self.surf = surf
        self.identifier = identifier

    @staticmethod
    def from_font(font: pygame.Font, text: str, antialias=True, color="black", bg_color="white", scale=1):
        img = font.render(text, antialias=antialias, color=color, bgcolor=bg_color).convert_alpha()
        box = warp.calc_bounding_box(img)
        img = img.subsurface([box[0], 0, box[2], img.get_height()])  # preserve height to make vertical alignment easier
        if scale != 1:
            img = pygame.transform.scale_by(img, scale)
        return Template(img, text)


class AlignedTemplate:

    def __init__(self, template: Template, alignment: Alignment):
        self.template = template
        self.alignment = alignment

    def get_corners(self):
        cx = self.alignment.xy[0]
        cy = self.alignment.xy[1]
        width = self.alignment.scale[0] * self.template.surf.get_width()
        height = self.alignment.scale[1] * self.template.surf.get_height()
        return [
            (cx - width / 2, cy - height / 2),
            (cx + width / 2, cy - height / 2),
            (cx + width / 2, cy + height / 2),
            (cx - width / 2, cy + height / 2)
        ]

    def calc_error(self, sample):
        pass

    def render(self, smooth=True) -> typing.Tuple[pygame.Surface, pygame.Rect]:
        return warp.warp(self.template.surf, self.get_corners(), smooth=smooth)


MOUSE_XY = (0, 0)

if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((640, 480), pygame.RESIZABLE)
    clock = pygame.Clock()

    sample = pygame.image.load("test_input/sample_line.png").subsurface([0, 0, 54, 14])
    sample = pygame.transform.scale_by(sample, 8)

    font = pygame.Font("ARIAL.TTF", 11)

    all_chars = "z1Rby2W"
    all_templates = [Template.from_font(font, c, scale=1) for c in all_chars]

    current_template = Template.from_font(font, "z", scale=1)
    current_scale = 8

    print(f"template size: {current_template.surf.get_size()}")
    print(f"scaled size: ({current_template.surf.get_width() * current_scale}, {current_template.surf.get_height() * current_scale})")

    aligned = AlignedTemplate(current_template, Alignment(MOUSE_XY, (current_scale,) * 2))
    img, rect = aligned.render()
    corners = aligned.get_corners()
    print(f"aligned img size: {img.get_size()}")
    print(f"aligned size: {rect}")
    print(f"aligned corners: {corners}")

    while True:
        for e in pygame.event.get():
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    raise SystemExit
                elif e.key == pygame.K_UP:
                    current_scale += 0.1
                elif e.key == pygame.K_DOWN:
                    current_scale -= 0.1
                elif e.key == pygame.K_SPACE:
                    pygame.image.save(screen, "screenshot.png")
            elif e.type == pygame.QUIT:
                raise SystemExit
            elif e.type == pygame.MOUSEMOTION:
                MOUSE_XY = e.pos
            elif e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 1:
                    print(current_scale)

        screen.fill("plum")
        screen.blit(sample, (0, 0))

        if MOUSE_XY is not None and current_template is not None:
            aligned = AlignedTemplate(current_template, Alignment(MOUSE_XY, (current_scale,) * 2))
            img, rect = aligned.render()
            corners = aligned.get_corners()
            screen.blit(img, rect)

            img2 = pygame.transform.scale_by(current_template.surf, current_scale)
            screen.blit(img2, [rect[0] + rect[2] + 16, rect[1]])
            for i in range(0, 4):
                pygame.draw.line(screen, "red", corners[i], corners[(i + 1) % 4])


        pygame.display.flip()
        clock.tick(60)

