# Superset Chart Parameters by Visualization Type

This document provides a detailed description of parameters for charts found in the "Featured Charts", "World Bank's Data", "USA Births Names", and "deck.gl Demo" dashboards, organized by their `viz_type`.

---

## Viz Type: big_number

### Chart Name: World's Population
*   **compare_lag**: "10" - Lag for comparison, e.g., '10' for 10 periods ago.
*   **compare_suffix**: "over 10Y" - Suffix to append to the comparison value.
*   **country_fieldtype**: "cca3" - Type of country field (e.g., 'cca3' for ISO 3166-1 alpha-3 codes).
*   **entity**: "country_code" - The column representing the entity for geographic visualizations.
*   **granularity_sqla**: "year" - SQL Alchemy temporal column to use for time granularity.
*   **groupby**: [] - List of columns to group by.
*   **limit**: "25" - Maximum number of rows to return.
*   **markup_type**: "markdown" - Type of markup used (e.g., 'markdown').
*   **metric**: "sum__SP_POP_TOTL" - The metric used for the big number.
*   **row_limit**: 50000 - Row limit for the query.
*   **show_bubbles**: True - Whether to show bubbles in certain visualizations (might be ignored for big_number).
*   **since**: "2000" - Start date for the time range.
*   **time_range**: "2014-01-01 : 2014-01-02" - Specific time range filter.
*   **until**: "2014-01-02" - End date for the time range.
*   **viz_type**: "big_number" - The visualization type.

### Chart Name: Participants
*   **compare_lag**: "5" - Lag for comparison, e.g., '5' for 5 periods ago.
*   **compare_suffix**: "over 5Y" - Suffix to append to the comparison value.
*   **granularity_sqla**: "ds" - SQL Alchemy temporal column to use for time granularity.
*   **groupby**: [] - List of columns to group by.
*   **limit**: "25" - Maximum number of rows to return.
*   **markup_type**: "markdown" - Type of markup used (e.g., 'markdown').
*   **metric**: "sum__num" - The metric used for the big number.
*   **row_limit**: 50000 - Row limit for the query.
*   **time_range**: "100 years ago : now" - Specific time range filter.
*   **viz_type**: "big_number" - The visualization type.

### Chart Name: Big Number with Trendline
*   **datasource**: "22__table" - Identifier for the datasource used.
*   **viz_type**: "big_number" - The visualization type.
*   **x_axis**: "order_date" - The column used for the X-axis.
*   **time_grain_sqla**: "P1M" - Time grain for SQL Alchemy temporal columns (e.g., 'P1M' for monthly).
*   **metric**: "count" - The metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - List of adhoc filters applied.
*   **show_trend_line**: True - Whether to show a trend line.
*   **start_y_axis_at_zero**: True - Whether the Y-axis should start at zero.
*   **color_picker**: {'r': 0, 'g': 122, 'b': 135, 'a': 1} - Color settings in RGBA format.
*   **header_font_size**: 0.4 - Font size for the header.
*   **subheader_font_size**: 0.15 - Font size for the subheader.
*   **y_axis_format**: "SMART_NUMBER" - Format for Y-axis labels.
*   **time_format**: "smart_date" - Format for time values.
*   **rolling_type**: "None" - Type of rolling window calculation.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [13] - List of dashboard IDs this chart is part of.
*   **annotation_layers**: [] - List of annotation layers.

---

## Viz Type: table

