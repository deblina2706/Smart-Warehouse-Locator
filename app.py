from flask import Flask, render_template, request, jsonify
import pandas as pd
from geopy.distance import geodesic
from pulp import LpProblem, LpVariable, LpMinimize, lpSum, LpBinary
import requests
import random

app = Flask(__name__)

# Load data
store_locations = pd.read_csv('store_locations.csv')
warehouse_locations = pd.read_csv('warehouse_locations.csv')

# API configuration
API_KEY = 'a942efba9a957dfac3687f5972eee479'
GOOGLE_API_KEY = 'AIzaSyD199nguuWODwT1FfiTEDqcbQxc1PBQf6Q'

@app.route('/')
def index():
    # Initial rendering without optimalWarehouse
    return render_template('index.html', stores=store_locations.to_dict(orient='records'))

@app.route('/optimal_warehouse', methods=['POST'])
def optimal_warehouse():
    selected_stores_ids = request.json.get('selectedStoreIds')
    optimization_criterion = request.json.get('optimizationCriterion')
    selected_stores = store_locations[store_locations['Store_ID'].isin(selected_stores_ids)]

    # Ensure all selected stores are from the same city
    selected_city = selected_stores['City'].iloc[0]
    selected_stores = selected_stores[selected_stores['City'] == selected_city]

    # Filter warehouses to only include those in the selected city
    filtered_warehouse_locations = warehouse_locations[warehouse_locations['City'] == selected_city]

    def calculate_distance(lat1, lon1, lat2, lon2):
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers

    warehouse_distances = []

    for _, warehouse in filtered_warehouse_locations.iterrows():
        total_distance = 0
        for _, store in selected_stores.iterrows():
            distance = calculate_distance(store['Latitude'], store['Longitude'], warehouse['Latitude'], warehouse['Longitude'])
            total_distance += distance
        warehouse_distances.append({
            'Warehouse_ID': warehouse['Warehouse_ID'],
            'Total_Distance': total_distance,
            'Cost': warehouse['Cost'],
            'Name': warehouse['Name'],
            'Latitude': warehouse['Latitude'],
            'Longitude': warehouse['Longitude'],
            'Connectivity': warehouse['Connectivity'],
            'Capacity': warehouse['Capacity'],
            'Ownership': warehouse['Ownership'],
            'City': warehouse['City']
        })

    # Set up the optimization problem
    prob = LpProblem("Warehouse_Selection", LpMinimize)

    # Create a binary variable for each warehouse
    warehouse_vars = {row['Warehouse_ID']: LpVariable(f'warehouse_{row["Warehouse_ID"]}', cat=LpBinary) for row in warehouse_distances}

    # Objective function based on the optimization criterion
    if optimization_criterion == 'cost':
        prob += lpSum(warehouse_vars[wd['Warehouse_ID']] * wd['Cost'] for wd in warehouse_distances)
    elif optimization_criterion == 'distance':
        prob += lpSum(warehouse_vars[wd['Warehouse_ID']] * wd['Total_Distance'] for wd in warehouse_distances)
    elif optimization_criterion == 'both':
        max_distance = max([wd['Total_Distance'] for wd in warehouse_distances])
        max_cost = max([wd['Cost'] for wd in warehouse_distances])

        for wd in warehouse_distances:
            wd['Distance_Score'] = wd['Total_Distance'] / max_distance
            wd['Cost_Score'] = wd['Cost'] / max_cost
            wd['Combined_Score'] = wd['Distance_Score'] + wd['Cost_Score']

        prob += lpSum(warehouse_vars[wd['Warehouse_ID']] * wd['Combined_Score'] for wd in warehouse_distances)
    elif optimization_criterion == 'capacity':
        max_capacity = max([wd['Capacity'] for wd in warehouse_distances])
        for wd in warehouse_distances:
            wd['Capacity_Score'] = wd['Capacity'] / max_capacity

        prob += -lpSum(warehouse_vars[wd['Warehouse_ID']] * wd['Capacity_Score'] for wd in warehouse_distances)
    else:
        return jsonify({'error': 'Invalid criterion'}), 400

    # Add constraints: only one warehouse can be chosen
    prob += lpSum(warehouse_vars[wd['Warehouse_ID']] for wd in warehouse_distances) == 1

    # Solve the problem
    prob.solve()

    # Get the optimal warehouse
    optimal_warehouse_id = [var.name.split('_')[1] for var in warehouse_vars.values() if var.value() == 1]
    if not optimal_warehouse_id:
        return jsonify({'error': 'No warehouse selected'}), 400

    optimal_warehouse = next(wd for wd in warehouse_distances if wd['Warehouse_ID'] == int(optimal_warehouse_id[0]))

    return jsonify({'optimalWarehouse': optimal_warehouse})

@app.route('/api/getOptimalWarehouseLocation', methods=['GET'])
def get_optimal_warehouse_location():
    # Assuming the optimal warehouse location has already been calculated and is available
    optimal_warehouse = request.json.get('optimalWarehouse')
    return jsonify(optimal_warehouse)



@app.route('/api/get-traffic-info')
def get_traffic_info():
    traffic_info = {
        "speed": f"{random.randint(20, 65)} km/h",
        "avgSpeed": f"{random.randint(20, 60)} km/h",
        "congestion": f"{random.randint(0, 100)}%"
    }
    return jsonify(traffic_info)


@app.route('/get_weather')
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={API_KEY}'
    response = requests.get(url)
    weather_data = response.json()

    result = {
        'temperature': weather_data['main']['temp'],
        'weather': weather_data['weather'][0]['description'],
        'humidity': weather_data['main']['humidity'],
        'wind_speed': weather_data['wind']['speed']
    }

    return jsonify(result)

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 8080)

