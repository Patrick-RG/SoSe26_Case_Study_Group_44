import base64
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_FILENAME = "SoSe26_Case_Study_finalData_Group_44.csv"
# Support both folder spellings so the app also runs on case-sensitive systems.
DATA_CANDIDATES = (BASE_DIR / "Data" / DATA_FILENAME, BASE_DIR / "data" / DATA_FILENAME)
DATA_PATH = next((path for path in DATA_CANDIDATES if path.exists()), DATA_CANDIDATES[0])
WWW_DIR = BASE_DIR / "www"
CSS_PATH = WWW_DIR / "styles.css"
FONT_DIR = WWW_DIR / "fonts"
LOGO_PATH = WWW_DIR / "images" / "group44_logo_icon.svg"

FONT_FILES = (
    ("SourceSansPro-Regular.ttf.woff2", 400),
    ("SourceSansPro-Semibold.ttf.woff2", 600),
    ("SourceSansPro-Bold.ttf.woff2", 700),
)

APP_TITLE = "Quality KPI Dashboard"
APP_SUBTITLE = "OEM process audit and defect-source analysis"
CHUNK_SIZE = 250_000

PRIMARY_BLUE = "#5DADE2"
DARK_BLUE = "#2471A3"
WHITE = "#FFFFFF"
TEXT = "#183B56"
GRID = "#E9F1F7"
AXIS = "#C9D9E5"

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "scrollZoom": True,
    "responsive": True,
}

FILTER_COLUMNS = [
    "OEM",
    "Vehicle_Type",
    "Vehicle_Production_Year",
    "OEM_Plant_Number",
    "OEM_Plant",
    "OEM_City",
]

COMPONENT_FIELDS = {
    "Type": "Component_Type",
    "Supplier_Plant_Number": "Supplier_Plant_Number",
    "Supplier_City": "Supplier_City",
    "Direct_Defect": "Direct_Defect",
    "Part_Defect": "Part_Defect",
    "Effective_Defect": "Effective_Defect",
}

COMPONENT_GROUP_COLUMNS = FILTER_COLUMNS + [
    "Component_Role",
    "Component_Type",
    "Supplier_Plant_Number",
    "Supplier_City",
]
ROLE_YEAR_GROUP_COLUMNS = FILTER_COLUMNS + ["Component_Role"]

PLANT_RAW_AGG = {
    "Vehicles": ("Vehicle_Effective_Defect", "size"),
    "Defective_Vehicles": ("Vehicle_Effective_Defect", "sum"),
}
COMPONENT_RAW_AGG = {
    "Installed_Components": ("Effective_Defect", "size"),
    "Direct_Defects": ("Direct_Defect", "sum"),
    "Part_Defects": ("Part_Defect", "sum"),
    "Effective_Defects": ("Effective_Defect", "sum"),
}
ROLE_YEAR_RAW_AGG = {
    "Installed_Components": ("Effective_Defect", "size"),
    "Effective_Defects": ("Effective_Defect", "sum"),
}

CITY_NAMES = {
    "NUERNBERG": "Nürnberg",
    "NURNBERG": "Nürnberg",
    "GOETTINGEN": "Göttingen",
    "GOTTINGEN": "Göttingen",
    "GÖTTINGEN": "Göttingen",
    "MUENCHEN": "München",
    "WUERZBURG": "Würzburg",
    "FUERTH": "Fürth",
}

ROLE_PALETTE = [
    "#0072B2",
    "#009E73",
    "#CC79A7",
    "#D55E00",
] + px.colors.qualitative.Safe
PLANT_PALETTE = px.colors.qualitative.Bold + px.colors.qualitative.Safe
LINE_DASHES = ("solid", "dash", "dot", "dashdot")
MARKER_SYMBOLS = ("circle", "square", "diamond", "triangle-up", "cross")



def configure_page():
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
    )


def load_css():
    if not CSS_PATH.exists():
        st.error(f"Stylesheet not found:\n\n{CSS_PATH}")
        st.stop()

    # Embed the bundled fonts so Source Sans Pro does not depend on the local machine.
    font_faces = []
    for filename, weight in FONT_FILES:
        path = FONT_DIR / filename
        if path.exists():
            font_faces.append(
                '@font-face {'
                'font-family: "Source Sans Pro";'
                f'src: url("data:font/woff2;base64,'
                f'{base64.b64encode(path.read_bytes()).decode("ascii")}") '
                'format("woff2");'
                f'font-weight: {weight};'
                'font-style: normal;'
                'font-display: swap;'
                '}'
            )

    css = CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{''.join(font_faces)}{css}</style>", unsafe_allow_html=True)


def ensure_data_exists():
    if not DATA_PATH.exists():
        st.error(f"Final dataset not found:\n\n{DATA_PATH}")
        st.stop()


