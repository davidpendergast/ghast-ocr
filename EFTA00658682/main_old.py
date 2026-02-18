import os
import re
import typing

import pygame
import math
import functools


def get_filenames(root, regex=None):
    ret = []
    for name in os.listdir(root):
        filepath = os.path.join(root, name)
        if name.endswith(".png") and (regex is None or re.match(regex, filepath)):
            ret.append(filepath)
    return ret


def smear(img: pygame.Surface):
    yaxis = [0] * img.get_height()
    xaxis = [0] * img.get_width()
    for y in range(img.get_height()):
        for x in range(img.get_width()):
            px = sum(img.get_at((x, y)).rgb) / 3
            xaxis[x] += px / 255
            yaxis[y] += px / 255
    yaxis = [val / img.get_width() for val in yaxis]
    xaxis = [val / img.get_height() for val in xaxis]
    return xaxis, yaxis


def multismear(imgs):
    tot_yaxis = [0] * imgs[0].get_height()
    tot_xaxis = [0] * imgs[0].get_width()
    for img in imgs:
        xaxis, yaxis = smear(img)
        for x in range(len(xaxis)):
            tot_xaxis[x] += xaxis[x]
        for y in range(len(yaxis)):
            tot_yaxis[y] += yaxis[y]
    for x in range(len(tot_xaxis)):
        tot_xaxis[x] /= len(imgs)
    for y in range(len(tot_yaxis)):
        tot_yaxis[y] /= len(imgs)
    return tot_xaxis, tot_yaxis


def find_lines(img, expand=(0, 0, 0, 0), cond=None):
    rects = []
    q = [(0, 0)]
    seen = set()
    seen.add(q[0])
    while len(q) > 0:
        x, y = q.pop(-1)
        for (nx, ny) in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if nx < 0 or nx >= img.get_width() or ny < 0 or ny >= img.get_height():
                continue
            elif (nx, ny) in seen:
                continue
            elif sum(img.get_at((nx, ny)).rbg) // 3 == 255:
                seen.add((nx, ny))
                q.append((nx, ny))
            else:
                seen.add((nx, ny))
                rect, rejects = _fill(img, (nx, ny), seen, lambda px: px < 255)
                if cond is None or cond(rect):
                    rect = [rect[0] - expand[0],
                            rect[1] - expand[1],
                            rect[2] + expand[0] + expand[1],
                            rect[3] + expand[1] + expand[3]]
                    rects.append(rect)
                for rej in rejects:
                    seen.add(rej)
                    q.append(rej)

    def _cmp(a, b):
        if b[1] >= a[1] + a[3]:
            return -1
        elif a[1] >= b[1] + b[3]:
            return 1
        else:
            return -1 if b[0] > a[0] else (0 if b[0] == a[0] else 1)

    res = []
    for r in sorted(rects, key=functools.cmp_to_key(_cmp)):
        res.append([r[0] - expand[0],
                    r[1] - expand[1],
                    r[2] + expand[0] + expand[2],
                    r[3] + expand[1] + expand[3]])
    return res


