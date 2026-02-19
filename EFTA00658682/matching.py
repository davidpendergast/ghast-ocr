import pygame
import warp
import typing
import math
import cv2


class Alignment:

    def __init__(self, xy, scale=(1, 1)):
        self.xy = xy
        self.scale = scale


class Template:

    def __init__(self, surf: pygame.Surface, identifier=None):
        self.surf = surf
        self.identifier = identifier

    @staticmethod
    def from_font(font: pygame.Font, text: str, antialias=True, color="black", bg_color="white", scale=1, expand_x=(0, 0)):
        img = font.render(text, antialias=antialias, color=color, bgcolor=bg_color).convert_alpha()
        box = warp.calc_bounding_box(img)

        # preserve height to make vertical alignment easier
        img = warp.safe_subsurf(img, [box[0] - expand_x[0], 0, box[2] + (expand_x[0] + expand_x[1]), img.get_height()]).convert_alpha()
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

    def render(self, smooth=cv2.INTER_NEAREST) -> typing.Tuple[pygame.Surface, pygame.FRect]:
        return warp.warp(self.template.surf, self.get_corners(), smooth=smooth)


class Match:

    def __init__(self, err_val: float, guess: AlignedTemplate, guess_img: pygame.Surface, err_img: pygame.Surface, rect):
        self.err_val = err_val
        self.guess = guess
        self.guess_img = guess_img
        self.err_img = err_img
        self.rect = rect


class SearchProcess:

    def _all_aligned_templates(self):
        for t in self.templates:
            w, h = t.surf.get_size()
            ws = math.ceil(w * self.scale[0])
            hs = math.ceil(h * self.scale[1])

            for x in range(self.search_rect[0], self.search_rect[0] + self.search_rect[2] - ws):
                for y in range(self.search_rect[1], self.search_rect[1] + self.search_rect[3] - hs):
                    yield AlignedTemplate(t, Alignment((x + ws / 2, y + hs / 2), scale=self.scale))

    def __init__(self, sample: pygame.Surface, templates: typing.List[Template], scale, smooth=cv2.INTER_NEAREST, search_rect=None, err_thresh=3700):
        self.sample = sample
        self.search_rect = sample.get_rect() if search_rect is None else search_rect
        self.templates = templates
        self.scale = scale
        self.smooth = smooth

        self.matches = []
        self.err_thresh = err_thresh
        self.last_search = None
        self._generator = self._all_aligned_templates()
        self._done = False

    def _filter_and_merge_new_matches(self, new_matches):
        all_matches_sorted = self.matches + new_matches
        all_matches_sorted.sort(key=lambda m: m.err_val)

        accepted = []

        def _calc_overlap(_x1, _x2, o1, o2):
            if (_x2 - _x1) == 0 or (o2 - o1) == 0:
                return 0
            elif o1 <= _x1 and _x2 <= o2:
                return 1
            elif _x1 <= o1 and o2 <= _x2:
                return ((o1 - _x1) + (_x2 - o2)) / (_x2 - _x1)
            elif _x1 <= o1 <= _x2 <= o2:
                return (_x2 - o1) / (_x2 - _x1)
            elif o1 <= _x1 <= o2 <= _x2:
                return (o2 - _x1) / (_x2 - _x1)
            else:
                return 0

        def _get_overlapping(_x1, _x2):
            # TODO binary search
            for m2 in accepted:
                if m2.rect[0] >= _x2:
                    continue
                elif m2.rect[0] + m2.rect[2] <= _x1:
                    continue
                else:
                    yield (m2,
                           _calc_overlap(_x1, _x2, m2.rect[0], m2.rect[0] + m2.rect[2]),
                           _calc_overlap(m2.rect[0], m2.rect[0] + m2.rect[2], _x1, _x2))

        for m in all_matches_sorted:
            rect = m.rect
            x1 = rect[0]
            x2 = rect[0] + rect[2]
            skip = False
            for overlapping_m in _get_overlapping(x1, x2):
                m2, m_into_m2, m2_into_m = overlapping_m
                if max(m_into_m2, m2_into_m) > 0.5 or min(m_into_m2, m2_into_m) > 0.3:
                    skip = True
                    break
            if not skip:
                accepted.append(m)

        accepted.sort(key=lambda m: m.rect[0])  # sort by x
        self.matches = accepted


    def search(self, n) -> bool:
        new_matches = []
        for _ in range(n):
            try:
                guess = next(self._generator)
            except StopIteration:
                self._done = True
                self._filter_and_merge_new_matches(new_matches)
                return True

            guess_rend, rect = guess.render(smooth=self.smooth)
            rect = pygame.Rect(int(rect[0]), int(rect[1]), guess_rend.get_width(), guess_rend.get_height())
            err_val, err_img = warp.calc_error(self.sample, guess_rend, rect)

            self.last_search = Match(err_val, guess, guess_rend, err_img, rect)
            if err_val < self.err_thresh:
                new_matches.append(self.last_search)

        self._filter_and_merge_new_matches(new_matches)
        return False

    def is_done(self):
        return self._done

    def get_matches(self) -> typing.List[Match]:
        return self.matches