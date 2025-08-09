# drywall_estimator_app.py
# Drywall estimator with per-room geometry, openings, quick-pick heights, door presets,
# material takeoff (board, mud, tape, screws, corner bead, optional resilient channel),
# and pricing (cost per sheet, pot lights, per-ft2/m2, tax %, cash price).

import streamlit as st
import pandas as pd
import math

FT2_TO_M2 = 0.09290304

# ---- Presets ----
WALL_HEIGHT_PRESETS = ["8 ft", "9 ft", "10 ft", "12 ft", "14 ft", "Custom"]
DOOR_PRESETS = [
    ("24 x 80 in", 24/12, 80/12),
    ("28 x 80 in", 28/12, 80/12),
    ("30 x 80 in", 30/12, 80/12),
    ("32 x 80 in", 32/12, 80/12),
    ("36 x 80 in", 36/12, 80/12),
    ("Custom", None, None),
]

st.set_page_config(page_title="Drywall Estimator", page_icon="🧱", layout="wide")
st.title("Drywall Estimator (per room)")
st.caption("Calculate drywall areas, auto material takeoff, and pricing. Windows/doors deducted, ceilings optional.")

# ================= Sidebar Options =================
with st.sidebar:
    st.header("General Options")
    include_waste = st.checkbox("Add waste percentage", value=True)
    waste_pct = st.number_input("Waste %", 0.0, 50.0, 10.0, 0.5) if include_waste else 0.0
    show_intermediate = st.checkbox("Show intermediate math", value=False)

    st.markdown("---")
    st.header("Material Takeoff Factors (defaults)")
    mud_gal_per_1000 = st.number_input("Mud (gal per 1000 ft^2)", 5.0, 20.0, 9.5, 0.1)
    mud_pail_gal = st.number_input("Mud pail size (gal)", 1.0, 6.0, 4.5, 0.5)
    tape_sqft_per_roll = st.number_input("Tape coverage (ft^2 per roll)", 600.0, 2000.0, 1200.0, 50.0)
    screws_per_sqft = st.number_input("Screws per ft^2", 0.5, 2.0, 1.25, 0.05)
    screws_per_box = st.number_input("Screws per box", 500, 5000, 1000, 100)

    corner_bead_lf_per_1000 = st.number_input("Corner bead (lf per 1000 ft^2)", 0.0, 200.0, 50.0, 5.0)
    corner_bead_piece_len_ft = st.number_input("Corner bead piece length (ft)", 4.0, 12.0, 8.0, 1.0)

    st.markdown("---")
    st.header("Board & RC Settings")
    sheet_size = st.selectbox("Sheet size", ["4x8 (32 ft^2)", "4x12 (48 ft^2)"], index=0)
    cost_per_sheet = st.number_input("Cost per sheet ($)", 0.0, 100.0, 0.0, 0.5)
    include_resilient_channel = st.checkbox("Include Resilient Channel (calculated)", value=False)
    rc_spacing_in = st.selectbox("RC spacing (in)", [16, 24], index=0)
    rc_piece_length_ft = st.number_input("RC piece length (ft)", 8.0, 16.0, 12.0, 1.0)

    st.markdown("---")
    st.header("Pricing")
    pot_light_count = st.number_input("Pot lights (qty)", min_value=0, step=1, value=0)
    pot_light_cost = st.number_input("Cost per pot light ($)", min_value=0.0, step=1.0, value=0.0)
    high_areas_ft2 = st.number_input("High areas (extra ft^2 to charge)", min_value=0.0, step=1.0, value=0.0,
                                     help="Extra tall/complex zones to charge but not add to materials.")
    price_per_sqft = st.number_input("Price per ft^2 ($)", min_value=0.0, step=0.01, value=0.0)
    price_per_sqm = st.number_input("Price per m^2 ($)", min_value=0.0, step=0.01, value=0.0)
    tax_pct = st.number_input("Tax %", 0.0, 25.0, 13.0, 0.5, help="Ontario HST ~13%")

st.markdown("---")

# ================= Room Inputs =================
col_l, col_r = st.columns([1, 1])
with col_l:
    room_count = st.number_input("Number of rooms", 1, 50, 3, 1)
with col_r:
    default_h_choice = st.selectbox("Default wall height", WALL_HEIGHT_PRESETS, index=0)
    if default_h_choice == "Custom":
        default_wall_h = st.number_input("Custom default wall height (ft)", 0.0, 20.0, 8.0, 0.1)
    else:
        default_wall_h = float(default_h_choice.split()[0])

rooms_data = []
rc_total_lf = 0.0  # accumulate resilient channel linear feet across ceilings