def _fill(img, start, seen, cond):
    min_x = start[0]
    max_x = start[0]
    min_y = start[1]
    max_y = start[1]
    q = [start]
    rejects = set()
    while len(q) > 0:
        x, y = q.pop(-1)
        for (nx, ny) in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
            if nx < 0 or nx >= img.get_width() or ny < 0 or ny >= img.get_height():
                continue
            elif (nx, ny) in seen:
                continue
            elif not cond(sum(img.get_at((nx, ny)).rbg) // 3):
                rejects.add((nx, ny))
                continue
            else:
                q.append((nx, ny))
                seen.add((nx, ny))
                min_x = min(min_x, nx)
                max_x = max(max_x, nx)
                min_y = min(min_y, ny)
                max_y = max(max_y, ny)

    return [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1], rejects


class Glyph:

    def __init__(self, img: pygame.Surface, src=None, pos=None, page_idx=None, page_filename=None):
        self.img = img
        self.src = src
        self.pos = pos
        self.page_idx = page_idx
        self.page_filename = page_filename
        self._id = self._calc_id()

    def get_id(self):
        return self._id

    def _calc_id(self):
        ret = [0] * (self.img.get_width() * self.img.get_height())
        for y in range(self.img.get_height()):
            for x in range(self.img.get_width()):
                val = sum(self.img.get_at((x, y)).rgb) // 3
                ret[y * self.img.get_width() + x] = val
        return tuple(ret)

    def get_thumbnail(self, icing=(1, 2, 1, 4)):
        if self.src is None or self.pos is None:
            return self.img
        else:
            # TODO this will give inconsistent output if glyph is right against the surface boundary
            # (icing will be sliced off, messing up GlyphMap's expectations)
            x1 = max(0, self.pos[0] - icing[0])
            x2 = min(self.pos[0] + self.pos[2] + icing[2], self.src.get_width())
            y1 = max(0, self.pos[1] - icing[1])
            y2 = min(self.pos[1] + self.pos[3] + icing[3], self.src.get_height())
            return self.src.subsurface((x1, y1, x2 - x1, y2 - y1))

    def __eq__(self, other):
        return self.get_id() == other.get_id()

    def __hash__(self):
        return hash(self.get_id())


def process_pages(filenames, text_area, white_thresh=0.95):
    imgs = [pygame.image.load(filename).subsurface(text_area) for filename in filenames]
    print(f"Loaded {len(imgs)} files.")

    results = []

    print("Finding lines...")
    for idx, img in enumerate(imgs):
        xaxis, yaxis = smear(img)

        smeared = pygame.Surface(img.get_size())
        for y in range(img.get_height()):
            for x in range(img.get_width()):
                if yaxis[y] > white_thresh:
                    val = 255
                else:
                    val = int(yaxis[y] * 255)
                smeared.set_at((x, y), (val, val, val))

        lines = find_lines(smeared, expand=(0, 1, 0, 2), cond=lambda r: r[3] > 5)
        print(f"Found {len(lines)} lines in {filenames[idx]}")

        results.append({
            'img': img,
            'glyphs': [],
            'smeared': smeared,
            'lines': lines
        })

    # print(f"Collecting {len(rects) * len(imgs)} glyphs from {len(imgs)} image(s)...")
    # for idx, img in enumerate(imgs):
    #     for r in rects:
    #         res['glyphs'].append(Glyph(img.subsurface(r), src=img, pos=r, page_idx=idx, page_filename=filenames[idx]))
    #         if len(res['glyphs']) % (len(rects) * len(imgs) // 10) == 0:
    #             print(f"{100 * len(res['glyphs']) / (len(rects) * len(imgs)):.0f}% Done")
    #
    # print("Done.")

    return results


class GlyphMap:

    def __init__(self):
        self.lookup: typing.Dict['Glyph', str] = {}

    def all_unknown(self) -> typing.Generator['Glyph', None, None]:
        for (g, m) in self.lookup.items():
            if m is None:
                yield g

    def save_to_disk(self, filename, icing=(1, 2, 1, 4)):
        max_size = [0, 0]
        for g in self.lookup:
            max_size[0] = max(max_size[0], g.img.get_width())
            max_size[1] = max(max_size[1], g.img.get_height())
        cell_size = (max_size[0] + icing[0] + icing[2] + 1,
                     max_size[1] + icing[1] + icing[3] + 1)
        n_cells = len(self.lookup)
        if n_cells == 0 or max_size == [0, 0]:
            raise ValueError("GlyphMap is empty")
        dims = (round(math.sqrt(n_cells) + 0.5),) * 2

        text = [f"n={n_cells};"
                f"cell_size={cell_size[0]}x{cell_size[1]};"
                f"icing=({icing[0]},{icing[1]},{icing[2]},{icing[3]})"]

        surf = pygame.Surface((dims[0] * cell_size[0], dims[1] * cell_size[1]))
        surf.fill("cyan")
        for i, g in enumerate(self.lookup.keys()):
            gridx = i % dims[0]
            gridy = i // dims[0]
            rect = [gridx * cell_size[0], gridy * cell_size[1], cell_size[0], cell_size[1]]

            if i == 0 or gridy > ((i - 1) // dims[0]):
                text.append("\n")
            text.append(self.lookup[g] if self.lookup[g] is not None else " ")

            thumb = g.get_thumbnail(icing=icing)
            if thumb.get_size() != (g.img.get_width() + icing[0] + icing[2], g.img.get_height() + icing[1] + icing[3]):
                raise ValueError("thumbnail has incorrect size (see comment in Glyph.get_thumbnail()")

            surf.blit(thumb, (rect[0], rect[1]))

            pygame.draw.line(surf, 'red',  # horizontal indicator
                             (rect[0] + icing[0], rect[1] + rect[3] - 1),
                             (rect[0] + icing[0] + g.img.get_width() - 1, rect[1] + rect[3] - 1))

            pygame.draw.line(surf, 'magenta',  # vertical indicator
                             (rect[0] + rect[2] - 1, rect[1] + icing[1]),
                             (rect[0] + rect[2] - 1, rect[1] + icing[1] + g.img.get_height() - 1))

        png_file = filename + ".png"
        pygame.image.save(surf, png_file)
        print(f"Wrote {png_file}")

        txt_file = filename + ".txt"
        with open(txt_file, "w") as f:
            f.write("".join(text) + "\n")
            print(f"Wrote {txt_file}")


    @staticmethod
    def load_from_disk(filename: str):
        png_path = filename + ".png"
        txt_path = filename + ".txt"
        if not os.path.exists(png_path):
            raise ValueError(f"GlyphMap file not found: {png_path}")
        if not os.path.exists(txt_path):
            raise ValueError(f"GlyphMap file not found: {txt_path}")

        surf = pygame.image.load(png_path)

        with open(txt_path, "r") as f:
            text = [line.rstrip() for line in f.readlines() if len(line.rstrip()) > 0]

        match = re.search(r"n=(\d+);cell_size=(\d+)x(\d+);icing=\((\d+),(\d+),(\d+),(\d+)\)", text[0])
        n = int(match.group(1))
        cell_size = (int(match.group(2)), int(match.group(3)))
        icing = (int(match.group(4)), int(match.group(5)), int(match.group(6)), int(match.group(7)))
        dims = (surf.get_width() // cell_size[0], surf.get_height() // cell_size[1])

        glyph_map = GlyphMap()
        for i in range(n):
            gridx = i % dims[0]
            gridy = i // dims[0]
            rect = [gridx * cell_size[0], gridy * cell_size[1], cell_size[0], cell_size[1]]

            min_x = float('inf')
            max_x = -float('inf')
            for x in range(rect[2]):
                if surf.get_at((rect[0] + x, rect[1] + rect[3] - 1)) == (255, 0, 0):
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)

            min_y = float('inf')
            max_y = -float('inf')
            for y in range(rect[3]):
                if surf.get_at((rect[0] + rect[2] - 1, rect[1] + y)) == (255, 0, 255):
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)

            if min_x < 0 or min_y < 0:
                raise ValueError(f"Glyph Map {png_path} is missing size markers at cell: ({gridx}, {gridy})")

            glyph_rect = [rect[0] + min_x, rect[1] + min_y, max_x - min_x + 1, max_y - min_y + 1]
            glyph = Glyph(surf.subsurface(glyph_rect), src=surf, pos=glyph_rect)
            glyph_map.lookup[glyph] = text[gridy + 1][gridx]

        return glyph_map


def process_glyphs(glyphs):
    glyph_map = GlyphMap()
    for glyph in glyphs:
        if glyph not in glyph_map.lookup:
            glyph_map.lookup[glyph] = None
    print(f"Found {len(glyphs)} glyphs ({len(glyph_map.lookup)} unique).")

    if os.path.exists("glyph_map.png") and os.path.exists("glyph_map.txt"):
        stored_glyph_map = GlyphMap.load_from_disk("glyph_map")
        cnt = 0
        for g in stored_glyph_map.lookup:
            if g in glyph_map.lookup:
                cnt += 1
                glyph_map.lookup[g] = stored_glyph_map.lookup[g]
        print(f"Loaded {cnt} glyph meanings from stored glyph map "
              f"(leaving {len(list(glyph_map.all_unknown()))} unknown).")

    if len(list(glyph_map.all_unknown())) > 0:
        do_save = ask_yes_or_no_question(f"Save Glyph Map?")
        if do_save:
            glyph_map.save_to_disk("glyph_map_new")

    return glyph_map


def ask_yes_or_no_question(question):
    print("")
    answer = None
    while answer is None:
        txt = input("  " + question + " (y/n): ")
        if txt == "y" or txt == "Y":
            answer = True
        elif txt == "n" or txt == "N":
            answer = False
    print("")
    return answer


def calc_bounding_box(img, cond=lambda x: x < 245, icing=(0, 2, 0, 2)):
    x_min = float('inf')
    y_min = float('inf')
    x_max = -float('inf')
    y_max = -float('inf')
    for x in range(img.get_width()):
        for y in range(img.get_height()):
            val = sum(img.get_at((x, y)).rgb) // 3
            if cond(val):
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x)
                y_max = max(y_max, y)
    if x_max < 0:
        return None
    else:
        x_min -= icing[0]
        y_min -= icing[1]
        x_max += icing[2]
        y_max += icing[3]
        return [x_min, y_min, x_max - x_min + 1, y_max - y_min + 1]


