# Standard library imports
import os
from datetime import datetime, timedelta, date

# Third-party library imports
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import polib

# Custom module imports
from etl_process import FetchDatasetList, FetchData, FetchChineseName, CleanData, ExtractMarketCloseDate
from random_stock_select import MonkeySelectStock
from regular_investment_plan import FilterMonths, FilterQuarters, CalculateInvestmentReturns

DIR_PATH = os.path.dirname(os.path.realpath(__file__))
KEY_PATH = os.path.join(DIR_PATH, "secret_info/stockaroo-privatekey.json")

# Used for the data frame in random stock selection experiment
CSS = """
<style>
    table {
        width: 100%;
        table-layout: fixed;
        word-wrap: break-word;
    }
    th, td {
        padding: 10px;
        text-align: left;
    }
</style>
"""



def filter_date(data, code):
    """
    Filter stock data based within specific date range
    
    Args:
        data (dataframe): The data frame of stock data.
        code (int): The code indicating the date range of data to filter.
    
    Returns:
        dataframe: The filtered stock data or the original data if the the date range indicates
        all available dates
    """
    code_day_map = {
        0: 30,
        1: 90,
        2: 150,
        3: 365,
        4: 1825
    }
    if code in code_day_map:
        return data[-code_day_map[code]:]
    
    return data

def get_valid_end_quarter():
    """
    Get the valid end quarter for date range available.
    
    Returns:
        tuple: A tuple containing the year and the valid quarter.
    """
    today = date.today()
    year = today.year
    month = today.month

    if month<4:
        year -= 1
        quarter = 4
    elif month<7:
        quarter = 1
    elif month<10:
        quarter = 2
    else:
        quarter = 3
    return year, quarter

def get_valid_end_year():
    """
    Get the valid end year for date range available.
    
    Returns:
        tuple: A tuple containing the valid year.
    """
    year = date.today().year
    year -= 1
    return year

def progress_callback(step, total_steps):
    progress_percentage = int(step / total_steps * 100)
    progress_bar.progress(progress_percentage)


def modify_detail_df(stocks_group, profit_ratios_group, dates, _t=None):
    """
    Format detailed stock data for display.
    
    Args:
        stock_groups (list): List of lists containing stock symbols.
        profit_ratio_groups (list): List of lists containing profit ratios for each stock.
        dates (list): List of dates for the date intervals.
    
    Returns:
        pd.DataFrame: DataFrame containing formatted stock details with execution periods.
    """

    # Create date intervals for the data frame
    date_intervals = [
        f"{dates[i]} to {str(datetime.strptime(dates[i+1], '%Y-%m-%d')-timedelta(days=1)).split(' ')[0]}" 
        for i in range(len(dates)-1)
        ]

    # Create formatted information for each stock
    formatted_infos = []
    for stocks, profits in zip(stocks_group, profit_ratios_group):
        info_list = [
            f"<p style='color: red;'>{stock}<br>▲{profit}%</p>" if profit > 0 else f"<p style='color: green;'>{stock}<br>▼{str(profit)[1:]}%</p>"
            for stock, profit in zip(stocks, profits)
        ]
        formatted_infos.append(info_list)

    info_df = pd.DataFrame(formatted_infos)

    # Set column names for stocks
    info_df.columns = [_t("Stock-")+str(i+1) for i in range(len(stocks_group[0]))]

    # Add date intervals as a new column
    info_df[_t("Portfolio Holding Period")] = date_intervals

    # Reorder columns to place "執行期間" at the front
    columns = [_t("Portfolio Holding Period")] + [_t("Stock-")+str(i+1) for i in range(len(stocks_group[0]))]
    info_df = info_df[columns]

    return info_df

# Define a function to determine the color based on the value
def get_color(value):
    return "red" if value > 0 else "green"

# Define a function to format the value with a "+" sign if positive
def format_value(value):
    return f"+{value}%" if value > 0 else str(value)+"%"


def get_translation(language):
    localedir = os.path.join(os.path.dirname(__file__), 'translations')
    po_file = os.path.join(localedir, language, 'messages.po')
    po = polib.pofile(po_file)
    translations = {entry.msgid: entry.msgstr for entry in po}
    return translations

# Define the available languages
languages = {'English': 'en', 'Traditional Chinese': 'zh_TW'}