### Chart Name: Most Populated Countries
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: ["country_name"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: ["sum__SP_POP_TOTL"] - Metrics used.
*   **row_limit**: 50000 - Row limit.
*   **show_bubbles**: True - Show bubbles (might be ignored).
*   **since**: "2014-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "2014-01-02" - End date.
*   **viz_type**: "table" - Visualization type.

### Chart Name: Girls
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'girl', 'expressionType': 'SIMPLE', 'operator': '==', 'subject': 'gender'}] - Adhoc filters applied.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["name"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: ["sum__num"] - Metrics used.
*   **row_limit**: 50 - Row limit.
*   **time_range**: "100 years ago : now" - Time range.
*   **timeseries_limit_metric**: "sum__num" - Metric to limit timeseries.
*   **viz_type**: "table" - Visualization type.

### Chart Name: Boys
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'boy', 'expressionType': 'SIMPLE', 'operator': '==', 'subject': 'gender'}] - Adhoc filters applied.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["name"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: ["sum__num"] - Metrics used.
*   **row_limit**: 50 - Row limit.
*   **time_range**: "100 years ago : now" - Time range.
*   **timeseries_limit_metric**: "sum__num" - Metric to limit timeseries.
*   **viz_type**: "table" - Visualization type.

### Chart Name: Table
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "table" - Visualization type.
*   **query_mode**: "raw" - Query mode (e.g., 'raw' or 'aggregate').
*   **groupby**: [] - Columns to group by.
*   **time_grain_sqla**: "P1D" - Time grain.
*   **temporal_columns_lookup**: {'order_date': True} - Dictionary mapping temporal columns to boolean.
*   **all_columns**: ["order_date", "product_line", "status", "price_each", "sales"] - All columns to display.
*   **percent_metrics**: [] - Metrics to display as percentages.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **order_by_cols**: [] - Columns to order by.
*   **row_limit**: 1000 - Row limit.
*   **server_page_length**: 10 - Number of rows per page for server-side pagination.
*   **order_desc**: True - Whether to order descending.
*   **table_timestamp_format**: "smart_date" - Format for table timestamps.
*   **show_cell_bars**: True - Whether to show cell bars.
*   **color_pn**: True - Whether to color positive/negative values.
*   **allow_render_html**: True - Whether to allow rendering HTML in cells.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [13] - Dashboard IDs this chart is part of.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: echarts_timeseries_line

### Chart Name: Growth Rate
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: ["country_name"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: ["sum__SP_POP_TOTL"] - Metrics used.
*   **num_period_compare**: "10" - Number of periods to compare.
*   **row_limit**: 50000 - Row limit.
*   **show_bubbles**: True - Show bubbles (might be ignored).
*   **since**: "1960-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "2014-01-02" - End date.
*   **viz_type**: "echarts_timeseries_line" - Visualization type.

### Chart Name: Trends
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["name"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: [{'aggregate': 'SUM', 'column': {'column_name': 'num', 'type': 'BIGINT'}, 'expressionType': 'SIMPLE', 'label': 'Births', 'optionName': 'metric_11'}] - Metrics used.
*   **rich_tooltip**: True - Whether to show rich tooltips.
*   **row_limit**: 50000 - Row limit.
*   **show_legend**: True - Whether to show the legend.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "echarts_timeseries_line" - Visualization type.

### Chart Name: Line
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "echarts_timeseries_line" - Visualization type.
*   **x_axis**: "order_date" - X-axis column.
*   **time_grain_sqla**: "P1M" - Time grain.
*   **x_axis_sort_asc**: True - Sort X-axis ascending.
*   **x_axis_sort_series**: "name" - Sort series by name.
*   **x_axis_sort_series_ascending**: True - Sort series ascending.
*   **metrics**: ["count"] - Metrics used.
*   **groupby**: ["product_line"] - Columns to group by.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **order_desc**: True - Order descending.
*   **row_limit**: 10000 - Row limit.
*   **truncate_metric**: True - Truncate metric values.
*   **show_empty_columns**: True - Show empty columns.
*   **comparison_type**: "values" - Comparison type.
*   **annotation_layers**: [] - Annotation layers.
*   **forecastPeriods**: 10 - Number of forecast periods.
*   **forecastInterval**: 0.8 - Forecast interval.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 15 - Y-axis title margin.
*   **y_axis_title_position**: "Left" - Y-axis title position.
*   **sort_series_type**: "sum" - Sort series by sum.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **seriesType**: "echarts_timeseries_line" - Series type.
*   **only_total**: True - Only show total.
*   **opacity**: 0.2 - Opacity of series.
*   **markerSize**: 6 - Marker size.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **rich_tooltip**: True - Rich tooltip.
*   **tooltipTimeFormat**: "smart_date" - Tooltip time format.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **truncateXAxis**: True - Truncate X-axis.
*   **y_axis_bounds**: [None, None] - Y-axis bounds.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [13] - Dashboard IDs.

---

## Viz Type: world_map

### Chart Name: % Rural
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: [] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metric**: "sum__SP_RUR_TOTL_ZS" - Metric used.
*   **num_period_compare**: "10" - Number of periods to compare.
*   **row_limit**: 50000 - Row limit.
*   **secondary_metric**: {'aggregate': 'SUM', 'column': {'column_name': 'SP_RUR_TOTL', 'optionName': '_col_SP_RUR_TOTL', 'type': 'DOUBLE'}, 'expressionType': 'SIMPLE', 'hasCustomLabel': True, 'label': 'Rural Population'} - Secondary metric.
*   **show_bubbles**: True - Show bubbles.
*   **since**: "2014-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "2014-01-02" - End date.
*   **viz_type**: "world_map" - Visualization type.

---

## Viz Type: bubble

### Chart Name: Life Expectancy VS Rural %
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': ['TCA', 'MNP', 'DMA', 'MHL', 'MCO', 'SXM', 'CYM', 'TUV', 'IMY', 'KNA', 'ASM', 'ADO', 'AMA', 'PLW'], 'expressionType': 'SIMPLE', 'filterOptionName': '2745eae5', 'operator': 'NOT IN', 'subject': 'country_code'}] - Adhoc filters.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_name" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: [] - Columns to group by.
*   **limit**: 0 - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **max_bubble_size**: "50" - Maximum bubble size.
*   **row_limit**: 50000 - Row limit.
*   **series**: "region" - Series column.
*   **show_bubbles**: True - Show bubbles.
*   **since**: "2011-01-01" - Start date.
*   **size**: "sum__SP_POP_TOTL" - Size metric.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "2011-01-02" - End date.
*   **viz_type**: "bubble" - Visualization type.
*   **x**: "sum__SP_RUR_TOTL_ZS" - X-axis metric.
*   **y**: "sum__SP_DYN_LE00_IN" - Y-axis metric.

---

## Viz Type: sunburst_v2

### Chart Name: Rural Breakdown
*   **columns**: ["region", "country_name"] - Columns to use for the sunburst.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: [] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metric**: "sum__SP_POP_TOTL" - Metric used.
*   **row_limit**: 50000 - Row limit.
*   **secondary_metric**: {'aggregate': 'SUM', 'column': {'column_name': 'SP_RUR_TOTL', 'optionName': '_col_SP_RUR_TOTL', 'type': 'DOUBLE'}, 'expressionType': 'SIMPLE', 'hasCustomLabel': True, 'label': 'Rural Population'} - Secondary metric.
*   **show_bubbles**: True - Show bubbles (might be ignored).
*   **since**: "2011-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "2011-01-02" - End date.
*   **viz_type**: "sunburst_v2" - Visualization type.

### Chart Name: Sunburst
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "sunburst_v2" - Visualization type.
*   **columns**: ["year", "product_line"] - Columns for the sunburst.
*   **metric**: "count" - Metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 10000 - Row limit.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **linear_color_scheme**: "superset_seq_1" - Linear color scheme.
*   **show_labels**: True - Show labels.
*   **show_labels_threshold**: 5 - Threshold for showing labels.
*   **label_type**: "key" - Type of label.
*   **number_format**: "~g" - Number format.
*   **date_format**: "smart_date" - Date format.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: echarts_area

### Chart Name: World's Pop Growth
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: ["region"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: ["sum__SP_POP_TOTL"] - Metrics used.
*   **row_limit**: 50000 - Row limit.
*   **show_bubbles**: True - Show bubbles (might be ignored).
*   **since**: "1960-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "now" - End date.
*   **viz_type**: "echarts_area" - Visualization type.

### Chart Name: Top 10 Girl Name Share
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'girl', 'expressionType': 'SIMPLE', 'operator': '==', 'subject': 'gender'}] - Adhoc filters.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **comparison_type**: "values" - Comparison type.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["name"] - Columns to group by.
*   **limit**: 10 - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: [{'aggregate': 'SUM', 'column': {'column_name': 'num', 'type': 'BIGINT'}, 'expressionType': 'SIMPLE', 'label': 'Births', 'optionName': 'metric_11'}] - Metrics used.
*   **row_limit**: 50000 - Row limit.
*   **stacked_style**: "expand" - Stacked style.
*   **time_grain_sqla**: "P1D" - Time grain.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "echarts_area" - Visualization type.
*   **x_axis_forma**: "smart_date" - X-axis format.

### Chart Name: Top 10 Boy Name Share
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'boy', 'expressionType': 'SIMPLE', 'operator': '==', 'subject': 'gender'}] - Adhoc filters.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **comparison_type**: "values" - Comparison type.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["name"] - Columns to group by.
*   **limit**: 10 - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: [{'aggregate': 'SUM', 'column': {'column_name': 'num', 'type': 'BIGINT'}, 'expressionType': 'SIMPLE', 'label': 'Births', 'optionName': 'metric_11'}] - Metrics used.
*   **row_limit**: 50000 - Row limit.
*   **stacked_style**: "expand" - Stacked style.
*   **time_grain_sqla**: "P1D" - Time grain.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "echarts_area" - Visualization type.
*   **x_axis_forma**: "smart_date" - X-axis format.