def calc_guess_img(text, font_size, box_size):
    print(f"Using font size: {font_size}")
    font = pygame.Font("ARIAL.TTF", font_size)
    test_img = font.render(text, True, "black", "white").convert()
    bb = calc_bounding_box(test_img)
    return pygame.transform.smoothscale(safe_subsurf(test_img, bb), box_size)


def safe_subsurf(img, rect, bg_color="white"):
    if rect[0] >= 0 and rect[1] >= 0 and rect[0] + rect[2] <= img.get_width() and rect[1] + rect[3] <= img.get_height():
        return img.subsurface(rect)
    else:
        res = pygame.Surface((rect[2], rect[3]))
        res.fill(bg_color)
        res.blit(img, (-rect[0], -rect[1]))
        return res


def calc_subtraction(sample_img, guess_img, alignment=None, area=None):
    if alignment is not None:
        aligned_guess_img = alignment.apply(guess_img, sample_img.get_size(), area=area)
    else:
        aligned_guess_img = guess_img

    area = [0, 0, sample_img.get_width(), sample_img.get_height()] if area is None else area
    res = pygame.Surface(sample_img.get_size())
    res.fill("black")

    total_error = 0
    n_pix = 0

    for ys in range(area[1], area[1] + area[3]):
        for xs in range(area[0], area[0] + area[2]):
            guess_val = sum(aligned_guess_img.get_at((xs, ys)).rgb) // 3
            sample_val = sum(sample_img.get_at((xs, ys)).rgb) // 3
            error = guess_val - sample_val
            total_error += abs(error)
            n_pix += 1
            if error < 0:
                res.set_at((xs, ys), (abs(error), 0, 0))
            else:
                res.set_at((xs, ys), (0, 0, abs(error)))

    return res, total_error / n_pix