# Create a selectbox for language selection
selected_language = st.sidebar.selectbox('Select Language', options=list(languages.keys()))

# Load the translation function based on the selected language
translations = get_translation(languages[selected_language])
_t = lambda s: translations.get(s, s)

tab_graph, tab_dollar_cost_averaging, tab_random_strategy = st.tabs([_t("Stock Trend"), _t("Regular Investment Plan"), _t("Random Stock Selection Plan")])



with tab_graph:
    # Fetch the list of stock IDs
    stock_list = FetchChineseName(KEY_PATH)

    # Select a stock from the list
    selected_stock = st.selectbox(_t("Stock List"), stock_list, key="G1")
    selected_stock = str("s" + selected_stock.split("-")[0])

    # Fetch and clean data for the selected stock
    raw_data = FetchData("stock", selected_stock, KEY_PATH)
    cleaned_data = CleanData(raw_data)
    market_close_dates = ExtractMarketCloseDate(cleaned_data)
    
    # Map the duration to filter codes
    duration_map = {
        _t("1M"): 0,
        _t("3M"): 1,
        _t("5M"): 2,
        _t("1Y"): 3,
        _t("5Y"): 4,
        _t("All"): 5
    }

    # Select the duration for plotting
    selected_duration = st.radio(
        _t("Please select the length of the date"),
        list(duration_map.keys()),
        horizontal=True
    )

    # Filter data based on the selected duration
    filter_code = duration_map[selected_duration]
    filtered_data = filter_date(cleaned_data, filter_code)

    # Create the line plot
    line_plot = go.Scatter(
        x=filtered_data["date"],
        y=filtered_data["close"],
        mode="lines"
    )
    fig = go.Figure()
    fig.add_trace(line_plot)

    # Update the x-axis to exclude market close dates
    fig.update_xaxes(rangebreaks=[dict(values=market_close_dates)])

    # Display the plot
    st.plotly_chart(fig, use_container_width=True)

