from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Quality KPI Dashboard",
    layout="wide"
)


@st.cache_data(show_spinner="Loading quality data...")
def load_dashboard_data():
    path = Path("data/final/vehicle_quality.csv")

    parts = []

    for chunk in pd.read_csv(
        path,
        usecols=[
            "OEM",
            "Fahrzeugtyp",
            "Werksnummer_OEM",
            "ORT_OEM",
            "Produktionsdatum",
            "Fehlerhaft_Gesamt"
        ],
        parse_dates=[
            "Produktionsdatum"
        ],
        chunksize=250000
    ):
        aggregated = (
            chunk
            .groupby(
                [
                    "Produktionsdatum",
                    "OEM",
                    "Fahrzeugtyp",
                    "Werksnummer_OEM",
                    "ORT_OEM"
                ],
                as_index=False,
                dropna=False
            )
            .agg(
                Vehicles=(
                    "Fehlerhaft_Gesamt",
                    "size"
                ),
                Defective_Vehicles=(
                    "Fehlerhaft_Gesamt",
                    "sum"
                )
            )
        )

        parts.append(aggregated)

    dashboard_data = (
        pd.concat(
            parts,
            ignore_index=True
        )
        .groupby(
            [
                "Produktionsdatum",
                "OEM",
                "Fahrzeugtyp",
                "Werksnummer_OEM",
                "ORT_OEM"
            ],
            as_index=False,
            dropna=False
        )
        .agg(
            Vehicles=(
                "Vehicles",
                "sum"
            ),
            Defective_Vehicles=(
                "Defective_Vehicles",
                "sum"
            )
        )
    )

    return dashboard_data


dashboard_data = load_dashboard_data()


st.title("Quality KPI Dashboard")


oem_options = sorted(
    dashboard_data["OEM"]
    .dropna()
    .unique()
    .tolist()
)

type_options = sorted(
    dashboard_data["Fahrzeugtyp"]
    .dropna()
    .unique()
    .tolist()
)

plant_options = sorted(
    dashboard_data["ORT_OEM"]
    .dropna()
    .unique()
    .tolist()
)

min_date = (
    dashboard_data["Produktionsdatum"]
    .dropna()
    .min()
    .date()
)

max_date = (
    dashboard_data["Produktionsdatum"]
    .dropna()
    .max()
    .date()
)


filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(
    [1, 1, 1.3, 1.5]
)

with filter_col1:
    selected_oems = st.multiselect(
        "OEM",
        options=oem_options,
        default=oem_options
    )

with filter_col2:
    selected_types = st.multiselect(
        "Vehicle Type",
        options=type_options,
        default=type_options
    )

with filter_col3:
    selected_plants = st.multiselect(
        "Production Plant",
        options=plant_options,
        default=plant_options
    )

with filter_col4:
    selected_dates = st.date_input(
        "Production Date",
        value=(
            min_date,
            max_date
        ),
        min_value=min_date,
        max_value=max_date
    )


mask = (
    dashboard_data["OEM"].isin(
        selected_oems
    )
    &
    dashboard_data["Fahrzeugtyp"].isin(
        selected_types
    )
    &
    dashboard_data["ORT_OEM"].isin(
        selected_plants
    )
)


if len(selected_dates) == 2:
    start_date, end_date = selected_dates

    if (
        start_date != min_date
        or end_date != max_date
    ):
        date_mask = (
            dashboard_data[
                "Produktionsdatum"
            ].between(
                pd.Timestamp(start_date),
                pd.Timestamp(end_date)
            )
        )

        mask &= date_mask


filtered_data = dashboard_data.loc[
    mask
]


if filtered_data.empty:
    st.warning(
        "No vehicles match the selected filters."
    )
    st.stop()


oem_kpi = (
    filtered_data
    .groupby(
        [
            "OEM",
            "Werksnummer_OEM",
            "ORT_OEM"
        ],
        as_index=False,
        dropna=False
    )
    .agg(
        Vehicles=(
            "Vehicles",
            "sum"
        ),
        Defective_Vehicles=(
            "Defective_Vehicles",
            "sum"
        )
    )
)


oem_kpi["Defect_Rate_%"] = (
    oem_kpi["Defective_Vehicles"]
    / oem_kpi["Vehicles"]
    * 100
)


vehicles = (
    oem_kpi["Vehicles"]
    .sum()
)

defective_vehicles = (
    oem_kpi["Defective_Vehicles"]
    .sum()
)

overall_defect_rate = (
    defective_vehicles
    / vehicles
    * 100
)

highest_rate_row = (
    oem_kpi
    .sort_values(
        "Defect_Rate_%",
        ascending=False
    )
    .iloc[0]
)


metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(
    4
)

metric_col1.metric(
    "Vehicles",
    f"{vehicles:,.0f}"
)