class Alignment:
    """
    Transformation applied to guess image to align it to a sample.
    Stretch is applied first, then offset.
    """

    def __init__(self, offset, stretch):
        self.offset = offset
        self.stretch = stretch

    def __repr__(self):
        return f"{type(self).__name__}(offs={self.offset}, stretch={self.stretch})"

    def apply(self, guess_img, sample_size, area=None):
        res = pygame.Surface(sample_size)
        res.fill("white")
        area = [0, 0, res.get_width(), res.get_height()] if area is None else area
        for ys in range(area[1], area[1] + area[3]):
            for xs in range(area[0], area[0] + area[2]):

                x0 = int((xs - self.offset[0]) / self.stretch[0])
                y0 = int((ys - self.offset[1]) / self.stretch[1])
                x1 = int((xs + 1 - self.offset[0]) / self.stretch[0])
                y1 = int((ys + 1 - self.offset[1]) / self.stretch[1])

                guess_sum = 0
                guess_area = 0
                for yg in range(y0, y1 + 1):
                    for xg in range(x0, x1 + 1):
                        if xg < 0 or yg < 0 or xg >= guess_img.get_width() or yg >= guess_img.get_height():
                            guess_val = 255
                        else:
                            guess_val = sum(guess_img.get_at((xg, yg)).rgb) // 3
                        overlap = 1  # TODO
                        guess_sum += guess_val
                        guess_area += overlap

                guess_val = int(guess_sum / guess_area) if guess_area > 0 else 255
                res.set_at((xs, ys), (guess_val,) * 3)

        return res

    @staticmethod
    def calc_from_bounding_boxes(sample_img, guess_img, white_thresh=245) -> 'Alignment':
        sample_bb = calc_bounding_box(sample_img, cond=lambda rgb: rgb < white_thresh)
        guess_bb = calc_bounding_box(guess_img, cond=lambda rgb: rgb < white_thresh)

        if sample_bb is None or guess_bb is None:
            return Alignment((0, 0), (1, 1))
        else:
            stretch = (sample_bb[2] / guess_bb[2], sample_bb[3] / guess_bb[3])
            offs = (sample_bb[0] - guess_bb[0], sample_bb[1] - guess_bb[1])
            return Alignment(offs, stretch)