with tab_dollar_cost_averaging:

    # Set the title of the app
    st.title("Regular Investment Plan")
    st.subheader("Select Monthly Investment Account")

    # Create a text input widget for monthly investment amount
    user_input = st.text_input("Money you invest monthly", value=1000)
    MIA = int(user_input)  # Default to 1000 if no input

    # Add a select box for the stock code at the top
    stock_list = FetchChineseName(KEY_PATH)
    selected_stock = st.selectbox("Stock List", stock_list, key="RIPS7")
    selected_stock = "s"+selected_stock.split("-")[0]


    # Select duration type: month, quarter, or year
    duration_type = st.selectbox("Select Duration Type:", ["Month", "Quarter", "Year"], key="RIPS1")

    st.subheader("Select Starting and Ending Date")
    # Load the stock data file based on the selected stock code
    data = FetchData("stock", selected_stock, KEY_PATH)
    data = CleanData(data)
    data0050 = FetchData("stock", "s0050", KEY_PATH)
    data0050 = CleanData(data0050)
    data['date'] = pd.to_datetime(data['date'])
    data0050['date'] = pd.to_datetime(data0050['date'])

    # Extract month, quarter, and year
    data['month'] = data['date'].dt.month
    data['year'] = data['date'].dt.year
    data['quarter'] = data['date'].dt.to_period('Q')
    data0050['month'] = data0050['date'].dt.month
    data0050['year'] = data0050['date'].dt.year
    data0050['quarter'] = data0050['date'].dt.to_period('Q')

    # Quarter Dictionary
    quarter_month_map = {
    "Q1": (1, 3),
    "Q2": (4, 6),
    "Q3": (7, 9),
    "Q4": (10, 12)
    }

    # Find the max and min dates in the file
    min_date = data['date'].min()
    max_date = data['date'].max()

    # Get the years range based on the min and max dates
    years = list(range(min_date.year, max_date.year + 1))

    if duration_type == "Month":
        start_year = st.selectbox("Start Year:", years, index=len(years) - 1, key="RIPS3")
        valid_start_months = FilterMonths(start_year, min_date, max_date)
        start_month = st.selectbox("Start Month:", valid_start_months, format_func=lambda x: datetime(1900, x, 1).strftime('%B'), key="RIPS2")

        end_year = st.selectbox("End Year:", years, index=len(years) - 1, key="RIPS4")
        valid_end_months = FilterMonths(end_year, min_date, max_date)
        end_month = st.selectbox("End Month:", valid_end_months, format_func=lambda x: datetime(1900, x, 1).strftime('%B'), key="RIPS5")
        
    elif duration_type == "Quarter":
        start_year = st.selectbox("Start Year:", years, index=len(years) - 1, key="RIPS3")
        valid_start_quarters = FilterQuarters(start_year, min_date, max_date)
        start_quarter = st.selectbox("Start Quarter:", valid_start_quarters, key="RIPS5")

        end_year = st.selectbox("End Year:", years, index=len(years) - 1, key="RIPS4")
        valid_end_quarters = FilterQuarters(end_year, min_date, max_date)
        end_quarter = st.selectbox("End Quarter:", valid_end_quarters, key="RIPS6")

        start_month = quarter_month_map[start_quarter][0]
        end_month = quarter_month_map[end_quarter][1]

    elif duration_type == "Year":
        start_year = st.selectbox("Start Year:", years, index=len(years) - 1, key="RIPS3")
        end_year = st.selectbox("End Year:", years, index=len(years) - 1, key="RIPS4")

        start_month = 1
        end_month = 12

    if start_year and start_month and end_year and end_month:
        start_date = datetime(start_year, start_month, 1)
        end_date = datetime(end_year, end_month, 1) + pd.offsets.MonthEnd(1)
        if end_date in data['date'].values:
            end_date = end_date
        else:
            end_date = max(data['date'])
        # Filter the data based on the selected date range
        filtered_data = data.loc[(data['date'] >= start_date) & (data['date'] <= end_date)].copy()
        filtered_data0050 = data0050.loc[(data0050['date'] >= start_date) & (data0050['date'] <= end_date)].copy()

        duration, cost, revenue, ROI = CalculateInvestmentReturns(filtered_data, duration_type, MIA)
        _, _, _, ROI0050 = CalculateInvestmentReturns(filtered_data0050, duration_type, MIA)

        if duration_type == "Month":
            duration_label = 'Duration (Months)'
        elif duration_type == "Quarter":
            duration_label = 'Duration (Quarters)'
        elif duration_type == "Year":
            duration_label = 'Duration (Years)'

        result = pd.DataFrame({
            duration_label: duration,
            'Cost': cost,
            'Revenue': revenue,
            'Return on Investment (%)': ROI
        })

        st.subheader("Investment Summary Table")
        st.write(f"Investment Duration: {start_date.strftime(r'%Y-%m-%d')} to {end_date.strftime(r'%Y-%m-%d')}")
        st.markdown(f'<p style="color:gray; font-style:italic;">The ROI of Stock 0050 is {ROI0050[-1]} in this duration</p>', unsafe_allow_html=True)

        fig = go.Figure(data=go.Table(
            header=dict(values=list(result[[duration_label, 'Cost', 'Revenue', 'Return on Investment (%)']].columns),
                        fill_color='#FDBE72',
                        align='center'),
            cells=dict(values=[result[duration_label], result['Cost'], result['Revenue'], result['Return on Investment (%)']],
                        fill_color='#E5ECF6',
                        align='left'))
        )

        fig.update_layout(margin=dict(l=5, r=5, b=10, t=10),
                            paper_bgcolor='white')

        st.write(fig)
    
    else:
        st.write("No data available for the selected date range.")

