def theraml_point_rotate(rotation_angle, tx, ty, raw_w, raw_h, disp_w, disp_h):
    nx = tx / raw_w
    ny = ty / raw_h

    if rotation_angle == 0:
        rnx, rny = nx, ny
    elif rotation_angle == 90:
        rnx, rny = 1 - ny, nx
    elif rotation_angle == 180:
        rnx, rny = 1 - nx, 1 - ny
    elif rotation_angle == 270:
        rnx, rny = ny, 1 - nx
    else:
        rnx, rny = nx, ny
    
    dx = int(rnx * disp_w)
    dy = int(rny * disp_h)

    dx = max(0, min(disp_w - 1, dx))
    dy = max(0, min(disp_h - 1, dy))
    return dx, dy