class LineGuess:

    def __init__(self,
                 guess_text: str,
                 font_size: int,
                 font_file: str,
                 alignment: Alignment,
                 sample_img: pygame.Surface,
                 antialias=True):

        self.guess_text = guess_text
        self.font_size = font_size
        self.font_file = font_file
        self.alignment = alignment
        self.sample_img = sample_img
        self.antialias = antialias

        self.guess_img = None
        self.sub_img = None
        self.err = None
        self._update()

    def set_alignment(self, align):
        self.alignment = align

    def _update(self):
        self.guess_img = self._calc_guess()
        self.sub_img, self.err = calc_subtraction(self.sample_img, self.guess_img)

    def _calc_guess(self):
        font = pygame.Font(self.font_file, self.font_size)
        raw_img = font.render(self.guess_text, self.antialias, "black", "white")
        if self.alignment == "auto":
            self.alignment = Alignment.calc_from_bounding_boxes(self.sample_img, raw_img)
            print(f"Found auto-alignment: {self.alignment}")
        return self.alignment.apply(raw_img, self.sample_img.get_size())

    def get_preview_img(self):
        w, h = self.sample_img.get_size()
        ret = pygame.Surface((w, h * 3))
        ret.blit(self.sample_img, (0, 0))
        ret.blit(self.guess_img, (0, h))
        ret.blit(self.sub_img, (0, h * 2))
        return ret


