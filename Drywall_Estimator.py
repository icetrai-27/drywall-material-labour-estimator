# drywall_estimator_app.py
# Standalone Streamlit app to estimate drywall surface area per room (walls + optional ceiling),
# with per-room exclusions for windows and doors. Outputs SQFT & SQM, per-room breakdown,
# grand totals, optional waste %, and CSV/TXT downloads.

import streamlit as st
import pandas as pd

FT2_TO_M2 = 0.09290304

st.set_page_config(page_title="Drywall Estimator", page_icon="🧱", layout="wide")
st.title("🧱 Drywall Estimator (per room)")
st.caption("Calculate drywall surface areas for walls and ceilings, with openings deducted — exports SQFT & SQM.")

with st.sidebar:
    st.header("Options")
    include_waste = st.checkbox("Add waste percentage", value=True)
    waste_pct = (
        st.number_input(
            "Waste %",
            min_value=0.0,
            max_value=50.0,
            value=10.0,
            step=0.5,
            help="Applied to wall + ceiling net areas",
        )
        if include_waste
        else 0.0
    )
    show_intermediate = st.checkbox("Show intermediate math", value=False)

st.markdown("---")

# ===== Room inputs =====
col_l, col_r = st.columns([1, 1])
with col_l:
    room_count = st.number_input("Number of rooms", min_value=1, max_value=50, value=3, step=1)
with col_r:
    default_wall_h = st.number_input("Default wall height (ft)", min_value=0.0, value=8.0, step=0.1)

rooms_data = []

for i in range(int(room_count)):
    st.subheader(f"Room {i+1}")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 1])
        with c1:
            name = st.text_input(f"Room name #{i+1}", value=f"Room {i+1}", key=f"name_{i}")
        with c2:
            length = st.number_input(f"Length (ft) #{i+1}", min_value=0.0, step=0.1, key=f"len_{i}")
        with c3:
            width = st.number_input(f"Width (ft) #{i+1}", min_value=0.0, step=0.1, key=f"wid_{i}")
        with c4:
            height = st.number_input(
                f"Wall height (ft) #{i+1}", min_value=0.0, step=0.1, value=default_wall_h, key=f"h_{i}"
            )

        c5, c6, c7 = st.columns([1, 1, 1])
        with c5:
            include_ceiling = st.checkbox(f"Include ceiling? #{i+1}", value=True, key=f"ceil_inc_{i}")
        with c6:
            num_windows = st.number_input(
                f"Windows (count) #{i+1}", min_value=0, max_value=20, value=0, step=1, key=f"w_count_{i}"
            )
        with c7:
            num_doors = st.number_input(
                f"Doors (count) #{i+1}", min_value=0, max_value=20, value=0, step=1, key=f"d_count_{i}"
            )

        # Openings - windows
        windows = []
        if num_windows > 0:
            st.markdown("**Windows**")
            for w in range(num_windows):
                wc1, wc2 = st.columns(2)
                with wc1:
                    w_w = st.number_input(
                        f"Window {w+1} width (ft) [R{i+1}]", min_value=0.0, step=0.1, key=f"win_w_{i}_{w}"
                    )
                with wc2:
                    w_h = st.number_input(
                        f"Window {w+1} height (ft) [R{i+1}]", min_value=0.0, step=0.1, key=f"win_h_{i}_{w}"
                    )
                windows.append((w_w, w_h))

        # Openings - doors
        doors = []
        if num_doors > 0:
            st.markdown("**Doors**")
            for d in range(num_doors):
                dc1, dc2 = st.columns(2)
                with dc1:
                    d_w = st.number_input(
                        f"Door {d+1} width (ft) [R{i+1}]", min_value=0.0, step=0.1, key=f"door_w_{i}_{d}"
                    )
                with dc2:
                    d_h = st.number_input(
                        f"Door {d+1} height (ft) [R{i+1}]", min_value=0.0, step=0.1, key=f"door_h_{i}_{d}"
                    )
                doors.append((d_w, d_h))

        # --- Calculations ---
        perimeter = 2 * (length + width)
        wall_area_gross = perimeter * height
        openings_area = sum(w * h for w, h in windows) + sum(w * h for w, h in doors)
        wall_area_net = max(wall_area_gross - openings_area, 0.0)
        ceiling_area = (length * width) if include_ceiling else 0.0
        total_area_ft2 = wall_area_net + ceiling_area

        waste_multiplier = 1.0 + (waste_pct / 100.0)
        total_with_waste_ft2 = total_area_ft2 * waste_multiplier

        rooms_data.append(
            {
                "room": name,
                "length_ft": length,
                "width_ft": width,
                "height_ft": height,
                "perimeter_ft": perimeter,
                "wall_area_gross_ft2": wall_area_gross,
                "openings_area_ft2": openings_area,
                "wall_area_net_ft2": wall_area_net,
                "ceiling_area_ft2": ceiling_area,
                "total_area_ft2": total_area_ft2,
                "total_with_waste_ft2": total_with_waste_ft2,
            }
        )

        if show_intermediate:
            st.caption(
                f"Perimeter: {perimeter:.2f} ft | Wall gross: {wall_area_gross:.2f} ft² | "
                f"Openings: {openings_area:.2f} ft² | Net walls: {wall_area_net:.2f} ft² | "
                f"Ceiling: {ceiling_area:.2f} ft²"
            )