def render_header():
    logo = LOGO_PATH.read_text(encoding="utf-8") if LOGO_PATH.exists() else ""
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-brand">
                <div class="app-logo">{logo}</div>
                <div class="app-heading">
                    <div class="app-title">{APP_TITLE}</div>
                    <div class="app-subtitle">{APP_SUBTITLE}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_text_block(css_class, text):
    st.markdown(f'<div class="{css_class}">{text}</div>', unsafe_allow_html=True)


def render_section_title(text):
    render_text_block("section-title", text)


def render_subsection_title(text):
    render_text_block("subsection-title", text)


def city_label(city):
    if pd.isna(city):
        return "Unknown"
    value = str(city).strip()
    return CITY_NAMES.get(value.upper(), value.title())


def plant_label(plant, city):
    return f"{plant} · {city_label(city)}"


def add_plant_labels(data):
    result = data.copy()
    result["Plant_Label"] = [
        plant_label(plant, city)
        for plant, city in zip(result["OEM_Plant"], result["OEM_City"])
    ]
    return result


def calculate_rate(defects, population):
    return defects / population * 100


def add_rates(data, denominator, rate_map):
    result = data.copy()
    for defect_column, rate_column in rate_map.items():
        result[rate_column] = calculate_rate(result[defect_column], result[denominator])
    return result


def group_aggregate(data, columns, aggregations):
    return data.groupby(columns, dropna=False, as_index=False).agg(**aggregations)


def sum_grouped(data, columns, values):
    names = values if not isinstance(values, dict) else values.keys()
    return group_aggregate(
        data,
        columns,
        {name: (name, "sum") for name in names},
    )


def role_source_columns(role):
    return FILTER_COLUMNS + [f"{role}_{suffix}" for suffix in COMPONENT_FIELDS]


def prepare_role_data(chunk, role):
    rename = {
        f"{role}_{suffix}": target for suffix, target in COMPONENT_FIELDS.items()
    }
    result = chunk[role_source_columns(role)].rename(columns=rename)
    result["Component_Role"] = role
    return result


# Component roles are read from the dataset structure instead of being hardcoded.
def discover_component_roles(columns):
    column_set = set(columns)
    roles = []
    suffix = "_Effective_Defect"
    for column in columns:
        if not column.endswith(suffix):
            continue
        role = column[: -len(suffix)]
        required = {f"{role}_{field}" for field in COMPONENT_FIELDS}
        if required.issubset(column_set) and role not in roles:
            roles.append(role)
    return roles


@st.cache_data(show_spinner=False)
def load_schema():
    columns = pd.read_csv(DATA_PATH, nrows=0).columns.tolist()
    roles = discover_component_roles(columns)
    if not roles:
        raise ValueError("No component roles could be identified in the final dataset.")
    return columns, roles


def analysis_columns(roles):
    role_columns = [
        column
        for role in roles
        for column in role_source_columns(role)[len(FILTER_COLUMNS):]
    ]
    return FILTER_COLUMNS + ["Vehicle_Effective_Defect"] + role_columns


def defect_columns(roles):
    return ["Vehicle_Effective_Defect"] + [
        f"{role}_{kind}_Defect"
        for role in roles
        for kind in ("Direct", "Part", "Effective")
    ]


# Cache the prepared summaries so changing filters does not make the app reread the full CSV.
@st.cache_data(show_spinner="Preparing dashboard data...")
def load_dashboard_data():
    _, roles = load_schema()
    plant_parts, component_parts, role_year_parts = [], [], []

    # The final dataset is large, so only the columns needed for the dashboard are read in chunks.
    for chunk in pd.read_csv(
        DATA_PATH,
        usecols=analysis_columns(roles),
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        chunk["Vehicle_Production_Year"] = pd.to_numeric(
            chunk["Vehicle_Production_Year"], errors="coerce"
        )
        # Normalizing defect flags to 0/1 keeps the later sums and rates consistent.
        for column in defect_columns(roles):
            chunk[column] = (
                pd.to_numeric(chunk[column], errors="coerce")
                .eq(1)
                .astype("int8")
            )

        # Aggregate each chunk immediately so the full vehicle-level table never has to stay in memory.
        plant_parts.append(group_aggregate(chunk, FILTER_COLUMNS, PLANT_RAW_AGG))
        for role in roles:
            role_data = prepare_role_data(chunk, role)
            component_parts.append(
                group_aggregate(role_data, COMPONENT_GROUP_COLUMNS, COMPONENT_RAW_AGG)
            )
            role_year_parts.append(
                group_aggregate(role_data, ROLE_YEAR_GROUP_COLUMNS, ROLE_YEAR_RAW_AGG)
            )

    plant = sum_grouped(
        pd.concat(plant_parts, ignore_index=True),
        FILTER_COLUMNS,
        PLANT_RAW_AGG,
    )
    component = sum_grouped(
        pd.concat(component_parts, ignore_index=True),
        COMPONENT_GROUP_COLUMNS,
        COMPONENT_RAW_AGG,
    )
    role_year = sum_grouped(
        pd.concat(role_year_parts, ignore_index=True),
        ROLE_YEAR_GROUP_COLUMNS,
        ROLE_YEAR_RAW_AGG,
    )
    return plant, component, role_year, roles


# The Final Data page reads only the requested slice instead of loading all rows into the browser.
@st.cache_data(show_spinner=False)
def load_raw_page(start, rows):
    columns, _ = load_schema()
    return pd.read_csv(
        DATA_PATH,
        skiprows=start + 1,
        nrows=rows,
        header=None,
        names=columns,
        low_memory=False,
    )


def role_colors(roles):
    return {
        role: ROLE_PALETTE[index % len(ROLE_PALETTE)]
        for index, role in enumerate(roles)
    }


def plant_styles(plants):
    return {
        plant: {
            "dash": LINE_DASHES[index % len(LINE_DASHES)],
            "symbol": MARKER_SYMBOLS[index % len(MARKER_SYMBOLS)],
        }
        for index, plant in enumerate(sorted(plants))
    }


def style_figure(fig, height=340):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=WHITE,
        plot_bgcolor=WHITE,
        font=dict(family="Source Sans Pro", color=TEXT, size=13),
        title=None,
        height=height,
        margin=dict(l=50, r=35, t=20, b=45),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor=WHITE,
            font_family="Source Sans Pro",
            font_color=TEXT,
        ),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS)
    return fig