if __name__ == "__main__":

    outputs = process_pages(get_filenames("input", regex=r".*[2].png"), [214, 37, 564, 973])

    pygame.init()
    screen = pygame.display.set_mode((600, 600), pygame.RESIZABLE)

    font_file = "ARIAL.TTF"
    font_size = 18
    scale = 3

    def get_sample_img(page_idx, line_idx, scale, smooth=True):
        raw = safe_subsurf(outputs[page_idx]['img'], (outputs[page_idx]["lines"][line_idx]))
        if scale != 1 and smooth:
            return pygame.transform.smoothscale_by(raw, scale)
        elif scale != 1:
            return pygame.transform.scale_by(raw, scale)
        else:
            return raw


    calibration_line = LineGuess(
        "50qQASwN5ycYLKev5HH510Go28Os+LNPsniSSLT0N5OWUH5j8sa/zbHtWjoqFRweyJ5rxudH9pgS",
        font_size, font_file, 'auto',
        get_sample_img(0, 25, scale),
    )

    guesses = [
        calibration_line,
        LineGuess("Disposition: inline; filename=image001.jpg Content-Type: image/jpg; x-unix-mode–66; name=\"image001.jpg\"",
                  font_size, font_file, 'auto', # calibration_line.alignment,
                  get_sample_img(0, 1, scale)),
        LineGuess("z1Rby2W3E5uYBAekpkGz884p8GqWE0qxRX1o8jdESZST9ADXP6hqE2tNPo3h4RHGY7u/KBobYd1U",
                  font_size, font_file, 'auto',  # calibration_line.alignment,
                  get_sample_img(0, 30, scale))
    ]

    # sample_text = ("Disposition: inline; filename=image001.jpg Content-Type: "
    #                "image/jpg; x-unix-mode–66; name=\"image001.jpg\"")
    # sample_text = "50qQASwN5ycYLKev5HH510Go28Os+LNPsniSSLT0N5OWUH5j8sa/zbHtWjoqFRweyJ5rxudH9pgS"
    # sample_line_idx = 25
    # sample_img = outputs[0]['img'].subsurface(outputs[0]["lines"][sample_line_idx])
    #
    # sample_bb = calc_bounding_box(sample_img)
    # sample_img_scaled = pygame.transform.scale_by(safe_subsurf(sample_img, sample_bb), (scale, scale))
    # box = sample_img_scaled.get_size()
    #
    # alignment = Alignment((0, 0), (1, 1))
    # guess_img = calc_guess_img(sample_text, font_size, box)
    # sub_img, err = calc_subtraction(sample_img_scaled, guess_img, alignment)

    page_idx = 0
    mode_idx = 0
    modes = ["debug", "normal", "rects", "rects_filled", "smeared"]

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                raise SystemExit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    raise SystemExit()
                elif e.key == pygame.K_SPACE:
                    mode_idx = (mode_idx + 1) % len(modes)
                elif e.key == pygame.K_LEFT:
                    page_idx = (page_idx - 1) % len(outputs)
                elif e.key == pygame.K_RIGHT:
                    page_idx = (page_idx + 1) % len(outputs)
                elif e.key == pygame.K_UP or e.key == pygame.K_DOWN:
                    direct = 1 if e.key == pygame.K_UP else -1
                    font_size += direct

                    # guess_img = calc_guess_img(sample_text, font_size, box)
                    # sub_img, err = calc_subtraction(sample_img_scaled, guess_img, alignment)
                    # print(f"Error measure: {err}")

        screen.fill("black")

        mode = modes[mode_idx]
        if mode == 'normal':
            screen.blit(outputs[page_idx]["img"], (0, 0))
        elif mode == 'rects' or mode == 'rects_filled':
            screen.blit(outputs[page_idx]["img"], (0, 0))
            colors = ["red", "blue", "green", "magenta", "purple"]
            for r in outputs[page_idx]["lines"]:
                clr = colors[r[3] % len(colors)]
                pygame.draw.rect(screen, clr, r, width=0 if mode == 'rects_filled' else 1)
        elif mode == 'smeared':
            screen.blit(outputs[page_idx]["smeared"], (0, 0))
        elif mode == 'debug':
            y = 0
            previews = [g.get_preview_img() for g in guesses]
            for prev in previews:
                screen.blit(prev, (0, y))
                y += prev.get_height()

        elapsed_time_ms = pygame.time.get_ticks()
        i = elapsed_time_ms // 100

        scr_w, scr_h = screen.get_size()

        pygame.display.flip()