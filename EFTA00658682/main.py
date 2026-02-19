import pygame
import warp
import typing
import cv2
from matching import *





MOUSE_XY = (0, 0)

if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((640, 480), pygame.RESIZABLE)
    clock = pygame.Clock()

    current_scale = 3
    sample = pygame.image.load("test_input/sample_line.png")#.subsurface([0, 0, 64*3, 14])
    sample = pygame.transform.scale_by(sample, current_scale)

    font = pygame.Font("ARIAL.TTF", 11)

    normal_chars = "zby2ABCDEFGHJKLMNOPQSTUVXYZabcdefghkmnopqrstuvwxyz234567890+_"
    thin_chars = "i1lI/;jf"

    all_templates = [Template.from_font(font, c) for c in set(normal_chars)]
    all_templates.extend([Template.from_font(font, c, expand_x=(1, 1)) for c in set(thin_chars)])
    all_templates.append(Template.from_font(font, "W", expand_x=(-1, -1)))
    all_templates.append(Template.from_font(font, "R", expand_x=(0, -1)))
    all_templates.sort(key=lambda t: t.surf.get_width(), reverse=True)

    current_template = Template.from_font(font, "z", scale=1)
    template_idx = 0

    print(f"template size: {current_template.surf.get_size()}")
    print(f"scaled size: ({current_template.surf.get_width() * current_scale}, {current_template.surf.get_height() * current_scale})")

    aligned = AlignedTemplate(current_template, Alignment(MOUSE_XY, (current_scale,) * 2))
    img, rect = aligned.render()
    corners = aligned.get_corners()
    print(f"aligned img size: {img.get_size()}")
    print(f"aligned size: {rect}")
    print(f"aligned corners: {corners}")

    smooth_modes = (cv2.INTER_NEAREST, cv2.INTER_LINEAR, cv2.INTER_CUBIC)
    smooth_idx = 1

    info_font = pygame.Font("ARIAL.TTF", 16)

    search = SearchProcess(sample, all_templates, (current_scale,) * 2)

    while True:
        for e in pygame.event.get():
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    raise SystemExit
                elif e.key == pygame.K_s:
                    smooth_idx = (smooth_idx + 1) % len(smooth_modes)
                    search = SearchProcess(sample, all_templates, (current_scale,) * 2, smooth=smooth_modes[smooth_idx])
                elif e.key == pygame.K_UP:
                    current_scale += 0.125
                elif e.key == pygame.K_DOWN:
                    current_scale -= 0.125
                elif e.key == pygame.K_RIGHT:
                    template_idx = (template_idx + 1) % len(all_templates)
                elif e.key == pygame.K_LEFT:
                    template_idx = (template_idx - 1) % len(all_templates)
                elif e.key == pygame.K_RETURN:
                    search = SearchProcess(sample, all_templates, (current_scale,)*2, smooth=smooth_modes[smooth_idx])
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

        if search is not None:
            if not search.is_done():
                search.search(50)

            for m in search.matches:
                clr = (int(m.err_val / search.err_thresh * 255), 0, 0)
                pygame.draw.rect(screen, clr, m.rect, width=1)
                # letter_img = info_font.render(m.guess.template.identifier, antialias=True, color=clr)
                # err_val_img = info_font.render(f"{int(m.err_val)}", antialias=True, color=clr)
                # screen.blit(letter_img, (m.rect[0] + 4, m.rect[1] + 4))
                # screen.blit(err_val_img, (m.rect[0] + 4, m.rect[1] + m.rect[3] - err_val_img.get_height() - 4))

                screen.blit(m.guess_img, (m.rect[0], m.rect[1] + sample.get_height()))
                screen.blit(m.err_img, (m.rect[0], m.rect[1] + sample.get_height() * 2))

                bar_height = int(320 * m.err_val / search.err_thresh)
                pygame.draw.rect(screen, clr, [m.rect[0] + 2, sample.get_height() * 3, m.rect[2] - 4, bar_height])

            pygame.draw.line(screen, "red", (0, sample.get_height() * 3 + 320), (sample.get_width(), sample.get_height() * 3 + 320))

            if not search.is_done():
                pygame.draw.rect(screen, "black", search.last_search.rect, width=1)
                letter_img = info_font.render(search.last_search.guess.template.identifier, antialias=True, color="black")
                err_val_img = info_font.render(f"{int(search.last_search.err_val)}", antialias=True, color="black")
                screen.blit(letter_img, (search.last_search.rect[0] + 4, search.last_search.rect[1] + 4))
                screen.blit(err_val_img, (search.last_search.rect[0] + 4, search.last_search.rect[1] +search.last_search. rect[3] - err_val_img.get_height() - 4))

        elif MOUSE_XY is not None and current_template is not None:
            current_template = all_templates[template_idx]
            aligned = AlignedTemplate(current_template, Alignment(MOUSE_XY, (current_scale,) * 2))
            img, frect = aligned.render(smooth=smooth_modes[smooth_idx])
            corners = aligned.get_corners()
            rect = pygame.Rect(int(frect.x), int(frect.y), img.get_width(), img.get_height())
            screen.blit(img, rect)

            if warp.rect_contains(sample.get_rect(), rect):
                err_val, err_img = warp.calc_error(sample, img, rect)
                screen.blit(err_img, rect)

                text_img = info_font.render(f"error={err_val:.1f}", antialias=True, color="black")
                screen.blit(text_img, (rect[0], rect[1] + rect[3] + 8))

            # img2 = pygame.transform.scale_by(current_template.surf, current_scale)
            # screen.blit(img2, [rect[0] + rect[2] + 16, rect[1]])
            # for i in range(0, 4):
            #     pygame.draw.line(screen, "red", corners[i], corners[(i + 1) % 4])

        pygame.display.flip()
        clock.tick(60)