### Chart Name: Area
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "echarts_area" - Visualization type.
*   **x_axis**: "order_date" - X-axis column.
*   **time_grain_sqla**: "P1W" - Time grain.
*   **x_axis_sort_asc**: True - Sort X-axis ascending.
*   **x_axis_sort_series**: "name" - Sort series by name.
*   **x_axis_sort_series_ascending**: True - Sort series ascending.
*   **metrics**: [{'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'sales', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 734, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'DOUBLE PRECISION', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'SUM', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'SUM(sales)', 'optionName': 'metric_thuvfstatme_5o1pircsnev'}] - Metrics used.
*   **groupby**: ["deal_size"] - Columns to group by.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **order_desc**: True - Order descending.
*   **row_limit**: 10000 - Row limit.
*   **truncate_metric**: True - Truncate metric values.
*   **show_empty_columns**: True - Show empty columns.
*   **comparison_type**: "values" - Comparison type.
*   **annotation_layers**: [] - Annotation layers.
*   **forecastPeriods**: 10 - Number of forecast periods.
*   **forecastInterval**: 0.8 - Forecast interval.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 15 - Y-axis title margin.
*   **y_axis_title_position**: "Left" - Y-axis title position.
*   **sort_series_type**: "sum" - Sort series by sum.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **seriesType**: "echarts_timeseries_line" - Series type.
*   **opacity**: 0.2 - Opacity of series.
*   **only_total**: True - Only show total.
*   **markerSize**: 6 - Marker size.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **rich_tooltip**: True - Rich tooltip.
*   **tooltipTimeFormat**: "smart_date" - Tooltip time format.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **truncateXAxis**: True - Truncate X-axis.
*   **y_axis_bounds**: [None, None] - Y-axis bounds.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [13] - Dashboard IDs.

---

## Viz Type: box_plot

### Chart Name: Box plot
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: ["region"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: ["sum__SP_POP_TOTL"] - Metrics used.
*   **row_limit**: 50000 - Row limit.
*   **show_bubbles**: True - Show bubbles (might be ignored).
*   **since**: "1960-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "now" - End date.
*   **viz_type**: "box_plot" - Visualization type.
*   **whisker_options**: "Min/max (no outliers)" - Options for whiskers.
*   **x_ticks_layout**: "staggered" - Layout for X-axis ticks.

### Chart Name: Box Plot
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "box_plot" - Visualization type.
*   **columns**: ["order_date"] - Columns to use.
*   **time_grain_sqla**: "P1D" - Time grain.
*   **temporal_columns_lookup**: {'order_date': True} - Temporal columns lookup.
*   **groupby**: ["product_line"] - Columns to group by.
*   **metrics**: ["count"] - Metrics used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **whiskerOptions**: "Tukey" - Options for whiskers.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 15 - Y-axis title margin.
*   **y_axis_title_position**: "Left" - Y-axis title position.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **x_ticks_layout**: "auto" - Layout for X-axis ticks.
*   **number_format**: "SMART_NUMBER" - Number format.
*   **date_format**: "smart_date" - Date format.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: treemap_v2

### Chart Name: Treemap
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **country_fieldtype**: "cca3" - Type of country field.
*   **entity**: "country_code" - Entity column.
*   **granularity_sqla**: "year" - Time granularity.
*   **groupby**: ["region", "country_code"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metric**: "sum__SP_POP_TOTL" - Metric used.
*   **row_limit**: 50000 - Row limit.
*   **show_bubbles**: True - Show bubbles (might be ignored).
*   **since**: "1960-01-01" - Start date.
*   **time_range**: "2014-01-01 : 2014-01-02" - Time range.
*   **until**: "now" - End date.
*   **viz_type**: "treemap_v2" - Visualization type.

---

## Viz Type: echarts_timeseries_bar

### Chart Name: Genders by State
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': ['other'], 'expressionType': 'SIMPLE', 'filterOptionName': '2745eae5', 'operator': 'NOT IN', 'subject': 'state'}] - Adhoc filters.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["state"] - Columns to group by.
*   **limit**: "25" - Max rows.
*   **markup_type**: "markdown" - Markup type.
*   **metrics**: [{'aggregate': 'SUM', 'column': {'column_name': 'num_boys', 'type': 'BIGINT(20)'}, 'expressionType': 'SIMPLE', 'label': 'Boys', 'optionName': 'metric_11'}, {'aggregate': 'SUM', 'column': {'column_name': 'num_girls', 'type': 'BIGINT(20)'}, 'expressionType': 'SIMPLE', 'label': 'Girls', 'optionName': 'metric_12'}] - Metrics used.
*   **row_limit**: 50000 - Row limit.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "echarts_timeseries_bar" - Visualization type.

### Chart Name: Bar
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "echarts_timeseries_bar" - Visualization type.
*   **x_axis**: "order_date" - X-axis column.
*   **time_grain_sqla**: "P1M" - Time grain.
*   **x_axis_sort_asc**: True - Sort X-axis ascending.
*   **x_axis_sort_series**: "name" - Sort series by name.
*   **x_axis_sort_series_ascending**: True - Sort series ascending.
*   **metrics**: ["count"] - Metrics used.
*   **groupby**: ["deal_size"] - Columns to group by.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **order_desc**: True - Order descending.
*   **row_limit**: 10000 - Row limit.
*   **truncate_metric**: True - Truncate metric values.
*   **show_empty_columns**: True - Show empty columns.
*   **comparison_type**: "values" - Comparison type.
*   **annotation_layers**: [] - Annotation layers.
*   **forecastPeriods**: 10 - Number of forecast periods.
*   **forecastInterval**: 0.8 - Forecast interval.
*   **orientation**: "vertical" - Orientation of bars.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 15 - Y-axis title margin.
*   **y_axis_title_position**: "Left" - Y-axis title position.
*   **sort_series_type**: "sum" - Sort series by sum.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **only_total**: True - Only show total.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **truncateXAxis**: True - Truncate X-axis.
*   **y_axis_bounds**: [None, None] - Y-axis bounds.
*   **rich_tooltip**: True - Rich tooltip.
*   **tooltipTimeFormat**: "smart_date" - Tooltip time format.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [13] - Dashboard IDs.

---

## Viz Type: word_cloud

### Chart Name: Boy Name Cloud
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'boy', 'expressionType': 'SIMPLE', 'operator': '==', 'subject': 'gender'}] - Adhoc filters.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: [] - Columns to group by.
*   **limit**: "100" - Max words.
*   **markup_type**: "markdown" - Markup type.
*   **metric**: "sum__num" - Metric used.
*   **rotation**: "square" - Rotation style for words.
*   **row_limit**: 50000 - Row limit.
*   **series**: "name" - Series column (word to display).
*   **size_from**: "10" - Minimum font size.
*   **size_to**: "70" - Maximum font size.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "word_cloud" - Visualization type.

### Chart Name: Girl Name Cloud
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'girl', 'expressionType': 'SIMPLE', 'operator': '==', 'subject': 'gender'}] - Adhoc filters.
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: [] - Columns to group by.
*   **limit**: "100" - Max words.
*   **markup_type**: "markdown" - Markup type.
*   **metric**: "sum__num" - Metric used.
*   **rotation**: "square" - Rotation style for words.
*   **row_limit**: 50000 - Row limit.
*   **series**: "name" - Series column (word to display).
*   **size_from**: "10" - Minimum font size.
*   **size_to**: "70" - Maximum font size.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "word_cloud" - Visualization type.