def set_rate_axis(fig, title="Defect Rate [%]", autoscale=False):
    if autoscale:
        fig.update_yaxes(title=title, autorange=True)
    else:
        fig.update_yaxes(title=title, range=[0, 100], dtick=20)


def set_year_axis(fig):
    fig.update_xaxes(title="Production Year", dtick=1)


def set_vertical_legend(fig, title):
    fig.update_layout(
        legend=dict(
            title=title,
            orientation="v",
            x=1.01,
            xanchor="left",
            y=1,
            yanchor="top",
        )
    )


def show_plot(fig):
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG)


def render_chart_pair(left_title, left_fig, right_title, right_fig):
    for column, (title, figure) in zip(
        st.columns(2),
        ((left_title, left_fig), (right_title, right_fig)),
    ):
        with column:
            render_section_title(title)
            show_plot(figure)


def render_metric_row(metrics):
    for column, metric in zip(st.columns(len(metrics)), metrics):
        label, value, *delta = metric
        column.metric(label, value, delta[0] if delta else None)


def render_navigation():
    return st.segmented_control(
        "Section",
        options=["Overview", "Defect Analysis", "Final Data"],
        default="Overview",
        label_visibility="collapsed",
        width="stretch",
    )


def get_filter_options(plant_summary):
    plant_lookup = (
        plant_summary[["OEM_Plant", "OEM_City"]]
        .drop_duplicates()
        .sort_values("OEM_Plant")
    )
    years = sorted(
        plant_summary["Vehicle_Production_Year"].dropna().astype(int).unique().tolist()
    )
    return {
        "oems": sorted(plant_summary["OEM"].dropna().unique().tolist()),
        "vehicle_types": sorted(
            plant_summary["Vehicle_Type"].dropna().unique().tolist()
        ),
        "plants": plant_lookup["OEM_Plant"].tolist(),
        "plant_labels": {
            row.OEM_Plant: plant_label(row.OEM_Plant, row.OEM_City)
            for row in plant_lookup.itertuples(index=False)
        },
        "year_range": (min(years), max(years)),
    }


def render_filters(plant_summary):
    options = get_filter_options(plant_summary)
    min_year, max_year = options["year_range"]
    col1, col2, col3, col4 = st.columns([1, 1, 1.4, 1.5])

    with col1:
        oems = st.multiselect("OEM", options["oems"], placeholder="All OEMs")
    with col2:
        vehicle_types = st.multiselect(
            "Vehicle Type", options["vehicle_types"], placeholder="All vehicle types"
        )
    with col3:
        plants = st.multiselect(
            "Production Plant",
            options["plants"],
            placeholder="All production plants",
            format_func=lambda value: options["plant_labels"].get(value, str(value)),
        )
    with col4:
        year_range = st.slider(
            "Production Year",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
            step=1,
        )

    return {
        "oems": oems,
        "vehicle_types": vehicle_types,
        "plants": plants,
        "year_range": year_range,
    }


def apply_filters(data, filters):
    # An empty multiselect means "All", so that field is only filtered after a user makes a selection.
    mask = pd.Series(True, index=data.index)
    mappings = {
        "oems": "OEM",
        "vehicle_types": "Vehicle_Type",
        "plants": "OEM_Plant",
    }
    for filter_name, column in mappings.items():
        if filters[filter_name]:
            mask &= data[column].isin(filters[filter_name])

    start_year, end_year = filters["year_range"]
    mask &= data["Vehicle_Production_Year"].between(
        start_year, end_year, inclusive="both"
    )
    return data.loc[mask].copy()