# ===== Summary table =====
if rooms_data:
    df = pd.DataFrame(rooms_data)
    # Add SQM columns
    df["total_area_m2"] = df["total_area_ft2"] * FT2_TO_M2
    df["total_with_waste_m2"] = df["total_with_waste_ft2"] * FT2_TO_M2

    # Display
    st.markdown("---")
    st.subheader("Per-room breakdown")
    show_cols = [
        "room",
        "length_ft",
        "width_ft",
        "height_ft",
        "wall_area_net_ft2",
        "ceiling_area_ft2",
        "total_area_ft2",
        "total_area_m2",
        "total_with_waste_ft2",
        "total_with_waste_m2",
    ]
    nice_names = {
        "room": "Room",
        "length_ft": "Length (ft)",
        "width_ft": "Width (ft)",
        "height_ft": "Height (ft)",
        "wall_area_net_ft2": "Walls (net) ft²",
        "ceiling_area_ft2": "Ceiling ft²",
        "total_area_ft2": "Total ft²",
        "total_area_m2": "Total m²",
        "total_with_waste_ft2": "Total w/ waste ft²",
        "total_with_waste_m2": "Total w/ waste m²",
    }
    df_display = df[show_cols].rename(columns=nice_names)
    st.dataframe(df_display, use_container_width=True)

    # Totals
    total_ft2 = float(df["total_area_ft2"].sum())
    total_m2 = total_ft2 * FT2_TO_M2
    total_waste_ft2 = float(df["total_with_waste_ft2"].sum())
    total_waste_m2 = total_waste_ft2 * FT2_TO_M2

    ctot1, ctot2, ctot3, ctot4 = st.columns(4)
    ctot1.metric("Grand Total (ft²)", f"{total_ft2:,.2f}")
    ctot2.metric("Grand Total (m²)", f"{total_m2:,.2f}")
    ctot3.metric("Grand Total w/ waste (ft²)", f"{total_waste_ft2:,.2f}")
    ctot4.metric("Grand Total w/ waste (m²)", f"{total_waste_m2:,.2f}")

    # Downloads
    st.markdown("### Downloads")
    csv = df_display.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV (per-room)", csv, file_name="drywall_per_room.csv", mime="text/csv")

    # Simple TXT summary
    lines = ["Drywall Estimator Summary (per room)"]
    for _, r in df.iterrows():
        lines.append(
            f"- {r['room']}: Walls {r['wall_area_net_ft2']:.2f} ft², Ceiling {r['ceiling_area_ft2']:.2f} ft², "
            f"Total {r['total_area_ft2']:.2f} ft² ({r['total_area_ft2']*FT2_TO_M2:.2f} m²)"
        )
    lines.append("")
    lines.append(f"Grand Total: {total_ft2:.2f} ft² ({total_m2:.2f} m²)")
    if include_waste:
        lines.append(
            f"Grand Total w/ {waste_pct:.1f}% waste: {total_waste_ft2:.2f} ft² ({total_waste_m2:.2f} m²)"
        )
    txt = "
".join(lines)
    st.download_button("Download TXT (summary)", txt, file_name="drywall_summary.txt", mime="text/plain")

else:
    st.info("Add at least one room above to see results.")