### Chart Name: Word Cloud
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "word_cloud" - Visualization type.
*   **series**: "customer_name" - Series column (word to display).
*   **metric**: "count" - Metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 100 - Row limit.
*   **size_from**: 10 - Minimum font size.
*   **size_to**: 70 - Maximum font size.
*   **rotation**: "square" - Rotation style.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: pie

### Chart Name: Genders
*   **compare_lag**: "10" - Lag for comparison.
*   **compare_suffix**: "o10Y" - Suffix for comparison.
*   **granularity_sqla**: "ds" - Time granularity.
*   **groupby**: ["gender"] - Columns to group by.
*   **limit**: "25" - Max slices.
*   **markup_type**: "markdown" - Markup type.
*   **metric**: "sum__num" - Metric used.
*   **row_limit**: 50000 - Row limit.
*   **time_range**: "100 years ago : now" - Time range.
*   **viz_type**: "pie" - Visualization type.

### Chart Name: Pie
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "pie" - Visualization type.
*   **groupby**: ["product_line"] - Columns to group by.
*   **metric**: {'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'sales', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 734, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'DOUBLE PRECISION', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'SUM', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'SUM(sales)', 'optionName': 'metric_m2fycvcvjie_4gnezrycwmb'} - Metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 100 - Row limit.
*   **sort_by_metric**: True - Sort by metric.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **show_labels_threshold**: 5 - Threshold for showing labels.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **label_type**: "key" - Label type.
*   **number_format**: "SMART_NUMBER" - Number format.
*   **date_format**: "smart_date" - Date format.
*   **show_labels**: True - Show labels.
*   **labels_outside**: True - Labels outside of slices.
*   **outerRadius**: 70 - Outer radius of pie.
*   **innerRadius**: 30 - Inner radius of pie.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: deck_scatter

### Chart Name: Deck.gl Scatterplot
*   **color_picker**: {'a': 0.82, 'b': 3, 'g': 0, 'r': 205} - Color in RGBA format.
*   **datasource**: "5__table" - Identifier for the datasource.
*   **granularity_sqla**: None - Time granularity (not applicable here).
*   **groupby**: [] - Columns to group by.
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **max_radius**: 250 - Maximum radius for points.
*   **min_radius**: 1 - Minimum radius for points.
*   **multiplier**: 10 - Multiplier for radius.
*   **point_radius_fixed**: {'type': 'metric', 'value': 'count'} - Fixed radius settings.
*   **point_unit**: "square_m" - Unit for point radius.
*   **row_limit**: 5000 - Row limit.
*   **size**: "count" - Size metric.
*   **spatial**: {'latCol': 'LAT', 'lonCol': 'LON', 'type': 'latlong'} - Spatial column settings.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: " : " - Time range.
*   **viewport**: {'bearing': -4.952916738791771, 'latitude': 37.78926922909199, 'longitude': -122.42613341901688, 'pitch': 4.750411100577438, 'zoom': 12.729132798697304} - Viewport settings.
*   **viz_type**: "deck_scatter" - Visualization type.

---

## Viz Type: deck_screengrid

### Chart Name: Deck.gl Screen grid
*   **color_picker**: {'a': 1, 'b': 0, 'g': 255, 'r': 14} - Color in RGBA format.
*   **datasource**: "5__table" - Identifier for the datasource.
*   **granularity_sqla**: None - Time granularity (not applicable).
*   **grid_size**: 20 - Size of the grid cells.
*   **groupby**: [] - Columns to group by.
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **point_radius**: "Auto" - Point radius setting.
*   **point_radius_fixed**: {'type': 'fix', 'value': 2000} - Fixed radius settings.
*   **point_unit**: "square_m" - Unit for point radius.
*   **row_limit**: 5000 - Row limit.
*   **size**: "count" - Size metric.
*   **spatial**: {'latCol': 'LAT', 'lonCol': 'LON', 'type': 'latlong'} - Spatial column settings.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: "No filter" - Time range.
*   **viewport**: {'bearing': -4.952916738791771, 'latitude': 37.76024135844065, 'longitude': -122.41827069521386, 'pitch': 4.750411100577438, 'zoom': 14.161641703941438} - Viewport settings.
*   **viz_type**: "deck_screengrid" - Visualization type.

---

## Viz Type: deck_hex

### Chart Name: Deck.gl Hexagons
*   **color_picker**: {'a': 1, 'b': 0, 'g': 255, 'r': 14} - Color in RGBA format.
*   **datasource**: "5__table" - Identifier for the datasource.
*   **extruded**: True - Whether to extrude hexagons.
*   **granularity_sqla**: None - Time granularity (not applicable).
*   **grid_size**: 40 - Size of the grid cells.
*   **groupby**: [] - Columns to group by.
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **point_radius**: "Auto" - Point radius setting.
*   **point_radius_fixed**: {'type': 'fix', 'value': 2000} - Fixed radius settings.
*   **point_radius_unit**: "Pixels" - Unit for point radius.
*   **row_limit**: 5000 - Row limit.
*   **size**: "count" - Size metric.
*   **spatial**: {'latCol': 'LAT', 'lonCol': 'LON', 'type': 'latlong'} - Spatial column settings.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: "No filter" - Time range.
*   **viewport**: {'bearing': -2.3984797349335167, 'latitude': 37.789795085160335, 'longitude': -122.40632230075536, 'pitch': 54.08961642447763, 'zoom': 13.835465702403654} - Viewport settings.
*   **viz_type**: "deck_hex" - Visualization type.

---

## Viz Type: deck_grid

### Chart Name: Deck.gl Grid
*   **autozoom**: False - Whether to autozoom the map.
*   **color_picker**: {'a': 1, 'b': 0, 'g': 255, 'r': 14} - Color in RGBA format.
*   **datasource**: "5__table" - Identifier for the datasource.
*   **extruded**: True - Whether to extrude grid cells.
*   **granularity_sqla**: None - Time granularity (not applicable).
*   **grid_size**: 120 - Size of the grid cells.
*   **groupby**: [] - Columns to group by.
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **point_radius**: "Auto" - Point radius setting.
*   **point_radius_fixed**: {'type': 'fix', 'value': 2000} - Fixed radius settings.
*   **point_radius_unit**: "Pixels" - Unit for point radius.
*   **row_limit**: 5000 - Row limit.
*   **size**: "count" - Size metric.
*   **spatial**: {'latCol': 'LAT', 'lonCol': 'LON', 'type': 'latlong'} - Spatial column settings.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: "No filter" - Time range.
*   **viewport**: {'bearing': 155.80099696026355, 'latitude': 37.7942314882596, 'longitude': -122.42066918995666, 'pitch': 53.470800300695146, 'zoom': 12.699690845482069} - Viewport settings.
*   **viz_type**: "deck_grid" - Visualization type.

---

## Viz Type: deck_polygon

### Chart Name: Deck.gl Polygons
*   **datasource**: "11__table" - Identifier for the datasource.
*   **extruded**: True - Whether to extrude polygons.
*   **fill_color_picker**: {'a': 1, 'b': 73, 'g': 65, 'r': 3} - Fill color in RGBA format.
*   **filled**: True - Whether polygons are filled.
*   **granularity_sqla**: None - Time granularity (not applicable).
*   **js_columns**: [] - JavaScript columns to inject.
*   **js_data_mutator**: "" - JavaScript function to mutate data.
*   **js_onclick_href**: "" - JavaScript function for onclick href.
*   **js_tooltip**: "" - JavaScript function for tooltip.
*   **legend_format**: ".1s" - Format for legend.
*   **legend_position**: "tr" - Position of the legend.
*   **line_column**: "contour" - Column for line data.
*   **line_type**: "json" - Type of line data.
*   **line_width**: 10 - Width of lines.
*   **line_width_unit**: "meters" - Unit for line width.
*   **linear_color_scheme**: "oranges" - Linear color scheme.
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **metric**: {'aggregate': 'SUM', 'column': {'column_name': 'population', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 1332, 'is_dttm': False, 'optionName': '_col_population', 'python_date_format': None, 'type': 'BIGINT', 'verbose_name': None}, 'expressionType': 'SIMPLE', 'hasCustomLabel': True, 'label': 'Population', 'optionName': 'metric_t2v4qbfiz1_w6qgpx4h2p', 'sqlExpression': None} - Metric used.
*   **multiplier**: 0.1 - Multiplier for values.
*   **point_radius_fixed**: {'type': 'metric', 'value': {'aggregate': None, 'column': None, 'expressionType': 'SQL', 'hasCustomLabel': None, 'label': 'Density', 'optionName': 'metric_c5rvwrzoo86_293h6yrv2ic', 'sqlExpression': 'SUM(population)/SUM(area)'}} - Fixed radius settings.
*   **reverse_long_lat**: False - Whether to reverse longitude and latitude.
*   **slice_id**: 41 - ID of the slice.
*   **stroke_color_picker**: {'a': 1, 'b': 135, 'g': 122, 'r': 0} - Stroke color in RGBA format.
*   **stroked**: False - Whether polygons have strokes.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: " : " - Time range.
*   **viewport**: {'altitude': 1.5, 'bearing': 37.89506450385642, 'height': 906, 'latitude': 37.752020331384834, 'longitude': -122.43388541747726, 'maxLatitude': 85.05113, 'maxPitch': 60, 'maxZoom': 20, 'minLatitude': -85.05113, 'minPitch': 0, 'minZoom': 0, 'pitch': 60, 'width': 667, 'zoom': 11.133995608594631} - Viewport settings.
*   **viz_type**: "deck_polygon" - Visualization type.

---

## Viz Type: deck_arc

### Chart Name: Deck.gl Arcs
*   **color_picker**: {'a': 1, 'b': 135, 'g': 122, 'r': 0} - Color in RGBA format.
*   **datasource**: "10__table" - Identifier for the datasource.
*   **end_spatial**: {'latCol': 'LATITUDE_DEST', 'lonCol': 'LONGITUDE_DEST', 'type': 'latlong'} - End spatial column settings.
*   **granularity_sqla**: None - Time granularity (not applicable).
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **row_limit**: 5000 - Row limit.
*   **slice_id**: 42 - ID of the slice.
*   **start_spatial**: {'latCol': 'LATITUDE', 'lonCol': 'LONGITUDE', 'type': 'latlong'} - Start spatial column settings.
*   **stroke_width**: 1 - Width of strokes.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: " : " - Time range.
*   **viewport**: {'altitude': 1.5, 'bearing': 8.546256357301871, 'height': 642, 'latitude': 44.596651438714254, 'longitude': -91.84340711201104, 'maxLatitude': 85.05113, 'maxPitch': 60, 'maxZoom': 20, 'minLatitude': -85.05113, 'minPitch': 0, 'minZoom': 0, 'pitch': 60, 'width': 997, 'zoom': 2.929837070560775} - Viewport settings.
*   **viz_type**: "deck_arc" - Visualization type.

---

## Viz Type: deck_path

### Chart Name: Deck.gl Path
*   **color_picker**: {'a': 1, 'b': 135, 'g': 122, 'r': 0} - Color in RGBA format.
*   **datasource**: "12__table" - Identifier for the datasource.
*   **js_columns**: ["color"] - JavaScript columns to inject.
*   **js_data_mutator**: "data => data.map(d => ({
    ...d,
    color: colors.hexToRGB(d.extraProps.color)
}));" - JavaScript function to mutate data.
*   **js_onclick_href**: "" - JavaScript function for onclick href.
*   **js_tooltip**: "" - JavaScript function for tooltip.
*   **line_column**: "path_json" - Column for line data.
*   **line_type**: "json" - Type of line data.
*   **line_width**: 150 - Width of lines.
*   **mapbox_style**: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" - Mapbox style URL.
*   **reverse_long_lat**: False - Whether to reverse longitude and latitude.
*   **row_limit**: 5000 - Row limit.
*   **slice_id**: 43 - ID of the slice.
*   **time_grain_sqla**: None - Time grain (not applicable).
*   **time_range**: " : " - Time range.
*   **viewport**: {'altitude': 1.5, 'bearing': 0, 'height': 1094, 'latitude': 37.73671752604488, 'longitude': -122.18885402582598, 'maxLatitude': 85.05113, 'maxPitch': 60, 'maxZoom': 20, 'minLatitude': -85.05113, 'minPitch': 0, 'minZoom': 0, 'pitch': 0, 'width': 669, 'zoom': 9.51847667620428} - Viewport settings.
*   **viz_type**: "deck_path" - Visualization type.