def summarize_vehicle(data, group_columns):
    result = sum_grouped(data, group_columns, ["Vehicles", "Defective_Vehicles"])
    result = add_rates(result, "Vehicles", {"Defective_Vehicles": "Defect_Rate"})
    return add_plant_labels(result)


def make_plant_kpi(data):
    return summarize_vehicle(
        data,
        ["OEM", "OEM_Plant_Number", "OEM_Plant", "OEM_City"],
    )


# Calculate the yearly rates from each year's own production volume.
def aggregate_yearly_vehicle(data):
    return summarize_vehicle(
        data,
        ["Vehicle_Production_Year", "OEM_Plant", "OEM_City"],
    )


# Effective component defects use the final effective flag, which already includes direct and part-derived defects.
def aggregate_component_quality(data):
    result = sum_grouped(
        data,
        ["Component_Role"],
        ["Installed_Components", "Direct_Defects", "Part_Defects", "Effective_Defects"],
    )
    return add_rates(
        result,
        "Installed_Components",
        {
            "Direct_Defects": "Direct_Rate",
            "Part_Defects": "Part_Rate",
            "Effective_Defects": "Effective_Rate",
        },
    )


# Use the component's own effective defect counts here, not the overall vehicle defect flag.
def aggregate_component_trend(data):
    result = sum_grouped(
        data,
        ["Vehicle_Production_Year", "OEM_Plant", "OEM_City", "Component_Role"],
        ["Installed_Components", "Effective_Defects"],
    )
    result = add_rates(
        result,
        "Installed_Components",
        {"Effective_Defects": "Effective_Defect_Rate"},
    )
    return add_plant_labels(result)


def aggregate_component_by_plant(data):
    result = sum_grouped(
        data,
        ["Component_Role", "OEM_Plant", "OEM_City"],
        ["Installed_Components", "Effective_Defects"],
    )
    result = add_rates(
        result,
        "Installed_Components",
        {"Effective_Defects": "Effective_Defect_Rate"},
    )
    return add_plant_labels(result)


# Summarize each Tier-1 plant by component type before comparing supplier defect rates.
def aggregate_supplier_quality(data):
    result = sum_grouped(
        data,
        ["Supplier_Plant_Number", "Supplier_City", "Component_Type"],
        ["Installed_Components", "Direct_Defects", "Part_Defects", "Effective_Defects"],
    )
    result = add_rates(
        result,
        "Installed_Components",
        {
            "Direct_Defects": "Direct_Rate",
            "Part_Defects": "Part_Rate",
            "Effective_Defects": "Effective_Rate",
        },
    )
    result["Supplier_Label"] = [
        plant_label(plant, city)
        for plant, city in zip(result["Supplier_Plant_Number"], result["Supplier_City"])
    ]
    return result


# Use the count to see where most defective vehicles come from and the rate to compare plants with different production volumes.
def make_plant_bar_chart(data, rate=False):
    if rate:
        value = "Defect_Rate"
        custom = ["OEM", "Vehicles", "Defective_Vehicles"]
        color = DARK_BLUE
        text_template = "%{text:.2f}%"
        hover = (
            "<b>%{x}</b><br>OEM: %{customdata[0]}<br>"
            "Vehicles: %{customdata[1]:,.0f}<br>"
            "Defective vehicles: %{customdata[2]:,.0f}<br>"
            "Defect rate: %{y:.2f}%<extra></extra>"
        )
    else:
        value = "Defective_Vehicles"
        custom = ["OEM", "Vehicles", "Defect_Rate"]
        color = PRIMARY_BLUE
        text_template = "%{text:,.0f}"
        hover = (
            "<b>%{x}</b><br>OEM: %{customdata[0]}<br>"
            "Vehicles: %{customdata[1]:,.0f}<br>"
            "Defective vehicles: %{y:,.0f}<br>"
            "Defect rate: %{customdata[2]:.2f}%<extra></extra>"
        )

    fig = px.bar(
        data.sort_values(value, ascending=False),
        x="Plant_Label",
        y=value,
        text=value,
        custom_data=custom,
        color_discrete_sequence=[color],
    )
    fig.update_traces(
        texttemplate=text_template,
        textposition="outside",
        cliponaxis=False,
        hovertemplate=hover,
    )
    fig.update_xaxes(title="Production Plant")
    if rate:
        set_rate_axis(fig)
    else:
        fig.update_yaxes(title="Defective Vehicles", rangemode="tozero")
    return style_figure(fig)