with tab_random_strategy:

    # Select the duration type
    duration_type = st.selectbox(_t("Portfolio Turnover Frequency:"), [_t("Quarter"), _t("Year")], key="RSS1")



    if duration_type == _t("Quarter"):
        quarter_month_map = {
        "Q1": (1, 3),
        "Q2": (4, 6),
        "Q3": (7, 9),
        "Q4": (10, 12)
        }
        valid_year, valid_quarter = get_valid_end_quarter()

        # Select start year and quarter
        years = list(np.arange(2018, valid_year+1))

        start_year = st.selectbox(_t("Start Year:"), years, key="RSS3")
        quarters_select = ["Q1", "Q2", "Q3", "Q4"][:valid_quarter if start_year == valid_year else 4]
        start_quarter = st.selectbox(_t("Start Quarter:"), quarters_select, key="RSS5")
        start_month = quarter_month_map[start_quarter][0]
        start_date = f"{start_year}-{str(start_month).zfill(2)}"

        # Select end year and quarter
        end_year = st.selectbox(_t("End Year:"), years, key="RSS4")
        quarters_select = ["Q1", "Q2", "Q3", "Q4"][:valid_quarter if end_year == valid_year else 4]
        end_quarter = st.selectbox(_t("End Quarter:"), quarters_select, key="RSS6")
        end_month = quarter_month_map[end_quarter][1]
        end_date = f"{end_year}-{str(end_month).zfill(2)}"

    elif duration_type == _t("Year"):
        valid_year = get_valid_end_year()
        years = list(np.arange(2018, valid_year+1))

        # Select start year
        start_year = st.selectbox(_t("Start Year:"), years, key="RSS3")
        start_date = f"{start_year}-01"

        # Select end year
        end_year = st.selectbox(_t("End Year:"), years, key="RSS4")
        end_date = f"{end_year+1}-01"

    # Select stock category
    options = [_t("All"), _t("ETF"), _t("Financial and Insurance"), 
               _t("Electrical and Mechanical"), _t("Electronic Industry"), 
               _t("Telecommunications and Networking Industry"), _t("Semiconductor Industry"), 
               _t("Computer and Peripheral Equipment Industry")]
    choice = st.radio(_t("Please select an industry"), options)


    # Select number of stocks 
    num_stock = st.selectbox(_t("Number of stocks"), [i+1 for i in range(5)])

    progress_bar = st.progress(0)
    if st.button(_t("Start")):
        if end_year <= start_year:
            st.write(_t("Please select a valid date range (End year > Start year)"))
        else:
            new_balances, new_balances_0050, dates, profit_ratios_group, stocks_group = MonkeySelectStock(
                start_date, end_date, duration_type, num_stock, choice, 1000, KEY_PATH, progress_callback
            )

            df_plot = pd.DataFrame({
                "balance" : new_balances,
                "balance_0050" : new_balances_0050,
                "date" : dates
            })

            

            # Plot the balance over time
            fig = px.line(df_plot, x="date", y=["balance", "balance_0050"], title=_t("Balance of Random Stock Selection Plan"))
            st.plotly_chart(fig)


            # Provide summary statistics
            profit_ratio_random = np.round((new_balances[-1]-1000)/1000*100, 2)
            profit_ratio_0050 = np.round((new_balances_0050[-1]-1000)/1000*100, 2)
            profit_ratio_difference = np.round(profit_ratio_random-profit_ratio_0050, 2)
            

            html_code = f"""
            <style>
            .container {{
                display: flex;
                justify-content: space-around;  /* Use space-around to center the metrics */
                margin-bottom: 20px;
            }}

            .metric {{
                text-align: center;
                position: relative;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-width: 220px; /* Set a minimum width to ensure space between metrics */
            }}

            .metric::after {{
                content: '';
                position: absolute;
                right: -10px; /* Adjust the position to be just outside the padding */
                top: 10%; /* Adjust this value to center the line vertically */
                height: 80%; /* Adjust this value to change the line height */
                border-right: 1px solid #e0e0e0;
            }}

            .metric:last-child::after {{
                content: none;
            }}

            .metric-title {{
                font-size: 16px;
                white-space: nowrap; /* Prevents breaking into multiple lines */
            }}

            .metric-value {{
                font-size: 32px;
                font-weight: bold;
            }}
            </style>

            <div class="container">
                <div class="metric">
                    <div class="metric-title">{_t("Return Rate of Random Stock Selection Plan")}</div>
                    <div class="metric-value" style="color: {get_color(profit_ratio_random)};">{format_value(profit_ratio_random)}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">{_t("Return Rate of 0050")}</div>
                    <div class="metric-value" style="color: {get_color(profit_ratio_0050)};">{format_value(profit_ratio_0050)}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">{_t("Comparison with 0050")}</div>
                    <div class="metric-value" style="color: {get_color(profit_ratio_difference)};">{format_value(profit_ratio_difference)}</div>
                </div>
            </div>
            """

            st.markdown(html_code, unsafe_allow_html=True)

            # Displayed detailed information
            df_detail_info = modify_detail_df(stocks_group, profit_ratios_group, dates, _t)
            st.markdown(CSS+df_detail_info.to_html(escape=False, index=False), unsafe_allow_html=True)