for i in range(int(room_count)):
    st.subheader(f"Room {i+1}")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 1])
        with c1:
            name = st.text_input(f"Room name #{i+1}", value=f"Room {i+1}", key=f"name_{i}")
        with c2:
            length = st.number_input(f"Length (ft) #{i+1}", 0.0, 1000.0, 0.0, 0.1, key=f"len_{i}")
        with c3:
            width = st.number_input(f"Width (ft) #{i+1}", 0.0, 1000.0, 0.0, 0.1, key=f"wid_{i}")
        with c4:
            default_idx = WALL_HEIGHT_PRESETS.index(f"{int(default_wall_h)} ft") if f"{int(default_wall_h)} ft" in WALL_HEIGHT_PRESETS else len(WALL_HEIGHT_PRESETS)-1
            h_choice = st.selectbox(f"Wall height #{i+1}", WALL_HEIGHT_PRESETS, index=default_idx, key=f"h_choice_{i}")
            if h_choice == "Custom":
                height = st.number_input(f"Custom wall height (ft) #{i+1}", 0.0, 20.0, default_wall_h, 0.1, key=f"h_{i}")
            else:
                height = float(h_choice.split()[0])

        c5, c6, c7 = st.columns([1, 1, 1])
        with c5:
            include_ceiling = st.checkbox(f"Include ceiling? #{i+1}", value=True, key=f"ceil_inc_{i}")
        with c6:
            has_windows = st.checkbox(f"Windows? #{i+1}", value=False, key=f"win_has_{i}")
        with c7:
            has_doors = st.checkbox(f"Doors? #{i+1}", value=False, key=f"door_has_{i}")

        # Windows
        windows = []
        if has_windows:
            num_windows = st.number_input(f"How many windows? #{i+1}", 1, 20, 1, 1, key=f"w_count_{i}")
            st.markdown("**Windows**")
            for w in range(num_windows):
                wc1, wc2 = st.columns(2)
                with wc1:
                    w_w = st.number_input(f"Window {w+1} width (ft) [R{i+1}]", 0.0, 100.0, 0.0, 0.1, key=f"win_w_{i}_{w}")
                with wc2:
                    w_h = st.number_input(f"Window {w+1} height (ft) [R{i+1}]", 0.0, 100.0, 0.0, 0.1, key=f"win_h_{i}_{w}")
                windows.append((w_w, w_h))

        # Doors
        doors = []
        if has_doors:
            num_doors = st.number_input(f"How many doors? #{i+1}", 1, 20, 1, 1, key=f"d_count_{i}")
            st.markdown("**Doors**")
            for d in range(num_doors):
                dc1, dc2, dc3 = st.columns([1.2, 1, 1])
                with dc1:
                    choice_labels = [label for label, _, _ in DOOR_PRESETS]
                    default_door_idx = choice_labels.index("30 x 80 in") if "30 x 80 in" in choice_labels else 0
                    door_choice = st.selectbox(f"Door {d+1} size [R{i+1}]", choice_labels, index=default_door_idx, key=f"door_choice_{i}_{d}")
                if door_choice == "Custom":
                    with dc2:
                        d_w_in = st.number_input(f"Door {d+1} width (in)", 0.0, 120.0, 0.0, 0.5, key=f"door_w_in_{i}_{d}")
                    with dc3:
                        d_h_in = st.number_input(f"Door {d+1} height (in)", 0.0, 120.0, 0.0, 0.5, key=f"door_h_in_{i}_{d}")
                    d_w = d_w_in / 12.0
                    d_h = d_h_in / 12.0
                else:
                    preset = next(p for p in DOOR_PRESETS if p[0] == door_choice)
                    d_w, d_h = preset[1], preset[2]
                doors.append((d_w, d_h))

        # --- Area calculations ---
        perimeter = 2 * (length + width)
        wall_area_gross = perimeter * height
        openings_area = sum(w * h for w, h in windows) + sum(w * h for w, h in doors)
        wall_area_net = max(wall_area_gross - openings_area, 0.0)
        ceiling_area = (length * width) if include_ceiling else 0.0
        total_area_ft2 = wall_area_net + ceiling_area
        waste_multiplier = 1.0 + (waste_pct / 100.0)
        total_with_waste_ft2 = total_area_ft2 * waste_multiplier

        # Resilient channel LF (if enabled) – rows across width, length per row = room length
        if include_resilient_channel and include_ceiling and width > 0 and length > 0:
            rows = math.floor((width * 12) / rc_spacing_in) + 1
            rc_total_lf += rows * length

        rooms_data.append({
            "room": name,
            "length_ft": length,
            "width_ft": width,
            "height_ft": height,
            "perimeter_ft": perimeter,
            "wall_area_net_ft2": wall_area_net,
            "ceiling_area_ft2": ceiling_area,
            "total_area_ft2": total_area_ft2,
            "total_with_waste_ft2": total_with_waste_ft2,
        })

        if show_intermediate:
            st.caption(
                f"Perimeter: {perimeter:.2f} ft | Walls net: {wall_area_net:.2f} ft^2 | "
                f"Ceiling: {ceiling_area:.2f} ft^2 | Total: {total_area_ft2:.2f} ft^2 | "
                f"Waste%: {waste_pct:.1f} -> With waste: {total_with_waste_ft2:.2f} ft^2"
            )

