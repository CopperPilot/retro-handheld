#!/usr/bin/env python3
"""Parametric enclosure & purchased-part generator for Pocket Retro Game Console."""

from rea_hardware import cad


def world_from_front(bf: dict, fx: float, fy: float) -> tuple[float, float]:
    """Map front-view (fx, fy) in mm to world (wx, wy) in mm."""
    ox, oy, _ = bf["front_origin"]
    return ox + fx, oy - fy


def build_outer_blank(w: float, h: float, r: float, z0: float, z1: float,
                      chamfer_bottom: float = 0.0, chamfer_top: float = 0.0):
    """Build an outer shell blank centered on the envelope with optional Z chamfers."""
    cx = w / 2.0 - 2.5
    cy = -h / 2.0 + 2.5
    sections = []
    if chamfer_bottom > 0.0:
        c = chamfer_bottom
        sections.append((z0, w - 2 * c, h - 2 * c, max(0.8, r - c), cx, cy))
        sections.append((z0 + c, w, h, r, cx, cy))
    else:
        sections.append((z0, w, h, r, cx, cy))

    if chamfer_top > 0.0:
        c = chamfer_top
        sections.append((z1 - c, w, h, r, cx, cy))
        sections.append((z1 - 1e-3, w - 2 * c, h - 2 * c, max(0.8, r - c), cx, cy))
    else:
        sections.append((z1 - 1e-3, w, h, r, cx, cy))

    return cad.loft(sections)


def build_purchased_models(bf: dict) -> None:
    """Build watertight STL models for purchased parts (display and battery)."""
    # 1. Display module: ER-TFT024-3 (52.0 x 40.0 x 2.2 mm at [3.0, -44.5, 4.2])
    disp_info = bf["purchased"]["display"]
    dx, dy, _ = disp_info["position_mm"]
    dw, dh, dd = disp_info["dims_mm"]
    disp_solid = cad.rounded_box(dw, dh, dd, r=0.5, at=(dx, dy, 4.55))
    cad.export(disp_solid, disp_info["model"])

    # 2. Battery pack: LP503450-1200mAh (34.0 x 50.0 x 5.0 mm at [12.0, -68.0, -5.8])
    bat_info = bf["purchased"]["battery"]
    bx, by, _ = bat_info["position_mm"]
    bw, bh, _ = bat_info["dims_mm"]
    bat_solid = cad.rounded_box(bw, bh, 4.15, r=1.2, at=(bx, by, -4.95))
    cad.export(bat_solid, bat_info["model"])


