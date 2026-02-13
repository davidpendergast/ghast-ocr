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

        lines = find_lines(smeared, expand=(0, 0, 0, 1), cond=lambda r: r[3] > 5)
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


if __name__ == "__main__":

    outputs = process_pages(get_filenames("input", regex=r".*[234].png"), [214, 37, 564, 973])

    # glyph_map = process_glyphs(output['glyphs'])

    # n_unknown = len(list(glyph_map.all_unknown()))
    # if n_unknown > 0:
    #     print(f"Skipping outputs, since we have {n_unknown} unknown glyphs.")
    # else:
    #     output_files = {}
    #     for idx, g in enumerate(output['glyphs']):
    #         file_id = os.path.split(os.path.split(g.page_filename)[0])[1]
    #         out_filename = f"{file_id}_plaintext.txt"
    #         if out_filename not in output_files:
    #             output_files[out_filename] = []
    #         if idx > 0 and (g.page_idx > output['glyphs'][idx-1].page_idx or g.pos[1] > output['glyphs'][idx-1].pos[1]):
    #             output_files[out_filename].append("\n")
    #         output_files[out_filename].append(glyph_map.lookup[g])
    #
    #     for fname, f_chars in output_files.items():
    #         f_text = "".join(f_chars)
    #         f_lines = f_text.split("\n")
    #         f_lines = [line.rstrip() for line in f_lines]
    #         f_path = os.path.join("out_plaintext", fname)
    #         with open(f_path, "w") as f:
    #             f.writelines([(line + "\n") for line in f_lines])
    #         print(f"Wrote: {f_path}")

    pygame.init()
    screen = pygame.display.set_mode((600, 600), pygame.RESIZABLE)
    page_idx = 0
    mode_idx = 0
    modes = ["normal", "rects", "rects_filled", "smeared"]

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

        elapsed_time_ms = pygame.time.get_ticks()
        i = elapsed_time_ms // 100

        scr_w, scr_h = screen.get_size()

        pygame.display.flip()