# ================= Summary & Takeoff =================
if rooms_data:
    df = pd.DataFrame(rooms_data)
    df["total_area_m2"] = df["total_area_ft2"] * FT2_TO_M2
    df["total_with_waste_m2"] = df["total_with_waste_ft2"] * FT2_TO_M2

    st.markdown("---")
    st.subheader("Per-room breakdown")
    show_cols = ["room","length_ft","width_ft","height_ft",
                 "wall_area_net_ft2","ceiling_area_ft2","total_area_ft2",
                 "total_area_m2","total_with_waste_ft2","total_with_waste_m2"]
    st.dataframe(df[show_cols], use_container_width=True)

    total_ft2 = float(df["total_area_ft2"].sum())
    total_m2 = total_ft2 * FT2_TO_M2
    total_waste_ft2 = float(df["total_with_waste_ft2"].sum())
    total_waste_m2 = total_waste_ft2 * FT2_TO_M2

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Grand Total (ft^2)", f"{total_ft2:,.2f}")
    c2.metric("Grand Total (m^2)", f"{total_m2:,.2f}")
    c3.metric("With Waste (ft^2)", f"{total_waste_ft2:,.2f}")
    c4.metric("With Waste (m^2)", f"{total_waste_m2:,.2f}")

    # ---------- MATERIAL TAKEOFF ----------
    st.markdown("---")
    st.subheader("Material Takeoff (auto)")

    sheet_area = 32.0 if "4x8" in sheet_size else 48.0
    sheets = math.ceil(total_waste_ft2 / sheet_area) if sheet_area > 0 else 0

    mud_gal = (total_waste_ft2 / 1000.0) * mud_gal_per_1000
    mud_pails = math.ceil(mud_gal / mud_pail_gal) if mud_pail_gal > 0 else 0

    tape_rolls = math.ceil(total_waste_ft2 / tape_sqft_per_roll) if tape_sqft_per_roll > 0 else 0

    screws_qty = math.ceil(total_waste_ft2 * screws_per_sqft)
    screws_boxes = math.ceil(screws_qty / screws_per_box) if screws_per_box > 0 else 0

    # Corner bead (pieces) via factor
    corner_bead_lf = (total_waste_ft2 / 1000.0) * corner_bead_lf_per_1000
    corner_bead_pcs = math.ceil(corner_bead_lf / corner_bead_piece_len_ft) if corner_bead_piece_len_ft > 0 else 0

    # Resilient channel (pieces)
    rc_pieces = 0
    if include_resilient_channel:
        rc_pieces = math.ceil(rc_total_lf / rc_piece_length_ft) if rc_piece_length_ft > 0 else 0

    colA, colB, colC = st.columns([1,1,1])
    with colA:
        st.write(f"Board area (with waste): **{total_waste_ft2:,.0f} ft^2**")
        st.write(f"Sheets ({sheet_size}): **{sheets}**")
        st.write(f"Mud: **{mud_gal:,.1f} gal** (~{mud_pails} pails @ {mud_pail_gal:g} gal)")
    with colB:
        st.write(f"Tape: **{tape_rolls} rolls** (≈ {int(tape_sqft_per_roll)} ft^2/roll)")
        st.write(f"Screws: **{screws_qty:,} pcs** (~{screws_boxes} boxes @ {screws_per_box} pcs)")
        st.write(f"Corner bead: **{corner_bead_pcs} pcs** (~{corner_bead_lf:,.0f} lf, {corner_bead_piece_len_ft:g} ft pieces)")
    with colC:
        if include_resilient_channel:
            st.write(f"Resilient channel: **{rc_pieces} pcs** (~{rc_total_lf:,.0f} lf, {rc_piece_length_ft:g} ft pieces)")
        else:
            st.write("Resilient channel: **not included**")

    # ---------- PRICING ----------
    st.markdown("---")
    st.subheader("Pricing")

    # Chargeable area uses with-waste + high areas
    charge_area_ft2 = total_waste_ft2 + high_areas_ft2
    charge_area_m2 = charge_area_ft2 * FT2_TO_M2

    # Area price by chosen unit rate
    if price_per_sqft > 0:
        area_price = charge_area_ft2 * price_per_sqft
        area_rate_label = f"${price_per_sqft:.2f}/ft^2"
    elif price_per_sqm > 0:
        area_price = charge_area_m2 * price_per_sqm
        area_rate_label = f"${price_per_sqm:.2f}/m^2"
    else:
        area_price = 0.0
        area_rate_label = "(no area rate)"

    # Sheets cost
    sheets_cost = sheets * cost_per_sheet

    # Pot lights
    pot_lights_total = pot_light_count * pot_light_cost

    # Subtotals / tax / cash
    subtotal_no_tax = area_price + sheets_cost + pot_lights_total
    total_with_tax = subtotal_no_tax * (1.0 + tax_pct / 100.0) if tax_pct > 0 else subtotal_no_tax
    cash_price = subtotal_no_tax  # as requested: cash price (no tax)

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Chargeable area (ft^2)", f"{charge_area_ft2:,.2f}")
    p2.metric("Chargeable area (m^2)", f"{charge_area_m2:,.2f}")
    p3.metric("Area price", f"${area_price:,.2f}")
    p4.metric("Sheets cost", f"${sheets_cost:,.2f}")

    st.write(f"Area rate used: **{area_rate_label}**")
    st.write(f"Pot lights: **{pot_light_count} x ${pot_light_cost:,.2f} = ${pot_lights_total:,.2f}**")
    st.success(f"Subtotal (no tax): ${subtotal_no_tax:,.2f} | Total with tax ({tax_pct:.1f}%): ${total_with_tax:,.2f} | Cash price: ${cash_price:,.2f}")

    # ---------- Downloads ----------
    st.markdown("### Downloads")
    df_display = df[show_cols]
    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV (per-room)", csv, file_name="drywall_per_room.csv", mime="text/csv")

    # TXT Summary
    lines = ["Drywall Estimator Summary (per room)"]
    for _, r in df.iterrows():
        lines.append(f"- {r['room']}: Walls {r['wall_area_net_ft2']:.2f} ft^2, Ceiling {r['ceiling_area_ft2']:.2f} ft^2, Total {r['total_area_ft2']:.2f} ft^2 ({r['total_area_ft2']*FT2_TO_M2:.2f} m^2)")
    lines += [
        "",
        f"Grand Total: {total_ft2:.2f} ft^2 ({total_m2:.2f} m^2)",
        f"Grand Total w/ waste: {total_waste_ft2:.2f} ft^2 ({total_waste_m2:.2f} m^2)",
        "",
        "Material Takeoff:",
        f"- Board: {total_waste_ft2:,.0f} ft^2 → {sheets} sheets ({sheet_size})",
        f"- Mud: {mud_gal:,.1f} gal (~{mud_pails} pails @ {mud_pail_gal:g} gal)",
        f"- Tape: {tape_rolls} rolls (≈ {int(tape_sqft_per_roll)} ft^2/roll)",
        f"- Screws: {screws_qty:,} pcs (~{screws_boxes} boxes @ {screws_per_box} pcs)",
        f"- Corner bead: {corner_bead_pcs} pcs (~{corner_bead_lf:,.0f} lf, {corner_bead_piece_len_ft:g} ft pieces)",
    ]
    if include_resilient_channel:
        lines.append(f"- Resilient channel: {rc_pieces} pcs (~{rc_total_lf:,.0f} lf, {rc_piece_length_ft:g} ft pieces)")
    else:
        lines.append("- Resilient channel: not included")

    lines += [
        "",
        "Pricing:",
        f"- Chargeable area: {charge_area_ft2:.2f} ft^2 ({charge_area_m2:.2f} m^2)",
        f"- Area price ({area_rate_label}): ${area_price:,.2f}",
        f"- Sheets cost: ${sheets_cost:,.2f}",
        f"- Pot lights: {pot_light_count} x ${pot_light_cost:.2f} = ${pot_lights_total:,.2f}",
        f"- Subtotal (no tax): ${subtotal_no_tax:,.2f}",
        f"- Total with tax ({tax_pct:.1f}%): ${total_with_tax:,.2f}",
        f"- Cash price (no tax): ${cash_price:,.2f}",
    ]
    txt = "\n".join(lines)
    st.download_button("Download TXT (summary)", txt, file_name="drywall_summary.txt", mime="text/plain")

else:
    st.info("Add at least one room above to see results.")