def make_vehicle_trend_chart(data, rate=False):
    if rate:
        value = "Defect_Rate"
        custom = ["Vehicles", "Defective_Vehicles"]
        y_title = "Defect Rate [%]"
        hover = (
            "<b>%{fullData.name}</b><br>Production year: %{x:.0f}<br>"
            "Effective vehicle defect rate: %{y:.2f}%<br>"
            "Vehicles: %{customdata[0]:,.0f}<br>"
            "Defective vehicles: %{customdata[1]:,.0f}<extra></extra>"
        )
    else:
        value = "Defective_Vehicles"
        custom = ["Vehicles", "Defect_Rate"]
        y_title = "Defective Vehicles"
        hover = (
            "<b>%{fullData.name}</b><br>Production year: %{x:.0f}<br>"
            "Defective vehicles: %{y:,.0f}<br>"
            "Vehicles: %{customdata[0]:,.0f}<br>"
            "Defect rate: %{customdata[1]:.2f}%<extra></extra>"
        )

    fig = px.line(
        data.sort_values("Vehicle_Production_Year"),
        x="Vehicle_Production_Year",
        y=value,
        color="Plant_Label",
        markers=True,
        custom_data=custom,
        labels={
            "Vehicle_Production_Year": "Production Year",
            value: y_title,
            "Plant_Label": "Production Plant",
        },
    )
    fig.update_traces(hovertemplate=hover)
    set_year_axis(fig)
    if rate:
        set_rate_axis(fig, autoscale=True)
    else:
        fig.update_yaxes(title=y_title, rangemode="tozero")
    return style_figure(fig, height=390)


def make_effective_component_chart(data, roles):
    fig = px.bar(
        data.sort_values("Effective_Rate", ascending=False),
        x="Component_Role",
        y="Effective_Rate",
        text="Effective_Rate",
        custom_data=["Installed_Components", "Effective_Defects"],
        color="Component_Role",
        color_discrete_map=role_colors(roles),
    )
    fig.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>Installed components: %{customdata[0]:,.0f}<br>"
            "Effective defects: %{customdata[1]:,.0f}<br>"
            "Effective defect rate: %{y:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title="Component")
    set_rate_axis(fig)
    return style_figure(fig)


def make_defect_source_chart(data):
    source_data = data[["Component_Role", "Direct_Rate", "Part_Rate"]].melt(
        id_vars="Component_Role",
        var_name="Defect Source",
        value_name="Defect Rate",
    )
    source_data["Defect Source"] = source_data["Defect Source"].replace(
        {
            "Direct_Rate": "Direct Component Defect",
            "Part_Rate": "Part-Derived Defect",
        }
    )
    fig = px.bar(
        source_data,
        x="Component_Role",
        y="Defect Rate",
        color="Defect Source",
        barmode="group",
        color_discrete_map={
            "Direct Component Defect": "#9CCFF0",
            "Part-Derived Defect": DARK_BLUE,
        },
    )
    fig.update_traces(
        hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.2f}%<extra></extra>"
    )
    fig.update_xaxes(title="Component")
    set_rate_axis(fig)
    return style_figure(fig)


def ordered_labels(data, key_column, label_column):
    return (
        data[[key_column, label_column]]
        .drop_duplicates()
        .sort_values(key_column)[label_column]
        .tolist()
    )


def make_component_plant_chart(data, roles):
    fig = px.bar(
        data,
        x="Component_Role",
        y="Effective_Defect_Rate",
        color="Plant_Label",
        barmode="group",
        text="Effective_Defect_Rate",
        custom_data=["Installed_Components", "Effective_Defects", "OEM_Plant"],
        category_orders={
            "Component_Role": roles,
            "Plant_Label": ordered_labels(data, "OEM_Plant", "Plant_Label"),
        },
        labels={
            "Component_Role": "Component",
            "Effective_Defect_Rate": "Defect Rate [%]",
            "Plant_Label": "Production Plant",
        },
    )
    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>%{fullData.name}<br>"
            "Effective defect rate: %{y:.2f}%<br>"
            "Installed components: %{customdata[0]:,.0f}<br>"
            "Effective defects: %{customdata[1]:,.0f}<extra></extra>"
        ),
    )
    fig.update_xaxes(title="Component")
    set_rate_axis(fig)
    set_vertical_legend(fig, "Production Plant")
    return style_figure(fig, height=440)