def main() -> None:
    bf = cad.board_frame("rea/spec.yaml")
    spec = bf["spec"]

    env_w = bf["env_w"]          # 63.0
    env_h = bf["env_h"]          # 81.0
    env_d = bf["env_d"]          # 17.0
    corner_r = bf["corner_r"]    # 2.5
    board_w = bf["board_w"]      # 58.0
    board_h = bf["board_h"]      # 76.0
    ox, oy, oz = bf["front_origin"]  # [-2.5, 2.5, 12.55]

    # Physical shell Z bounds: [-6.20, +10.80] (17.00 mm total depth)
    # With oz = 12.75, F_USBC (oz - 11.7 = +1.05, rays at Z = -0.03..+2.13) aligns directly with J1 on F.Cu
    # using a single stadium USB-C opening (Z = -0.08..+3.52) and a solid lower wall closing the battery bay.
    z_min = -6.20
    z_max = 10.798
    env_rect = (ox, oy - env_h, ox + env_w, oy)

    # Map features by id
    features = {f["id"]: f for f in spec["fidelity"]["must_match"]}

    # Build purchased part STLs first
    build_purchased_models(bf)

    # Split plane between rear_shell (up to 5.45) and front_shell (from 5.50)
    z_rear_top = 5.45
    z_front_bot = 5.50

    # -------------------------------------------------------------------------
    # 1. REAR SHELL (case/out/rear_shell.stl)
    # -------------------------------------------------------------------------
    rear_outer = build_outer_blank(
        env_w, env_h, corner_r, z_min, z_rear_top,
        chamfer_bottom=0.75, chamfer_top=0.0
    )

    # Main upper cavity for PCBA (X: -0.40 .. 58.40, Y: -76.40 .. 0.40, Z: -0.05 .. z_rear_top + 1)
    cav_x0, cav_y0 = -0.40, -76.40
    cav_w, cav_h = board_w + 0.80, board_h + 0.80
    upper_cavity = cad.rounded_box(
        cav_w, cav_h, (z_rear_top + 1.0) - (-0.05),
        r=1.0, at=(cav_x0, cav_y0, -0.05)
    )

    # Lower cavity below PCBA (Z: -2.5 .. 0.1) for bottom component clearance, leaving side ledges & mounting bosses
    lower_pcb_clear = cad.rounded_box(52.0, 71.0, 2.7, r=1.5, at=(3.0, -73.5, -2.5))

    # Internal vertical insertion & bottom-peg relief for J1 at (29.00, -74.18), spanning X = 24.53..33.47, Y = -77.03..-69.13
    # Stops at Z = -0.75 (above battery top Z = -0.80) so battery bay is completely sealed off.
    # J1 rear edge (Y = -69.13) has 1.03 mm physical PCB clearance to SW9/SW10 front edge (Y = -68.10).
    j1_bottom_relief = cad.rounded_box(9.6, 8.35, (z_rear_top + 1.0) - (-0.75), r=0.6, at=(24.2, -77.25, -0.75))

    # Deep pocket for battery (battery seated at [12.0, -68.0, -4.95..-0.80])
    # Floor at Z = -5.00 (0.05 mm below battery bottom at -4.95; 1.20 mm above z_min = -6.20)
    bat_pocket = cad.rounded_box(35.0, 51.0, 5.2, r=1.5, at=(11.5, -68.5, -5.00))

    # Channel for battery wire lead at bottom-right (around X=41.0, Y=-76.9..-68.0, Z=-4.2..z_rear_top+1)
    bat_wire_ch = cad.rounded_box(6.4, 9.0, (z_rear_top + 1.0) - (-4.2), r=1.2, at=(37.8, -76.9, -4.2))

    # Top-center relief pocket for J2 display FPC connector (which extends to Y = +1.75 mm on pcba)
    j2_relief = cad.rounded_box(15.0, 3.05, (z_rear_top + 1.0) - (-0.05), r=0.8, at=(21.5, -1.0, -0.05))

    rear = rear_outer - upper_cavity - lower_pcb_clear - j1_bottom_relief - bat_pocket - bat_wire_ch - j2_relief

    # Add solid internal baffle wall in front of battery bay at X = 23.0..35.0, Y = -76.35..-68.85, Z = -2.60..-0.75
    # so the battery bay is 100% closed off behind the USB-C opening.
    usb_baffle = cad.box(12.0, 7.50, 1.85, at=(23.0, -76.35, -2.60))
    rear = cad.union(rear, usb_baffle)

    # Add 4 PCB support bosses around the 4 mounting holes up to Z = -0.04 (0.04 mm below PCBA)
    for mh in bf["holes"]:
        hx, hy = mh["x_mm"], -mh["y_mm"]
        boss = cad.standoff(hx, hy, z0=-2.6, z1=-0.04, od=5.2, id_=0.0)
        rear = cad.union(rear, boss)

    # Cut pilot holes (d=2.0 mm, blind down to Z=-2.2) in the 4 bosses
    for mh in bf["holes"]:
        hx, hy = mh["x_mm"], -mh["y_mm"]
        rear = rear - cad.hole(hx, hy, d=2.0, depth=2.4, z0=-2.2)

    # Single bottom-edge USB-C port opening (F_USBC: view=bottom, center=[31.5, 11.7], size=[9.5, 3.6])
    # Single stadium cut at Z = -0.08..+3.52 (center Z = 1.72, h = 3.60) aligned with J1 mouth (Z = +0.20..+3.44)
    f_usb = features["F_USBC"]
    usb_wx = ox + f_usb["center_mm"][0]  # 29.0
    usb_w, _ = f_usb["size_mm"]          # 9.5, 3.6
    usb_cut = cad.edge_cut(
        axis="y", center=usb_wx, z=1.72, w=usb_w + 0.4, h=3.60,
        side="min", envelope=env_rect, r=1.0, reach=4.50
    )
    rear = rear - usb_cut

    # Internal top-edge saddle pockets in rear_shell for the 4 shoulder button actuator plungers (Y = -0.60 .. +1.25)
    # Outer top wall of rear_shell (Y = +1.25 .. +2.50, Z = -6.20 .. +5.45) remains 100% solid and unbroken.
    shoulder_ids = ["F_BTN_L1", "F_BTN_L2", "F_BTN_R2", "F_BTN_R1"]
    for sid in shoulder_ids:
        sf = features[sid]
        swx = ox + sf["center_mm"][0]
        sw_w, _ = sf["size_mm"]
        slot_w = sw_w + 0.16
        sh_inner_pocket = cad.rounded_box(
            slot_w, 1.85, (z_rear_top - 1.10) + 1.0,
            r=0.45, at=(swx - slot_w / 2.0, -0.60, 1.10)
        )
        rear = rear - sh_inner_pocket

    # Rear vertical grip grooves (F_REAR_GROOVES: 14 stadium grooves on rear face Z = z_min)
    # In inputs/rear.jpg, the leftmost two grooves (i = 0, 1) are shortened above the two lanyard slots (F_LANYARD),
    # while the remaining 12 grooves (i = 2 .. 13) extend down so their bottom ends align with the lanyard slots.
    f_grv = features["F_REAR_GROOVES"]
    grv_w_span, _ = f_grv["size_mm"]  # 52.8, 34.8
    grv_count = 14
    grv_w = 2.4
    grv_pitch = (grv_w_span - grv_w) / (grv_count - 1)
    grv_x0 = (ox + f_grv["center_mm"][0]) - (grv_count - 1) * grv_pitch / 2.0

    f_lan = features["F_LANYARD"]
    lan_y = oy - f_lan["center_mm"][1]  # -70.50 (spans Y = -72.75 .. -68.25)
    lan_h = 4.50
    grv_y_top = -32.20
    grv_y_short_bot = -66.80            # stops 1.45 mm above lanyard slots
    grv_y_full_bot = lan_y - lan_h / 2.0  # -72.75, aligned with bottom ends of lanyard slots

    for i in range(grv_count):
        gx = grv_x0 + i * grv_pitch
        y_bot = grv_y_short_bot if i < 2 else grv_y_full_bot
        g_cy = 0.5 * (grv_y_top + y_bot)
        g_h = grv_y_top - y_bot
        rear = rear - cad.slot(
            gx, g_cy,
            w=grv_w, h=g_h, depth=0.38, r=1.1, z0=z_min - 0.1
        )

    # Rear lanyard loop slots (F_LANYARD: pair of vertical pill recesses below shortened leftmost two grooves)
    for i in range(2):
        lx_left = grv_x0 + i * grv_pitch
        rear = rear - cad.slot(lx_left, lan_y, w=2.4, h=lan_h, depth=0.80, r=1.1, z0=z_min - 0.1)

    # Add two small press-fit nibs on top rim of rear_shell (overlapping front_shell at Z=5.50 by 0.05 mm -> Z=5.55)
    for px in [12.0, 46.0]:
        nib = cad.box(2.0, 0.06, 0.15, at=(px, -77.5, 5.40))
        rear = cad.union(rear, nib)

    cad.export(rear, "case/out/rear_shell.stl")

    # -------------------------------------------------------------------------
    # 2. SHOULDER BUTTONS (case/out/shoulder_buttons.stl)
    # -------------------------------------------------------------------------
    # Seated in flush contoured upper-shell slots (Z = 5.50 .. 9.20) with 0.06 mm vertical clearance
    # and internal actuator plungers reaching down behind rear_shell outer top wall to SW11..SW14 (Z = 1.20 .. 6.10).
    sh_parts = []
    for sid in shoulder_ids:
        sf = features[sid]
        swx = ox + sf["center_mm"][0]
        sw_w, _ = sf["size_mm"]
        cap_w = sw_w - 0.04
        cap_r = 1.35 if sw_w > 9.0 else 0.85
        cap_body = cad.rounded_box(
            cap_w, 1.95, 9.14 - 5.56, r=cap_r,
            at=(swx - cap_w / 2.0, 0.55, 5.56),
            r_edge=0.25
        )
        # Internal retention flange captured under front_shell retention ceiling (Z = 9.20 .. 9.85, Y = 0.05 .. 1.15 -> 1.10 mm thick >= 0.80 mm CNC)
        flange_w = cap_w - 0.6
        ret_flange = cad.rounded_box(
            flange_w, 1.10, 9.75 - 5.56, r=0.4,
            at=(swx - flange_w / 2.0, 0.05, 5.56)
        )
        # Internal actuator plunger reaching down to SW11..SW14 tip (Y = -0.121, Z = 0.235..1.435)
        # Y = +0.02 .. +1.15 (1.13 mm thick >= 0.80 mm CNC) stays +0.02 mm outside PCB (Y <= 0.00) and 0.141 mm from switch plunger
        plunger_step = cad.rounded_box(
            3.2, 1.13, 6.10 - 1.20, r=0.4,
            at=(swx - 1.6, 0.02, 1.20)
        )
        sh_parts.append(cad.union(cap_body, ret_flange, plunger_step))

    shoulder_solid = cad.union(*sh_parts)
    cad.export(shoulder_solid, "case/out/shoulder_buttons.stl")

    # -------------------------------------------------------------------------
    # 3. D-PAD (case/out/dpad.stl)
    # -------------------------------------------------------------------------
    dpad_up = features["F_DPAD_UP"]
    dpad_down = features["F_DPAD_DOWN"]
    dpad_left = features["F_DPAD_LEFT"]
    dpad_right = features["F_DPAD_RIGHT"]
    dpad_cx = ox + dpad_up["center_mm"][0]     # 11.58
    dpad_cy = oy - dpad_left["center_mm"][1]   # -59.13

    # Cap cross (Z: 5.55 .. z_max) with 0.30 mm radial clearance in 20.6 x 7.0 bore
    dpad_arm_w = 6.4
    dpad_span = 20.0
    cap_h = z_max - 5.55
    dpad_h_bar = cad.slot(dpad_cx, dpad_cy, w=dpad_span, h=dpad_arm_w, depth=cap_h, r=1.0, z0=5.55)
    dpad_v_bar = cad.slot(dpad_cx, dpad_cy, w=dpad_arm_w, h=dpad_span, depth=cap_h, r=1.0, z0=5.55)
    # Retention flange at base of cross (Z: 5.55 .. 6.55, 1.00 mm thick, 0.05 mm below front_shell ceiling Z=6.60)
    dpad_fh = cad.slot(dpad_cx, dpad_cy, w=dpad_span + 1.4, h=dpad_arm_w + 1.6, depth=1.00, r=1.2, z0=5.55)
    dpad_fv = cad.slot(dpad_cx, dpad_cy, w=dpad_arm_w + 1.6, h=dpad_span + 1.4, depth=1.00, r=1.2, z0=5.55)
    dpad_solid = cad.union(dpad_h_bar, dpad_v_bar, dpad_fh, dpad_fv)

    # 4 actuator plungers down to Z = 1.85 mm over SW1..SW4 (0.034 mm above B3U-1000P top Z=1.816 mm)
    for df in (dpad_up, dpad_down, dpad_left, dpad_right):
        px, py = world_from_front(bf, *df["center_mm"])
        plunger = cad.cylinder(r=1.3, h=5.65 - 1.85, at=(px, py, 1.85))
        dpad_solid = cad.union(dpad_solid, plunger)

    # 4 directional arrow triangle engravings on top of D-pad
    arrow_specs = [
        (dpad_up, [(0.0, 1.4), (-1.3, -1.0), (1.3, -1.0)]),
        (dpad_down, [(0.0, -1.4), (1.3, 1.0), (-1.3, 1.0)]),
        (dpad_left, [(-1.4, 0.0), (1.0, -1.3), (1.0, 1.3)]),
        (dpad_right, [(1.4, 0.0), (-1.0, 1.3), (-1.0, -1.3)]),
    ]
    for df, pts in arrow_specs:
        ax, ay = world_from_front(bf, *df["center_mm"])
        tri = cad.CrossSection([pts]).extrude(0.5).translate((ax, ay, z_max - 0.35))
        dpad_solid = dpad_solid - tri

    # Miter the cross into 4 independent directional actuator segments (UP, DOWN, LEFT, RIGHT)
    cut_w = 0.32
    cut_l = 14.0
    diag1 = cad.box(cut_l, cut_w, 11.0, at=(-cut_l / 2.0, -cut_w / 2.0, 1.5)).rotate([0, 0, 45]).translate([dpad_cx, dpad_cy, 0])
    diag2 = cad.box(cut_l, cut_w, 11.0, at=(-cut_l / 2.0, -cut_w / 2.0, 1.5)).rotate([0, 0, -45]).translate([dpad_cx, dpad_cy, 0])
    center_clear = cad.cylinder(r=1.25, h=11.0, at=(dpad_cx, dpad_cy, 1.5))
    dpad_solid = dpad_solid - diag1 - diag2 - center_clear
    cad.export(dpad_solid, "case/out/dpad.stl")

    # -------------------------------------------------------------------------
    # 4. ACTION BUTTONS (case/out/action_buttons.stl)
    # -------------------------------------------------------------------------
    act_ids = [("F_BTN_X", "X"), ("F_BTN_Y", "Y"), ("F_BTN_A", "A"), ("F_BTN_B", "B")]
    act_solids = []
    for fid, label in act_ids:
        af = features[fid]
        ax, ay = world_from_front(bf, *af["center_mm"])
        cap_d = 7.6      # bore in front_shell is 8.2 mm (0.30 mm radial clearance)
        flange_d = 8.6   # 1.00 mm thick flange at Z = 5.55 .. 6.55
        cap_cyl = cad.cylinder(r=cap_d / 2.0, h=z_max - 5.55, at=(ax, ay, 5.55))
        flange_cyl = cad.cylinder(r=flange_d / 2.0, h=1.00, at=(ax, ay, 5.55))
        plunger_cyl = cad.cylinder(r=1.3, h=5.65 - 1.85, at=(ax, ay, 1.85))
        btn = cad.union(cap_cyl, flange_cyl, plunger_cyl)
        btn = btn - cad.text(label, size=3.0, at=(ax, ay, z_max - 0.30), depth=0.4)
        act_solids.append(btn)

    cad.export(cad.union(*act_solids), "case/out/action_buttons.stl")

    # -------------------------------------------------------------------------
    # 5. START / SELECT BUTTONS (case/out/start_select_buttons.stl)
    # -------------------------------------------------------------------------
    ss_ids = [("F_BTN_SE", "SE"), ("F_BTN_ST", "ST")]
    ss_solids = []
    # SW9 (24.59, -66.85) and SW10 (32.65, -66.85) span Y = -68.10 .. -65.60, with 1.03 mm physical clearance
    # North of J1 (29.00, -74.18, spanning Y = -77.03 .. -69.13).
    # Single cylindrical plunger (r = 0.75 mm) is concentric with SW9/SW10 black center plungers at (sx, -66.85).
    sw_cy = -66.85
    for fid, label in ss_ids:
        sf = features[fid]
        sx, sy = world_from_front(bf, *sf["center_mm"])
        cap_d = 5.2      # bore in front_shell is 5.8 mm (0.30 mm radial clearance)
        flange_d = 6.2   # 0.90 mm thick retention flange at Z = 5.65 .. 6.55
        cap_cyl = cad.cylinder(r=cap_d / 2.0, h=z_max - 5.65, at=(sx, sy, 5.65))
        flange_cyl = cad.cylinder(r=flange_d / 2.0, h=0.90, at=(sx, -67.50, 5.65))
        plunger_cyl = cad.cylinder(r=0.75, h=5.75 - 1.85, at=(sx, sw_cy, 1.85))
        btn = cad.union(cap_cyl, flange_cyl, plunger_cyl)
        btn = btn - cad.text(label, size=1.7, at=(sx, sy, z_max - 0.30), depth=0.35)
        ss_solids.append(btn)

    cad.export(cad.union(*ss_solids), "case/out/start_select_buttons.stl")

    # -------------------------------------------------------------------------
    # 6. FRONT SHELL (case/out/front_shell.stl)
    # -------------------------------------------------------------------------
    front_outer = build_outer_blank(
        env_w, env_h, corner_r, z_front_bot, z_max,
        chamfer_bottom=0.0, chamfer_top=0.75
    )

    # Hollow out interior below Z = 6.60 mm (leaving front bezel Z = 6.60 .. z_max)
    front_inner = cad.rounded_box(
        cav_w, cav_h, (6.60 - z_front_bot) + 0.5,
        r=1.0, at=(cav_x0, cav_y0, z_front_bot - 0.5)
    )
    front_bat_ch = cad.rounded_box(6.4, 9.0, (6.0 - z_front_bot) + 0.5, r=1.2, at=(37.8, -76.9, z_front_bot - 0.5))
    front = front_outer - front_inner - front_bat_ch

    # Display window recess and through-opening (F_DISP: center=[31.5, 27.14], size=[57.13, 46.79])
    f_disp = features["F_DISP"]
    disp_wx, disp_wy = world_from_front(bf, *f_disp["center_mm"])  # (29.0, -24.64)
    disp_w, disp_h = f_disp["size_mm"]                             # 57.13, 46.79
    win_ledge_z = z_max - 1.05                                     # 9.75

    # Add support frame under display window ledge from Z = 6.60 .. win_ledge_z
    win_support_block = cad.slot(
        disp_wx, disp_wy, w=disp_w + 0.8, h=disp_h + 0.8,
        depth=win_ledge_z - 6.60, r=1.5, z0=6.60
    )
    front = cad.union(front, win_support_block)

    # Outer window recess for display_window (Z = win_ledge_z .. z_max + 0.1): 56.93 x 46.47 mm
    win_recess = cad.slot(disp_wx, disp_wy, w=disp_w - 0.20, h=disp_h - 0.32, depth=1.5, r=1.5, z0=win_ledge_z)
    # Inner through-aperture (Z = 4.0 .. win_ledge_z + 0.05): 51.2 x 39.2 mm
    win_aperture = cad.slot(disp_wx, -24.5, w=51.2, h=39.2, depth=(win_ledge_z - 4.0) + 0.1, r=1.2, z0=4.0)
    # Relief below Z = 6.79 for purchased.display (52.0 x 40.0 at [3.0, -44.5, 4.55..6.75], 0.04 mm Z gap)
    disp_mod_relief = cad.rounded_box(52.8, 40.8, 2.89, r=1.0, at=(2.6, -44.9, 3.90))
    front = front - win_recess - win_aperture - disp_mod_relief

    # Add two tiny press-fit nibs on the display window ledge (overlapping display_window at win_ledge_z by 0.05 mm)
    for px in [12.0, 46.0]:
        w_nib = cad.box(2.0, 0.06, 0.10, at=(px, -46.8, win_ledge_z - 0.05))
        front = cad.union(front, w_nib)

    # Cut flush top-edge shoulder button openings (Z = 5.50 .. 9.20) and internal retention pockets (Z = 5.50 .. 9.85)
    # Leaves 1.60 mm outer top bar (10.80 - 9.20) and 0.95 mm retention roof (10.80 - 9.85 >= 0.80 mm CNC min wall).
    for sid in shoulder_ids:
        sf = features[sid]
        swx = ox + sf["center_mm"][0]
        sw_w, _ = sf["size_mm"]
        slot_w = sw_w + 0.16
        sh_front_cut = cad.rounded_box(
            slot_w, 3.6, (9.20 - z_front_bot) + 0.1,
            r=0.5, at=(swx - slot_w / 2.0, -0.60, z_front_bot - 0.1)
        )
        # Internal retention pocket stays strictly behind Y = 1.20 so outer top wall and top chamfer remain intact
        flange_cut = cad.rounded_box(
            slot_w, 1.80, (9.85 - z_front_bot) + 0.1,
            r=0.5, at=(swx - slot_w / 2.0, -0.60, z_front_bot - 0.1)
        )
        front = front - sh_front_cut - flange_cut

    # Cut D-pad cross opening through front_shell (Z = 6.50 .. z_max + 0.5)
    bore_depth = (z_max - 6.50) + 0.5
    front = front - cad.slot(dpad_cx, dpad_cy, w=20.6, h=7.0, depth=bore_depth, r=1.1, z0=6.50)
    front = front - cad.slot(dpad_cx, dpad_cy, w=7.0, h=20.6, depth=bore_depth, r=1.1, z0=6.50)

    # Cut Action button bores through front_shell (d = 8.2 mm, Z = 6.50 .. z_max + 0.5)
    for fid, _ in act_ids:
        af = features[fid]
        ax, ay = world_from_front(bf, *af["center_mm"])
        front = front - cad.hole(ax, ay, d=8.2, depth=bore_depth, z0=6.50)

    # Shallow pill recess around Select & Start on outer face of front_shell (Z = z_max - 0.35 .. z_max + 0.5)
    se_x, se_y = world_from_front(bf, *features["F_BTN_SE"]["center_mm"])
    st_x, st_y = world_from_front(bf, *features["F_BTN_ST"]["center_mm"])
    pill_cx = (se_x + st_x) / 2.0
    pill_cy = (se_y + st_y) / 2.0
    front = front - cad.slot(pill_cx, pill_cy, w=16.5, h=7.9, depth=1.0, r=3.8, z0=z_max - 0.35)

    # Cut Select & Start button bores through front_shell (d = 5.8 mm, Z = 6.50 .. z_max + 0.5)
    for fid, _ in ss_ids:
        sf = features[fid]
        sx, sy = world_from_front(bf, *sf["center_mm"])
        front = front - cad.hole(sx, sy, d=5.8, depth=bore_depth, z0=6.50)

    # Add 2 clamping posts at bottom mounting holes (H3, H4: (4.0, -72.5), (54.0, -72.5)) down to Z = 1.64
    for hx, hy in [(4.0, -72.5), (54.0, -72.5)]:
        post = cad.standoff(hx, hy, z0=1.64, z1=6.65, od=3.6, id_=0.0)
        front = cad.union(front, post)

    cad.export(front, "case/out/front_shell.stl")

    # -------------------------------------------------------------------------
    # 7. DISPLAY WINDOW (case/out/display_window.stl)
    # -------------------------------------------------------------------------
    win_top = cad.slot(disp_wx, disp_wy, w=disp_w - 0.28, h=disp_h - 0.40, depth=(z_max - 0.10) - win_ledge_z, r=1.4, z0=win_ledge_z)
    win_bottom = cad.slot(disp_wx, -24.5, w=50.5, h=38.5, depth=(win_ledge_z + 0.05) - 6.80, r=1.0, z0=6.80)
    display_window = cad.union(win_top, win_bottom)
    cad.export(display_window, "case/out/display_window.stl")


if __name__ == "__main__":
    main()
