import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def preprocess_bet_stn(df):
    """
    Preprocess the 'BET STN' column in the DataFrame to replace spaces with hyphens.
    """
    df['BET STN'] = df['BET STN'].apply(lambda x: x.replace(' ', '-') if ' ' in x else x)
    return df

def parse_time(time_str):
    """
    Parse time in 'HH:MM' or 'HH.MM' format to a datetime.time object.
    """
    try:
        return datetime.strptime(time_str.strip(), "%H:%M").time()
    except ValueError:
        hours, minutes = map(int, time_str.strip().split('.'))
        return (datetime.min + timedelta(hours=hours, minutes=minutes)).time()

def parse_duration(duration_str):
    """
    Parse duration in 'HH.MM hrs' format to timedelta object.
    """
    hours, minutes = map(int, duration_str.split(' ')[0].split('.'))
    return timedelta(hours=hours, minutes=minutes)

def adjust_requests_to_corridor(df_requests, df_corridor):
    """
    Adjust requests to fit within the corridor block times.
    """
    df_requests['optimized_time_from'] = ""
    df_requests['optimized_time_to'] = ""
    df_requests['optimization_details'] = ""

    grouped_requests = df_requests.groupby(['BET STN', 'LINE'])
    
    for (bet_stn, line), group_requests in grouped_requests:
        corridor_block = df_corridor[(df_corridor['Section/ station'] == bet_stn) & 
                                     (df_corridor['Line'] == line)]

        details = ""
        if corridor_block.empty:
            corridor_start = parse_time("00:00")
            corridor_end = parse_time("04:00")
            details += f"No corridor block found for {bet_stn} and {line}. Using default 00:00-04:00.\n"
        else:
            corridor_start = parse_time(corridor_block.iloc[0]['From'].split(' ')[0])
            corridor_end = parse_time(corridor_block.iloc[0]['To'].split(' ')[0])
            details += f"Corridor block from {corridor_start} to {corridor_end}.\n"

        for idx, request in group_requests.iterrows():
            request_start = parse_time(request['D.FRM'])
            request_end = parse_time(request['D.TO'])
            
            if request_end < request_start:
                request_end = (datetime.combine(datetime.today(), request_end) + timedelta(days=1)).time()
            request_duration = (datetime.combine(datetime.today(), request_end) - datetime.combine(datetime.today(), request_start))

            optimized_start = max(request_start, corridor_start)
            optimized_end = (datetime.combine(datetime.today(), optimized_start) + request_duration).time()

            if optimized_end > corridor_end:
                optimized_start = corridor_start
                optimized_end = (datetime.combine(datetime.today(), corridor_start) + request_duration).time()
                details += f"Adjusted to corridor start.\n"
            else:
                details += f"Within corridor.\n"

            df_requests.loc[idx, 'optimized_time_from'] = optimized_start.strftime("%H:%M")
            df_requests.loc[idx, 'optimized_time_to'] = optimized_end.strftime("%H:%M")

            # Save the optimization details
            df_requests.loc[idx, 'optimization_details'] = details.strip()
            details = ""
    
    return df_requests

# Streamlit app
st.title('Request Optimization Tool')

# Upload CSV file for requests
requests_csv = st.file_uploader('Upload Request CSV', type='csv')

# Load corridor table from a predefined local file path
corridor_csv_path = 'corridor.csv'  # Replace with your local path to the corridor CSV
df_corridor = pd.read_csv(corridor_csv_path)

if requests_csv:
    df_requests = pd.read_csv(requests_csv)

    st.write("### Original Request Data")
    st.dataframe(df_requests)

    st.write("### Corridor Block Data")
    st.dataframe(df_corridor)

    # Preprocess 'BET STN' column
    df_requests = preprocess_bet_stn(df_requests)

    # Adjust requests to fit within the corridor block
    optimized_requests_df = adjust_requests_to_corridor(df_requests, df_corridor)

    st.write("### Optimized Request Data")
    st.dataframe(optimized_requests_df)

    # Download button for optimized CSV
    csv = optimized_requests_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Optimized CSV",
        data=csv,
        file_name='optimized_requests.csv',
        mime='text/csv'
    )