def make_component_year_chart(data, selected_component, roles):
    fig = go.Figure()
    color = role_colors(roles)[selected_component]
    plants = sorted(data["OEM_Plant"].dropna().astype(str).unique().tolist())
    styles = plant_styles(plants)

    for plant in plants:
        subset = data[data["OEM_Plant"].astype(str).eq(plant)].sort_values(
            "Vehicle_Production_Year"
        )
        if subset.empty:
            continue
        label = plant_label(plant, subset["OEM_City"].iloc[0])
        fig.add_trace(
            go.Scatter(
                x=subset["Vehicle_Production_Year"],
                y=subset["Effective_Defect_Rate"],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2.8, dash=styles[plant]["dash"]),
                marker=dict(color=color, size=8, symbol=styles[plant]["symbol"]),
                customdata=list(
                    zip(subset["Installed_Components"], subset["Effective_Defects"])
                ),
                hovertemplate=(
                    f"<b>{label}</b><br>Production year: %{{x:.0f}}<br>"
                    "Effective defect rate: %{y:.2f}%<br>"
                    "Installed components: %{customdata[0]:,.0f}<br>"
                    "Effective defects: %{customdata[1]:,.0f}<extra></extra>"
                ),
            )
        )

    set_vertical_legend(fig, "Production Plant")
    set_year_axis(fig)
    set_rate_axis(fig, autoscale=True)
    return style_figure(fig, height=440)


# Not every Tier-1 plant supplies every component type, so existing bars are centered without (preventing ugly empty slots).
def build_sparse_supplier_positions(data, bar_width=0.18):
    plot_data = data.sort_values(["Component_Type", "Supplier_Label"]).copy()
    component_types = plot_data["Component_Type"].dropna().astype(str).unique().tolist()
    supplier_labels = plot_data["Supplier_Label"].dropna().astype(str).unique().tolist()
    centers = {component: index for index, component in enumerate(component_types)}

    plot_data["Component_Type"] = plot_data["Component_Type"].astype(str)
    plot_data["Group_Size"] = (
        plot_data.groupby("Component_Type")["Component_Type"].transform("size")
    )
    plot_data["Group_Index"] = plot_data.groupby("Component_Type").cumcount()
    plot_data["Plot_X"] = (
        plot_data["Component_Type"].map(centers)
        + (plot_data["Group_Index"] - (plot_data["Group_Size"] - 1) / 2) * bar_width
    )
    return plot_data, component_types, supplier_labels, centers


def make_supplier_chart(data):
    bar_width = 0.18
    plot_data, component_types, suppliers, centers = build_sparse_supplier_positions(
        data, bar_width
    )
    colors = {
        supplier: PLANT_PALETTE[index % len(PLANT_PALETTE)]
        for index, supplier in enumerate(suppliers)
    }
    fig = go.Figure()

    for supplier in suppliers:
        subset = plot_data[plot_data["Supplier_Label"].eq(supplier)]
        fig.add_trace(
            go.Bar(
                x=subset["Plot_X"],
                y=subset["Effective_Rate"],
                width=bar_width * 0.9,
                name=supplier,
                marker_color=colors[supplier],
                text=subset["Effective_Rate"],
                texttemplate="%{text:.1f}%",
                textposition="outside",
                cliponaxis=False,
                customdata=list(
                    zip(
                        subset["Component_Type"],
                        subset["Installed_Components"],
                        subset["Direct_Defects"],
                        subset["Part_Defects"],
                        subset["Effective_Defects"],
                        subset["Direct_Rate"],
                        subset["Part_Rate"],
                    )
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    f"Tier-1 plant: {supplier}<br>"
                    "Installed components: %{customdata[1]:,.0f}<br>"
                    "Direct defects: %{customdata[2]:,.0f}<br>"
                    "Part-derived defects: %{customdata[3]:,.0f}<br>"
                    "Effective defects: %{customdata[4]:,.0f}<br>"
                    "Direct defect rate: %{customdata[5]:.2f}%<br>"
                    "Part-derived rate: %{customdata[6]:.2f}%<br>"
                    "Effective defect rate: %{y:.2f}%<extra></extra>"
                ),
            )
        )

    fig.update_xaxes(
        title="Component Type",
        tickmode="array",
        tickvals=[centers[component] for component in component_types],
        ticktext=component_types,
        range=[-0.6, len(component_types) - 0.4],
    )
    set_rate_axis(fig, title="Effective Defect Rate [%]")
    fig.update_layout(barmode="overlay", bargap=0)
    set_vertical_legend(fig, "Tier-1 Plant")
    return style_figure(fig, height=400)


def format_table(data, columns, rename=None, rates=None, sort_by=None):
    table = data[columns].copy()
    if rename:
        table = table.rename(columns=rename)
    if rates:
        table[rates] = table[rates].round(2)
    if sort_by:
        table = table.sort_values(sort_by, ascending=False)
    return table


def format_plant_kpi_table(data):
    return format_table(
        data,
        [
            "OEM",
            "OEM_Plant_Number",
            "Plant_Label",
            "Vehicles",
            "Defective_Vehicles",
            "Defect_Rate",
        ],
        rename={
            "OEM_Plant_Number": "Plant Number",
            "Plant_Label": "Production Plant",
            "Defect_Rate": "Defect Rate [%]",
        },
        rates=["Defect Rate [%]"],
    )