---

## Viz Type: big_number_total

### Chart Name: Big Number
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "big_number_total" - Visualization type.
*   **metric**: "count" - Metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **header_font_size**: 0.4 - Font size for the header.
*   **subheader_font_size**: 0.15 - Font size for the subheader.
*   **y_axis_format**: "SMART_NUMBER" - Format for Y-axis labels.
*   **time_format**: "smart_date" - Format for time values.
*   **extra_form_data**: {} - Additional form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: mixed_timeseries

### Chart Name: Mixed
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "mixed_timeseries" - Visualization type.
*   **x_axis**: "order_date" - X-axis column.
*   **time_grain_sqla**: "P1M" - Time grain.
*   **metrics**: [{'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'sales', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 734, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'DOUBLE PRECISION', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'SUM', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'SUM(sales)', 'optionName': 'metric_b9hph4jr9i_nayy40sodwl'}] - Metrics for primary series.
*   **groupby**: [] - Columns to group by.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **order_desc**: True - Order descending.
*   **row_limit**: 10000 - Row limit.
*   **truncate_metric**: True - Truncate metric values.
*   **comparison_type**: "values" - Comparison type.
*   **metrics_b**: ["count"] - Metrics for secondary series.
*   **groupby_b**: [] - Groupby for secondary series.
*   **adhoc_filters_b**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters for secondary series.
*   **order_desc_b**: True - Order descending for secondary series.
*   **row_limit_b**: 10000 - Row limit for secondary series.
*   **truncate_metric_b**: True - Truncate metric values for secondary series.
*   **comparison_type_b**: "values" - Comparison type for secondary series.
*   **annotation_layers**: [] - Annotation layers.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 15 - Y-axis title margin.
*   **y_axis_title_position**: "Left" - Y-axis title position.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **seriesType**: "echarts_timeseries_line" - Primary series type.
*   **opacity**: 0.2 - Opacity of primary series.
*   **markerSize**: 6 - Marker size for primary series.
*   **yAxisIndex**: 1 - Y-axis index for primary series.
*   **seriesTypeB**: "echarts_timeseries_bar" - Secondary series type.
*   **opacityB**: 0.2 - Opacity of secondary series.
*   **markerSizeB**: 6 - Marker size for secondary series.
*   **yAxisIndexB**: 0 - Y-axis index for secondary series.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **rich_tooltip**: True - Rich tooltip.
*   **tooltipTimeFormat**: "smart_date" - Tooltip time format.
*   **truncateXAxis**: True - Truncate X-axis.
*   **y_axis_bounds**: [None, None] - Y-axis bounds.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **y_axis_bounds_secondary**: [None, None] - Y-axis bounds for secondary.
*   **y_axis_format_secondary**: "SMART_NUMBER" - Y-axis format for secondary.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: tree_chart

### Chart Name: Tree
*   **datasource**: "8__table" - Identifier for the datasource.
*   **viz_type**: "tree_chart" - Visualization type.
*   **id**: "id" - Column for node ID.
*   **parent**: "parent" - Column for parent ID.
*   **name**: "name" - Column for node name.
*   **root_node_id**: "1" - ID of the root node.
*   **metric**: "count" - Metric used.
*   **adhoc_filters**: [] - Adhoc filters.
*   **row_limit**: 1000 - Row limit.
*   **layout**: "radial" - Layout style.
*   **node_label_position**: "top" - Position of node labels.
*   **child_label_position**: "top" - Position of child labels.
*   **symbol**: "emptyCircle" - Symbol for nodes.
*   **symbolSize**: 7 - Size of node symbols.
*   **roam**: False - Whether roaming is enabled.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: heatmap_v2

### Chart Name: Heatmap
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "heatmap_v2" - Visualization type.
*   **x_axis**: "product_line" - X-axis column.
*   **time_grain_sqla**: "P1D" - Time grain.
*   **groupby**: "deal_size" - Column to group by for rows.
*   **metric**: "count" - Metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 10000 - Row limit.
*   **sort_x_axis**: "alpha_asc" - Sort X-axis alphabetically ascending.
*   **sort_y_axis**: "alpha_asc" - Sort Y-axis alphabetically ascending.
*   **normalize_across**: "heatmap" - Normalization strategy.
*   **legend_type**: "continuous" - Legend type.
*   **linear_color_scheme**: "superset_seq_1" - Linear color scheme.
*   **xscale_interval**: -1 - X-scale interval.
*   **yscale_interval**: -1 - Y-scale interval.
*   **left_margin**: "auto" - Left margin.
*   **bottom_margin**: "auto" - Bottom margin.
*   **value_bounds**: [None, None] - Value bounds for color mapping.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **show_legend**: True - Show legend.
*   **show_percentage**: True - Show percentage.
*   **show_values**: True - Show values.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: gantt_chart

### Chart Name: Gantt
*   **datasource**: "61__table" - Identifier for the datasource.
*   **viz_type**: "gantt_chart" - Visualization type.
*   **slice_id**: 1495 - ID of the slice.
*   **start_time**: "start_time" - Column for start time.
*   **end_time**: "end_time" - Column for end time.
*   **y_axis**: "status" - Column for Y-axis.
*   **series**: "priority" - Column for series.
*   **subcategories**: True - Whether to show subcategories.
*   **tooltip_columns**: ["project", "phase"] - Columns to show in tooltip.
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'No filter', 'expressionType': 'SIMPLE', 'operator': 'TEMPORAL_RANGE', 'subject': 'start_time'}] - Adhoc filters.
*   **order_by_cols**: ["["status",false]"] - Columns to order by.
*   **row_limit**: 10000 - Row limit.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 50 - Y-axis title margin.
*   **color_scheme**: "supersetAndPresetColors" - Color scheme.
*   **show_legend**: True - Show legend.
*   **legendType**: "plain" - Legend type.
*   **legendOrientation**: "right" - Legend orientation.
*   **legendMargin**: 100 - Legend margin.
*   **zoomable**: False - Whether chart is zoomable.
*   **show_extra_controls**: False - Show extra controls.
*   **x_axis_time_bounds**: ["08:00:00", "19:00:00"] - X-axis time bounds.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **tooltipTimeFormat**: "smart_date" - Tooltip time format.
*   **tooltipValuesFormat**: "SMART_NUMBER" - Tooltip values format.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [9] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: waterfall

