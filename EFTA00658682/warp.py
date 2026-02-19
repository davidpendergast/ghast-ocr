import typing
import math

import pygame
import numpy
import cv2


# from https://github.com/davidpendergast/pygame-utils

def warp(surf: pygame.Surface,
         warp_pts,
         smooth=True,
         bg_color=(255, 255, 255),
         out: pygame.Surface = None) -> typing.Tuple[pygame.Surface, pygame.FRect]:
    """Stretches a pygame surface to fill a quad using cv2's perspective warp.

        Args:
            surf: The surface to transform.
            warp_pts: A list of four xy coordinates representing the polygon to fill.
                Points should be specified in clockwise order starting from the top left.
            smooth: Whether to use linear interpolation for the image transformation.
                If false, nearest neighbor will be used.
            out: An optional surface to use for the final output. If None or not
                the correct size, a new surface will be made instead.

        Returns:
            [0]: A Surface containing the warped image.
            [1]: A Rect describing where to blit the output surface to make its coordinates
                match the input coordinates.
    """
    if len(warp_pts) != 4:
        raise ValueError("warp_pts must contain four points")

    w, h = surf.get_size()
    is_alpha = surf.get_flags() & pygame.SRCALPHA

    # XXX some nasty work here to convert from pygame's pixel coords to cv2's .-.
    eps = 0.49999
    src_corners = numpy.float32([(-eps, -eps), (-eps, w - eps), (h - eps, w - eps), (h - eps, -eps)])
    quad = [tuple(reversed(p)) for p in warp_pts]

    # find the bounding box of warp points
    # (this gives the size and position of the final output surface).
    min_x, max_x = float('inf'), -float('inf')
    min_y, max_y = float('inf'), -float('inf')
    for p in quad:
        min_x, max_x = min(min_x, p[0]), max(max_x, p[0])
        min_y, max_y = min(min_y, p[1]), max(max_y, p[1])
    warp_bounding_box = pygame.FRect(min_x, min_y, max_x - min_x, max_y - min_y)

    shifted_quad = [(p[0] - min_x, p[1] - min_y) for p in quad]
    dst_corners = numpy.float32(shifted_quad)

    mat = cv2.getPerspectiveTransform(src_corners, dst_corners)

    orig_rgb = pygame.surfarray.pixels3d(surf)
    out_size = (math.ceil(warp_bounding_box.w),
                math.ceil(warp_bounding_box.h))

    if smooth is None:
        smooth = cv2.INTER_NEAREST
    flags = smooth

    out_rgb = cv2.warpPerspective(orig_rgb, mat, out_size, borderValue=bg_color, flags=flags)

    # if the provided output to overwrite is wrong size, make a new surface to use
    if out is None or out.get_size() != out_rgb.shape[0:2]:
        out = pygame.Surface(out_rgb.shape[0:2], pygame.SRCALPHA if is_alpha else 0)

    pygame.surfarray.blit_array(out, out_rgb)

    if is_alpha:
        orig_alpha = pygame.surfarray.pixels_alpha(surf)
        out_alpha = cv2.warpPerspective(orig_alpha, mat, out_size, flags=flags)
        alpha_px = pygame.surfarray.pixels_alpha(out)
        alpha_px[:] = out_alpha
    else:
        out.set_colorkey(surf.get_colorkey())

    # XXX swap x and y once again...
    return out, pygame.FRect(warp_bounding_box.y, warp_bounding_box.x,
                             warp_bounding_box.h, warp_bounding_box.w)


def rect_contains(r1, r2):
    return (r1[0] <= r2[0]
            and r1[1] <= r2[1]
            and r1[0] + r1[2] >= r2[0] + r2[2]
            and r1[1] + r1[3] >= r2[1] + r2[3])


def calc_error(
        sample_img: pygame.Surface,
        rendered_template: pygame.Surface,
        rect: pygame.Rect) -> typing.Tuple[int, pygame.Surface]:

    surf_bw = pygame.transform.grayscale(sample_img.subsurface(rect))
    rend_bw = pygame.transform.grayscale(rendered_template)

    # should be the same size
    surf_vals = pygame.surfarray.pixels_red(surf_bw)
    rend_vals = pygame.surfarray.pixels_red(rend_bw)

    alpha_surf = pygame.surfarray.pixels_alpha(rend_bw)
    err_surf = numpy.subtract(surf_vals, rend_vals, dtype=numpy.int64)
    err_surf = numpy.abs(err_surf, out=err_surf)
    err_surf = numpy.multiply(err_surf, alpha_surf, dtype=numpy.int64)
    err_surf = numpy.floor_divide(err_surf, 255, out=err_surf)

    total_err = numpy.sum(numpy.square(err_surf))

    ret = pygame.Surface(err_surf.shape[0:2], pygame.SRCALPHA)
    pygame.surfarray.pixels_alpha(ret)[:] = alpha_surf
    pygame.surfarray.pixels_red(ret)[:] = err_surf
    pygame.surfarray.pixels_blue(ret)[:] = err_surf
    pygame.surfarray.pixels_green(ret)[:] = err_surf

    return total_err / (rect[2] * rect[3]), ret


def safe_subsurf(img, rect, bg_color="white"):
    if rect[0] >= 0 and rect[1] >= 0 and rect[0] + rect[2] <= img.get_width() and rect[1] + rect[3] <= img.get_height():
        return img.subsurface(rect)
    else:
        res = pygame.Surface((rect[2], rect[3]))
        res.fill(bg_color)
        res.blit(img, (-rect[0], -rect[1]))
        return res


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