def format_supplier_table(data):
    rate_columns = [
        "Direct Defect Rate [%]",
        "Part-Derived Rate [%]",
        "Effective Defect Rate [%]",
    ]
    return format_table(
        data,
        [
            "Supplier_Plant_Number",
            "Supplier_City",
            "Component_Type",
            "Installed_Components",
            "Direct_Defects",
            "Direct_Rate",
            "Part_Defects",
            "Part_Rate",
            "Effective_Defects",
            "Effective_Rate",
        ],
        rename={
            "Supplier_Plant_Number": "Tier-1 Plant",
            "Supplier_City": "City",
            "Component_Type": "Component Type",
            "Installed_Components": "Installed Components",
            "Direct_Rate": rate_columns[0],
            "Part_Rate": rate_columns[1],
            "Effective_Rate": rate_columns[2],
        },
        rates=rate_columns,
        sort_by=rate_columns[2],
    )


def leader(data, column):
    return data.loc[data[column].idxmax()]


def render_overview_metrics(plant_kpi):
    absolute = leader(plant_kpi, "Defective_Vehicles")
    relative = leader(plant_kpi, "Defect_Rate")
    render_metric_row(
        [
            ("Vehicles Analyzed", f"{int(plant_kpi['Vehicles'].sum()):,}"),
            ("Defective Vehicles", f"{int(plant_kpi['Defective_Vehicles'].sum()):,}"),
            (
                "Highest Absolute Defect Count",
                city_label(absolute["OEM_City"]),
                f"{int(absolute['Defective_Vehicles']):,}",
            ),
            (
                "Highest Relative Defect Rate",
                city_label(relative["OEM_City"]),
                f"{relative['Defect_Rate']:.2f}%",
            ),
        ]
    )
    return absolute, relative