### Chart Name: Waterfall
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "waterfall" - Visualization type.
*   **x_axis**: "order_date" - X-axis column.
*   **time_grain_sqla**: "P3M" - Time grain.
*   **groupby**: [] - Columns to group by.
*   **metric**: {'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'sales', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 734, 'is_dttm': False, 'python_date_format': None, 'type': 'DOUBLE PRECISION', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'SUM', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'SUM(sales)', 'optionName': 'metric_uufmfvmm7_zhsh1h4vbh'} - Metric used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 10000 - Row limit.
*   **show_value**: True - Show value labels.
*   **increase_color**: {'r': 90, 'g': 193, 'b': 137, 'a': 1} - Color for increase.
*   **decrease_color**: {'r': 224, 'g': 67, 'b': 85, 'a': 1} - Color for decrease.
*   **total_color**: {'r': 102, 'g': 102, 'b': 102, 'a': 1} - Color for total.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **x_ticks_layout**: "auto" - Layout for X-axis ticks.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: bubble_v2

### Chart Name: Bubble
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "bubble_v2" - Visualization type.
*   **series**: "product_line" - Column for series.
*   **entity**: "deal_size" - Column for entity.
*   **x**: {'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'quantity_ordered', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 739, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'BIGINT', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'SUM', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'SUM(quantity_ordered)', 'optionName': 'metric_ieq28dvzapm_wsnd3sj3trn'} - X-axis metric.
*   **y**: {'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'country', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 754, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'TEXT', 'type_generic': 1, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'COUNT_DISTINCT', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'COUNT_DISTINCT(country)', 'optionName': 'metric_2pvgxo9w3dc_fazapv2jd65'} - Y-axis metric.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **size**: "count" - Size metric.
*   **order_desc**: True - Order descending.
*   **row_limit**: 10000 - Row limit.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **max_bubble_size**: "25" - Maximum bubble size.
*   **tooltipSizeFormat**: "SMART_NUMBER" - Tooltip size format.
*   **opacity**: 0.6 - Opacity of bubbles.
*   **x_axis_title_margin**: 30 - X-axis title margin.
*   **xAxisFormat**: "SMART_NUMBER" - X-axis format.
*   **y_axis_title_margin**: 30 - Y-axis title margin.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **truncateXAxis**: True - Truncate X-axis.
*   **y_axis_bounds**: [None, None] - Y-axis bounds.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: graph_chart

### Chart Name: Graph
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "graph_chart" - Visualization type.
*   **source**: "deal_size" - Column for source nodes.
*   **target**: "product_line" - Column for target nodes.
*   **metric**: "count" - Metric used for node values.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 10000 - Row limit.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **layout**: "circular" - Layout type for the graph.
*   **edgeSymbol**: "none,arrow" - Symbol for edges.
*   **roam**: True - Whether roaming is enabled.
*   **selectedMode**: "single" - Selection mode.
*   **baseNodeSize**: 20 - Base size for nodes.
*   **baseEdgeWidth**: 3 - Base width for edges.
*   **edgeLength**: 400 - Length of edges.
*   **gravity**: 0.3 - Gravity for layout.
*   **repulsion**: 1000 - Repulsion for layout.
*   **friction**: 0.2 - Friction for layout.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: histogram_v2

### Chart Name: Histogram
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "histogram_v2" - Visualization type.
*   **slice_id**: 130 - ID of the slice.
*   **column**: "quantity_ordered" - Column to use for histogram.
*   **groupby**: ["deal_size"] - Columns to group by.
*   **adhoc_filters**: [{'clause': 'WHERE', 'comparator': 'No filter', 'expressionType': 'SIMPLE', 'operator': 'TEMPORAL_RANGE', 'subject': 'order_date'}] - Adhoc filters.
*   **row_limit**: 10000 - Row limit.
*   **bins**: 10 - Number of bins for the histogram.
*   **normalize**: False - Whether to normalize the histogram.
*   **color_scheme**: "supersetAndPresetColors" - Color scheme.
*   **show_value**: False - Show value labels.
*   **show_legend**: True - Show legend.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: sankey_v2

### Chart Name: Sankey
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "sankey_v2" - Visualization type.
*   **source**: "product_line" - Column for source nodes.
*   **target**: "deal_size" - Column for target nodes.
*   **metric**: "count" - Metric used for link values.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 10000 - Row limit.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.

---

## Viz Type: echarts_timeseries_scatter

### Chart Name: Scatter Plot
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "echarts_timeseries_scatter" - Visualization type.
*   **x_axis**: "order_date" - X-axis column.
*   **time_grain_sqla**: "P1D" - Time grain.
*   **x_axis_sort_asc**: True - Sort X-axis ascending.
*   **x_axis_sort_series**: "name" - Sort series by name.
*   **x_axis_sort_series_ascending**: True - Sort series ascending.
*   **metrics**: ["count"] - Metrics used.
*   **groupby**: ["deal_size"] - Columns to group by.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **order_desc**: True - Order descending.
*   **row_limit**: 10000 - Row limit.
*   **truncate_metric**: True - Truncate metric values.
*   **show_empty_columns**: True - Show empty columns.
*   **comparison_type**: "values" - Comparison type.
*   **annotation_layers**: [] - Annotation layers.
*   **forecastPeriods**: 10 - Number of forecast periods.
*   **forecastInterval**: 0.8 - Forecast interval.
*   **x_axis_title_margin**: 15 - X-axis title margin.
*   **y_axis_title_margin**: 15 - Y-axis title margin.
*   **y_axis_title_position**: "Left" - Y-axis title position.
*   **sort_series_type**: "sum" - Sort series by sum.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **only_total**: True - Only show total.
*   **markerSize**: 6 - Marker size.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **x_axis_time_format**: "smart_date" - X-axis time format.
*   **rich_tooltip**: True - Rich tooltip.
*   **tooltipTimeFormat**: "smart_date" - Tooltip time format.
*   **y_axis_format**: "SMART_NUMBER" - Y-axis format.
*   **truncateXAxis**: True - Truncate X-axis.
*   **y_axis_bounds**: [None, None] - Y-axis bounds.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [13] - Dashboard IDs.

---

## Viz Type: radar

### Chart Name: Radar
*   **datasource**: "22__table" - Identifier for the datasource.
*   **viz_type**: "radar" - Visualization type.
*   **groupby**: ["product_line"] - Columns to group by.
*   **metrics**: ["count", {'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'price_each', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 733, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'DOUBLE PRECISION', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'AVG', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'AVG(price_each)', 'optionName': 'metric_ethqy44wrel_gsqbm609hxt'}, {'expressionType': 'SIMPLE', 'column': {'advanced_data_type': None, 'certification_details': None, 'certified_by': None, 'column_name': 'sales', 'description': None, 'expression': None, 'filterable': True, 'groupby': True, 'id': 734, 'is_certified': False, 'is_dttm': False, 'python_date_format': None, 'type': 'DOUBLE PRECISION', 'type_generic': 0, 'verbose_name': None, 'warning_markdown': None}, 'aggregate': 'SUM', 'sqlExpression': None, 'datasourceWarning': False, 'hasCustomLabel': False, 'label': 'SUM(sales)', 'optionName': 'metric_r5emvf2ybfe_blvnta3absu'}] - Metrics used.
*   **adhoc_filters**: [{'clause': 'WHERE', 'subject': 'order_date', 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter', 'expressionType': 'SIMPLE'}] - Adhoc filters.
*   **row_limit**: 10 - Row limit.
*   **color_scheme**: "supersetColors" - Color scheme.
*   **show_legend**: True - Show legend.
*   **legendType**: "scroll" - Legend type.
*   **legendOrientation**: "top" - Legend orientation.
*   **legendMargin**: "" - Legend margin.
*   **show_labels**: False - Show labels.
*   **label_type**: "value" - Label type.
*   **label_position**: "top" - Label position.
*   **number_format**: "SMART_NUMBER" - Number format.
*   **date_format**: "smart_date" - Date format.
*   **is_circle**: True - Whether the radar chart is circular.
*   **extra_form_data**: {} - Extra form data.
*   **dashboards**: [] - Dashboard IDs.
*   **annotation_layers**: [] - Annotation layers.