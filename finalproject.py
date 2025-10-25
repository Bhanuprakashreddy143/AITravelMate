import streamlit as st
import json
import os
from serpapi import GoogleSearch
from agno.agent import Agent
from agno.tools.serpapi import SerpApiTools
from agno.models.google import Gemini
from datetime import datetime, timedelta
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="AI Travelmate",
    page_icon="✈️",
    layout="wide",
)

# --- API KEYS (Replace with your keys or use st.secrets) ---
SERPAPI_KEY = "7b16abd42c759d96f95b6e28f6d0ad199b437757867e0cd20ddc4a4f975344ce"
GOOGLE_API_KEY = "AIzaSyDiGlPvCPGR0RyPW671Vjnmpj3-rp97L8g"

if SERPAPI_KEY == "YOUR_SERPAPI_KEY" or GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY":
    st.error("🚨 Please replace 'YOUR_SERPAPI_KEY' and 'YOUR_GOOGLE_API_KEY' with your actual API keys.")
else:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# --- STYLING ---
st.markdown("""
<style>
    .stApp { background-color: #F0F2F6; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #F0F2F6; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    .stTabs [aria-selected="true"] { background-color: #FFFFFF; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 15px; text-align: center; background-color: #ffffff; box-shadow: 0 4px 8px 0 rgba(0,0,0,0.1); transition: 0.3s; }
    .card:hover { box-shadow: 0 8px 16px 0 rgba(0,0,0,0.2); }
    h1, h2, h3 { text-align: center; }
</style>""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'plan_generated' not in st.session_state:
    st.session_state.plan_generated = False
    st.session_state.cheapest_flights = []
    st.session_state.hotel_restaurants = []
    st.session_state.itinerary = []
    st.session_state.flight_params = {}
    st.session_state.destination_name = "Delhi"
    st.session_state.departure_date = datetime.now().date()
    st.session_state.return_date = datetime.now().date() + timedelta(days=5)

# --- HELPER FUNCTIONS ---
def get_city_name_from_iata(iata_code: str, api_key: str) -> str:
    params = {"engine": "google", "q": f"what city is iata code {iata_code}", "api_key": api_key}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        answer = results.get("answer_box", {}).get("answer")
        if answer: return answer.split('/')[0].strip()
        knowledge_graph = results.get("knowledge_graph", {})
        if knowledge_graph.get("description"): return knowledge_graph.get("description")
    except Exception: pass
    return iata_code.upper()

def format_datetime(iso_string):
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%d %H:%M")
        return dt.strftime("%b-%d, %Y | %I:%M %p")
    except: return "N/A"

def parse_json_from_ai(raw_string):
    match = re.search(r'```json\n(.*)\n```', raw_string, re.DOTALL)
    if match:
        json_string = match.group(1)
        try: return json.loads(json_string)
        except json.JSONDecodeError:
            st.error("AI returned invalid JSON.")
            return None
    st.warning("AI did not return expected JSON format.")
    return None

def get_image_url(place_name: str, api_key: str) -> str:
    if not place_name: return "https://via.placeholder.com/400x300.png?text=No+Image"
    params = {"engine": "google_images", "q": place_name, "api_key": api_key}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results["images_results"][0]["thumbnail"]
    except Exception:
        return "https://via.placeholder.com/400x300.png?text=Image+Not+Found"

def get_place_details(place_name: str, location: str, api_key: str) -> dict:
    if not place_name: return {}
    params = {"engine": "google_local", "q": f"{place_name} {location}", "api_key": api_key}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        place_data = results["local_results"][0]
        return {"website": place_data.get("website"), "address": place_data.get("address"), "phone": place_data.get("phone")}
    except Exception: return {}

def get_weather_forecast(destination: str, api_key: str) -> dict:
    params = {"engine": "google", "q": f"Weather in {destination}", "api_key": api_key}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results.get("answer_box", {})
    except Exception as e:
        st.error(f"An error occurred while fetching weather data: {e}")
        return {}

def get_weather_icon(condition: str) -> str:
    """Returns a weather emoji based on the condition string."""
    if not condition: return "❓"
    condition = condition.lower()
    if "sun" in condition or "clear" in condition: return "☀️"
    if "cloud" in condition: return "☁️"
    if "rain" in condition or "shower" in condition: return "🌧️"
    if "storm" in condition: return "⛈️"
    if "snow" in condition: return "❄️"
    if "mist" in condition or "fog" in condition: return "🌫️"
    return "🌍"

# --- SIDEBAR FOR USER INPUTS ---
with st.sidebar:
    st.image("https://www.pngfind.com/pngs/m/669-6691661_new-travel-peeps-travel-agency-logo-png-transparent.png", width=100)
    st.title("AI Travelmate")
    st.markdown("---")

    with st.expander("✈️ **Trip Details**", expanded=True):
        source = st.text_input("Departure City (IATA Code)", "BOM", help="e.g., BOM for Mumbai")
        destination = st.text_input("Destination City (IATA Code)", "DEL", help="e.g., DEL for Delhi")
        departure_date = st.date_input("Departure Date", value=st.session_state.departure_date)
        return_date = st.date_input("Return Date", value=st.session_state.return_date)
        num_days = (return_date - departure_date).days + 1
        st.info(f"Your trip duration is **{num_days} days**.")

    with st.expander("👤 **Traveler Profile**"):
        travel_theme = st.selectbox("Travel Theme:", ["💑 Couple Getaway", "👨‍👩‍👧‍👦 Family Vacation", "🏔️ Adventure Trip", "🧳 Solo Exploration"])
        activity_preferences = st.text_area("Activities You Enjoy:", "Exploring historical sites, trying local food.")
        budget = st.radio("💰 Budget Preference:", ["Economy", "Standard", "Luxury"], horizontal=True)

    with st.expander("📋 **Preferences & Essentials**"):
        hotel_rating = st.selectbox("🏨 Preferred Hotel Rating:", ["Any", "3⭐", "4⭐", "5⭐"])

    if st.button("🚀 Generate Travel Plan", use_container_width=True, type="primary"):
        st.session_state.departure_date = departure_date
        st.session_state.return_date = return_date
        
        with st.spinner("Finding destination city name..."):
            destination_name = get_city_name_from_iata(destination, SERPAPI_KEY)
            st.session_state.destination_name = destination_name
        
        with st.spinner("Step 1/4: Searching for flights..."):
            flight_params = {"engine": "google_flights", "departure_id": source, "arrival_id": destination, "outbound_date": str(departure_date), "return_date": str(return_date), "currency": "INR", "hl": "en", "api_key": SERPAPI_KEY}
            search = GoogleSearch(flight_params)
            results = search.get_dict()
            st.session_state.cheapest_flights = sorted(results.get("best_flights", []), key=lambda x: x.get("price", float("inf")))[:3]
            st.session_state.flight_params = flight_params
        researcher = Agent(
            name="Researcher", instructions=["Gather detailed info on the destination, attractions, and activities matching user interests."],
            model=Gemini(id="gemini-2.0-flash-exp"), tools=[SerpApiTools(api_key=SERPAPI_KEY)],
        )
        hotel_restaurant_finder = Agent(
            name="Hotel & Restaurant Finder",
            instructions=[
                "Find top-rated hotels and restaurants based on user preferences.",
                "Provide results in a structured JSON format. Each item must have 'name', 'type' (Hotel/Restaurant), 'rating', 'description', and 'image_url'."
            ],
            model=Gemini(id="gemini-2.0-flash-exp"), tools=[SerpApiTools(api_key=SERPAPI_KEY)],
        )
        planner = Agent(
            name="Planner",
            instructions=[
                "Create a detailed, day-by-day itinerary based on all provided data.",
                "The output must be a valid JSON list, where each item represents a day with keys: 'day', 'title', 'morning', 'afternoon', 'evening'."
            ],
            model=Gemini(id="gemini-2.0-flash-exp"),
        )

        with st.spinner("Step 2/4: Researching your destination..."):
            research_prompt = f"Research best attractions and activities in {st.session_state.destination_name} for a {num_days}-day {travel_theme.lower()} trip. Interests: {activity_preferences}. Budget: {budget}."
            research_results = researcher.run(research_prompt, stream=False)

        with st.spinner("Step 3/4: Finding hotels & restaurants..."):
            hotel_restaurant_prompt = (f"Find 3 top-rated hotels and 3 best restaurants in {st.session_state.destination_name} for a {travel_theme.lower()} trip. Budget: {budget}. Hotel Rating: {hotel_rating}. Return as a single JSON list in ```json ... ```. Each item must have keys: 'name', 'type' ('Hotel' or 'Restaurant'), 'rating', and 'description'.")
            hotel_restaurant_results = hotel_restaurant_finder.run(hotel_restaurant_prompt, stream=False)
            st.session_state.hotel_restaurants = parse_json_from_ai(hotel_restaurant_results.content)

        with st.spinner("Step 4/4: Building your itinerary..."):
            planning_prompt = (f"Create a {num_days}-day itinerary for a {travel_theme.lower()} trip to {st.session_state.destination_name} based on: Interests: {activity_preferences}, Research: {research_results.content}, and Hotel/Restaurant options: {hotel_restaurant_results.content}. Return as a single JSON list in ```json ... ```. Each day object must have keys: 'day', 'title', and objects for 'morning', 'afternoon', 'evening'. Each object must have 'activity' and 'place_name' keys.")
            itinerary_results = planner.run(planning_prompt, stream=False)
            st.session_state.itinerary = parse_json_from_ai(itinerary_results.content)

        st.session_state.plan_generated = True
        st.success("Your travel plan is ready!")
        st.balloons()

# --- MAIN CONTENT AREA ---
if not st.session_state.plan_generated:
    st.header("✨ Your AI-Powered Travel Planner Awaits")
    st.markdown("Tell us your travel dreams in the sidebar, and let our AI craft your perfect getaway!")
    st.image("https://images.unsplash.com/photo-1501785888041-af3ef285b470?q=80&w=2070", caption="Your next adventure starts here.")
else:
    st.header(f"Your {st.session_state.destination_name} Adventure Plan")
    tab1, tab2, tab3, tab4 = st.tabs(["✈️ Flights", "🏨 Stays & Eats", "🗺️ Itinerary", "🌦️ Weather"])

    with tab1:
        st.subheader("Top 3 Cheapest Flight Options")
        if st.session_state.cheapest_flights:
            cols = st.columns(len(st.session_state.cheapest_flights))
            for idx, flight in enumerate(st.session_state.cheapest_flights):
                with cols[idx]:
                    st.markdown(f"""<div class="card" style="height: 350px;">
                        <img src="{flight.get('airline_logo', '')}" width="50" style="margin-bottom: 10px;"/>
                        <h5 style="margin-bottom: 5px;">{flight.get('flights', [{}])[0].get('airline', 'Unknown')}</h5>
                        <p style="font-size: 24px; color: green; font-weight: bold;">₹{flight.get('price', 'N/A')}</p>
                        <p style="font-size: 14px;">{format_datetime(flight.get('flights', [{}])[0].get('departure_airport', {}).get('time'))} → {format_datetime(flight.get('flights', [{}])[-1].get('arrival_airport', {}).get('time'))}</p>
                        <p style="font-size: 14px;">Duration: {flight.get('total_duration', 'N/A')} min</p>
                        <a href="https://www.google.com/flights" target="_blank" style="text-decoration: none;"><button style="width: 100%; border: none; background-color: #FF4B4B; color: white; padding: 8px; border-radius: 5px;">Book Now</button></a>
                    </div>""", unsafe_allow_html=True)
        else:
            st.warning("⚠️ No flight data available.")

    with tab2:
        st.subheader("Recommended Hotels & Restaurants")
        if st.session_state.hotel_restaurants:
            def create_card(item):
                place_name = item.get('name', '')
                image_url = get_image_url(place_name, SERPAPI_KEY)
                details = get_place_details(place_name, st.session_state.destination_name, SERPAPI_KEY)
                website_button = f'<a href="{details.get("website")}" target="_blank" style="text-decoration: none;"><button style="width: 100%; border: none; background-color: #007bff; color: white; padding: 8px; border-radius: 5px; margin-top: 10px;">Visit Website</button></a>' if details.get("website") else ""
                return f"""<div class="card" style="height: 480px; display: flex; flex-direction: column; justify-content: space-between;"><div>
                    <img src="{image_url}" style="width: 100%; height: 200px; object-fit: cover; border-radius: 5px;"/>
                    <h5 style="margin-top: 10px; margin-bottom: 5px;">{place_name}</h5>
                    <p style="font-size: 14px; margin-bottom: 5px;"><b>Rating:</b> {item.get('rating', 'N/A')} ⭐</p>
                    <p style="font-size: 13px;"><i>{item.get('description', '')}</i></p>
                    <p style="font-size: 12px; color: #555;">📍 {details.get("address", "")}</p></div>{website_button}</div>"""
            
            hotels = [item for item in st.session_state.hotel_restaurants if item.get('type') == 'Hotel']
            restaurants = [item for item in st.session_state.hotel_restaurants if item.get('type') == 'Restaurant']
            
            if hotels:
                st.markdown("#### 🏨 Top Hotel Picks")
                for i in range(0, len(hotels), 3):
                    cols = st.columns(3)
                    for idx, item in enumerate(hotels[i:i+3]):
                        cols[idx].markdown(create_card(item), unsafe_allow_html=True)
            if restaurants:
                st.markdown("---")
                st.markdown("#### 🍜 Top Dining Spots")
                for i in range(0, len(restaurants), 3):
                    cols = st.columns(3)
                    for idx, item in enumerate(restaurants[i:i+3]):
                        cols[idx].markdown(create_card(item), unsafe_allow_html=True)
        else:
            st.info("No hotel or restaurant recommendations were generated.")

    with tab3:
        st.subheader("Your Day-by-Day Personalized Itinerary")
        if st.session_state.itinerary:
            for day_plan in st.session_state.itinerary:
                with st.expander(f"**Day {day_plan.get('day')}: {day_plan.get('title', '')}**"):
                    def display_activity(plan_key, emoji):
                        plan = day_plan.get(plan_key, {})
                        if plan and plan.get('activity'):
                            place_name = plan.get('place_name', '')
                            st.markdown(f"**{emoji} {plan_key.capitalize()}:** {plan.get('activity')}")
                            if place_name:
                                details = get_place_details(place_name, st.session_state.destination_name, SERPAPI_KEY)
                                if details.get("website"):
                                    st.markdown(f"🔗 [**More Info / Official Website**]({details['website']})")
                            image_url = get_image_url(place_name, SERPAPI_KEY)
                            st.image(image_url, width=400, caption=place_name)
                            st.markdown("---")
                    display_activity('morning', '🌅')
                    display_activity('afternoon', '☀️')
                    display_activity('evening', '🌙')
        else:
            st.info("No detailed itinerary was generated.")

    with tab4:
        st.subheader(f"Weather Outlook for {st.session_state.destination_name}")
        weather_data = get_weather_forecast(st.session_state.destination_name, SERPAPI_KEY)

        if weather_data and weather_data.get("forecast"):
            trip_dates = {st.session_state.departure_date + timedelta(days=i) for i in range((st.session_state.return_date - st.session_state.departure_date).days + 1)}
            today = datetime.now().date()
            filtered_forecast = []

            for i, day_forecast in enumerate(weather_data["forecast"]):
                current_forecast_date = today + timedelta(days=i)
                if current_forecast_date in trip_dates:
                    day_forecast['full_date'] = current_forecast_date
                    filtered_forecast.append(day_forecast)

            if not filtered_forecast:
                st.info("A detailed forecast for your specific travel dates is not yet available.")
            else:
                first_day = filtered_forecast[0]
                temp_data = first_day.get("temperature", {})
                summary_text = (
                    f"Your trip starts on **{first_day['full_date'].strftime('%A, %B %d')}**. "
                    f"Expect **{first_day.get('weather', 'clear skies')}** with a high of "
                    f"**{temp_data.get('high')}°** and a low of **{temp_data.get('low')}°**."
                )
                st.markdown(summary_text)
                st.markdown("---")

                for day_forecast in filtered_forecast:
                    temp_data = day_forecast.get("temperature", {})
                    icon = get_weather_icon(day_forecast.get("weather"))
                    
                    st.markdown(f"#### {day_forecast.get('day')}, {day_forecast['full_date'].strftime('%b %d')}")
                    st.markdown(
                        f"""
                        - **Weather:** {icon} {day_forecast.get('weather', 'N/A')}
                        - **High:** {temp_data.get('high')}°
                        - **Low:** {temp_data.get('low')}°
                        - **Precipitation:** {day_forecast.get('precipitation', 'N/A')}
                        - **Wind:** {day_forecast.get('wind', 'N/A')}
                        """
                    )
                    st.markdown("---")

        elif weather_data and weather_data.get("temperature"):
            current = weather_data
            st.info("Could not retrieve a multi-day forecast. Here is the current weather:")
            st.markdown(f"""<div class="card">
                <img src="{current.get("thumbnail")}" alt="weather icon" width="80">
                <h2>{current.get('temperature')}°{current.get('temperature_unit', 'C')} in {st.session_state.destination_name}</h2>
                <p>{current.get('condition')}</p>
                <p>Humidity: {current.get('humidity')} | Wind: {current.get('wind')}</p>
            </div>""", unsafe_allow_html=True)
        else:
            st.warning("Could not retrieve weather information at this time.")