# The recommendation prioritizes relative defect rate and at the same time still showing the plant with the largest absolute defect.
def render_audit_recommendation(absolute, relative):
    recommended = plant_label(relative["OEM_Plant"], relative["OEM_City"])
    absolute_label = plant_label(absolute["OEM_Plant"], absolute["OEM_City"])
    st.markdown(
        f"""
        <div class="recommendation-box">
            <div class="recommendation-title">Audit Recommendation</div>
            <b>{recommended}</b> has the highest effective relative defect rate at
            <b>{relative['Defect_Rate']:.2f}%</b> and therefore has the highest
            process-audit priority within the selected data. <b>{absolute_label}</b>
            has the largest absolute field-quality burden with
            <b>{int(absolute['Defective_Vehicles']):,}</b> defective vehicles.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(plant_data):
    if plant_data.empty:
        st.warning("No data match the selected filters.")
        return

    plant_kpi = make_plant_kpi(plant_data)
    absolute, relative = render_overview_metrics(plant_kpi)
    render_chart_pair(
        "Absolute Defect Frequency by Plant",
        make_plant_bar_chart(plant_kpi),
        "Relative Defect Rate by Plant",
        make_plant_bar_chart(plant_kpi, rate=True),
    )
    render_audit_recommendation(absolute, relative)

    render_subsection_title("Vehicle Defect Development over Production Years")
    yearly = aggregate_yearly_vehicle(plant_data)
    render_chart_pair(
        "Effective Vehicle Defect Rate by Production Year",
        make_vehicle_trend_chart(yearly, rate=True),
        "Defective Vehicles by Production Year",
        make_vehicle_trend_chart(yearly),
    )

    with st.expander("Production Plant KPI Table"):
        st.dataframe(
            format_plant_kpi_table(plant_kpi),
            hide_index=True,
            width="stretch",
        )


def select_component_data(component_data, role_year_data, selected_component):
    if selected_component == "All Components":
        return component_data.copy(), role_year_data.copy()
    mask = component_data["Component_Role"].eq(selected_component)
    trend_mask = role_year_data["Component_Role"].eq(selected_component)
    return component_data.loc[mask].copy(), role_year_data.loc[trend_mask].copy()


def render_component_metrics(component_quality, selected_component):
    if selected_component == "All Components":
        metrics = []
        for label, column in (
            ("Highest Effective Defect Rate", "Effective_Rate"),
            ("Highest Direct Defect Rate", "Direct_Rate"),
            ("Highest Part-Derived Rate", "Part_Rate"),
        ):
            row = leader(component_quality, column)
            metrics.append((label, row["Component_Role"], f"{row[column]:.2f}%"))
    else:
        row = component_quality.iloc[0]
        metrics = [
            ("Effective Defect Rate", f"{row['Effective_Rate']:.2f}%"),
            ("Direct Defect Rate", f"{row['Direct_Rate']:.2f}%"),
            ("Part-Derived Defect Rate", f"{row['Part_Rate']:.2f}%"),
        ]
    render_metric_row(metrics)


def render_component_summary_charts(component_quality, roles):
    render_chart_pair(
        "Effective Defect Rate",
        make_effective_component_chart(component_quality, roles),
        "Direct vs Part-Derived Defects",
        make_defect_source_chart(component_quality),
    )


def render_component_development(trend_source, selected_component, roles):
    trend_data = aggregate_component_trend(trend_source)
    if selected_component == "All Components":
        render_subsection_title("Component Comparison")
        render_section_title(
            "Effective Component Defect Rate by Component and Production Plant"
        )
        component_plant = aggregate_component_by_plant(trend_source)
        show_plot(make_component_plant_chart(component_plant, roles))
        return

    render_subsection_title("Defect Development over Production Years")
    render_section_title(
        f"{selected_component} Effective Defect Rate by Production Year"
    )
    show_plot(make_component_year_chart(trend_data, selected_component, roles))
    rate = calculate_rate(
        trend_data["Effective_Defects"].sum(),
        trend_data["Installed_Components"].sum(),
    )
    st.caption(
        f"Selected-period {selected_component.lower()} "
        f"effective defect rate: {rate:.2f}%"
    )


def render_supplier_drilldown(defect_data, selected_component):
    render_subsection_title("Tier-1 Supplier Drill-down")
    if selected_component == "All Components":
        st.info("Select one component to inspect its Tier-1 supplier plants.")
        return

    supplier_quality = aggregate_supplier_quality(defect_data)
    worst = leader(supplier_quality, "Effective_Rate")
    render_metric_row(
        [
            ("Highest-Rate Tier-1 Plant", worst["Supplier_Label"]),
            ("Effective Defect Rate", f"{worst['Effective_Rate']:.2f}%"),
        ]
    )
    render_section_title(
        f"{selected_component} Defect Rate by Component Type and Tier-1 Plant"
    )
    show_plot(make_supplier_chart(supplier_quality))
    with st.expander("Tier-1 Supplier KPI Table"):
        st.dataframe(
            format_supplier_table(supplier_quality),
            hide_index=True,
            width="stretch",
        )


def render_defect_analysis(component_data, role_year_data, roles):
    if component_data.empty:
        st.warning("No data match the selected filters.")
        return

    selector_col, _ = st.columns([1, 3])
    with selector_col:
        selected_component = st.selectbox(
            "Component Focus", options=["All Components", *roles]
        )

    defect_data, trend_source = select_component_data(
        component_data, role_year_data, selected_component
    )
    if defect_data.empty:
        st.warning("No component data match the selected filters.")
        return

    component_quality = aggregate_component_quality(defect_data)
    render_component_metrics(component_quality, selected_component)
    render_component_summary_charts(component_quality, roles)
    render_component_development(trend_source, selected_component, roles)
    render_supplier_drilldown(defect_data, selected_component)


def calculate_pagination(total_rows, page_size, page):
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    start_row = (int(page) - 1) * page_size
    return total_pages, start_row, min(start_row + page_size, total_rows)


# Paginating the complete final dataset to avoid rendering millions of rows at once.
def render_final_data(plant_summary):
    render_section_title("Final Dataset")
    render_text_block(
        "section-description",
        "Browse the complete final dataset used by the application.",
    )
    total_rows = int(plant_summary["Vehicles"].sum())
    col1, col2, _ = st.columns([1, 1, 2])

    with col1:
        page_size = st.selectbox("Rows per page", [100, 500, 1000, 5000], index=1)
    total_pages, _, _ = calculate_pagination(total_rows, page_size, 1)
    with col2:
        page = st.number_input(
            "Page", min_value=1, max_value=total_pages, value=1, step=1
        )

    _, start_row, end_row = calculate_pagination(total_rows, page_size, page)
    st.caption(f"Showing rows {start_row + 1:,}–{end_row:,} of {total_rows:,}")
    st.dataframe(
        load_raw_page(start_row, page_size),
        hide_index=True,
        width="stretch",
        height=650,
    )


def load_dashboard_or_stop():
    try:
        return load_dashboard_data()
    except Exception as error:
        st.error(f"Dashboard data could not be prepared: {error}")
        st.stop()


# Main app flow: load cached summaries, apply global filters, then render only the selected section.
def main():
    configure_page()
    ensure_data_exists()
    load_css()
    render_header()

    (
        plant_summary,
        component_summary,
        role_year_summary,
        roles,
    ) = load_dashboard_or_stop()
    section = render_navigation()

    if section == "Final Data":
        render_final_data(plant_summary)
        return

    filters = render_filters(plant_summary)
    plant_data = apply_filters(plant_summary, filters)
    component_data = apply_filters(component_summary, filters)
    role_year_data = apply_filters(role_year_summary, filters)

    if section == "Overview":
        render_overview(plant_data)
    else:
        render_defect_analysis(component_data, role_year_data, roles)


if __name__ == "__main__":
    main()