metric_col2.metric(
    "Defective Vehicles",
    f"{defective_vehicles:,.0f}"
)

metric_col3.metric(
    "Overall Defect Rate",
    f"{overall_defect_rate:.2f}%"
)

metric_col4.metric(
    "Highest Defect Rate",
    highest_rate_row[
        "ORT_OEM"
    ],
    f"{highest_rate_row['Defect_Rate_%']:.2f}%"
)


chart_col1, chart_col2 = st.columns(
    2
)


with chart_col1:
    absolute_kpi = (
        oem_kpi
        .sort_values(
            "Defective_Vehicles",
            ascending=False
        )
    )

    fig_absolute = px.bar(
        absolute_kpi,
        x="ORT_OEM",
        y="Defective_Vehicles",
        text="Defective_Vehicles",
        custom_data=[
            "OEM",
            "Werksnummer_OEM",
            "Vehicles",
            "Defect_Rate_%"
        ],
        labels={
            "ORT_OEM":
                "Production Plant",
            "Defective_Vehicles":
                "Defective Vehicles"
        },
        title=
            "Absolute Defect Frequency"
    )

    fig_absolute.update_traces(
        texttemplate=
            "%{text:,.0f}",
        textposition=
            "outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "OEM: %{customdata[0]}<br>"
            "Plant Number: %{customdata[1]}<br>"
            "Vehicles: %{customdata[2]:,.0f}<br>"
            "Defective Vehicles: %{y:,.0f}<br>"
            "Defect Rate: %{customdata[3]:.2f}%"
            "<extra></extra>"
        )
    )

    fig_absolute.update_layout(
        height=360,
        showlegend=False,
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        ),
        xaxis_title=None,
        yaxis_title=
            "Defective Vehicles"
    )

    fig_absolute.update_yaxes(
        rangemode="tozero"
    )

    st.plotly_chart(
        fig_absolute,
        use_container_width=True,
        config={
            "displayModeBar":
                False
        }
    )


with chart_col2:
    relative_kpi = (
        oem_kpi
        .sort_values(
            "Defect_Rate_%",
            ascending=True
        )
    )

    minimum_rate = (
        relative_kpi[
            "Defect_Rate_%"
        ].min()
    )

    maximum_rate = (
        relative_kpi[
            "Defect_Rate_%"
        ].max()
    )

    fig_relative = px.scatter(
        relative_kpi,
        x="Defect_Rate_%",
        y="ORT_OEM",
        text="Defect_Rate_%",
        custom_data=[
            "OEM",
            "Werksnummer_OEM",
            "Vehicles",
            "Defective_Vehicles"
        ],
        labels={
            "Defect_Rate_%":
                "Defect Rate [%]",
            "ORT_OEM":
                "Production Plant"
        },
        title=
            "Relative Defect Frequency"
    )

    fig_relative.update_traces(
        marker=dict(
            size=18
        ),
        texttemplate=
            "%{text:.2f}%",
        textposition=
            "middle right",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "OEM: %{customdata[0]}<br>"
            "Plant Number: %{customdata[1]}<br>"
            "Vehicles: %{customdata[2]:,.0f}<br>"
            "Defective Vehicles: %{customdata[3]:,.0f}<br>"
            "Defect Rate: %{x:.2f}%"
            "<extra></extra>"
        )
    )

    fig_relative.update_xaxes(
        range=[
            max(
                0,
                minimum_rate - 1
            ),
            min(
                100,
                maximum_rate + 1
            )
        ]
    )

    fig_relative.update_layout(
        height=360,
        showlegend=False,
        margin=dict(
            l=20,
            r=70,
            t=60,
            b=20
        ),
        xaxis_title=
            "Defect Rate [%]",
        yaxis_title=None
    )

    st.plotly_chart(
        fig_relative,
        use_container_width=True,
        config={
            "displayModeBar":
                False
        }
    )


with st.expander(
    "Production Plant KPI Table"
):
    display_table = (
        oem_kpi[
            [
                "OEM",
                "Werksnummer_OEM",
                "ORT_OEM",
                "Vehicles",
                "Defective_Vehicles",
                "Defect_Rate_%"
            ]
        ]
        .copy()
    )

    display_table = (
        display_table
        .rename(
            columns={
                "Werksnummer_OEM":
                    "Plant Number",
                "ORT_OEM":
                    "Production Plant",
                "Defect_Rate_%":
                    "Defect Rate [%]"
            }
        )
    )

    display_table[
        "Defect Rate [%]"
    ] = (
        display_table[
            "Defect Rate [%]"
        ].round(2)
    )

    display_table = (
        display_table
        .sort_values(
            "Defect Rate [%]",
            ascending=False
        )
    )

    st.dataframe(
        display_table,
        hide_index=True,
        use_container_width=True
    )